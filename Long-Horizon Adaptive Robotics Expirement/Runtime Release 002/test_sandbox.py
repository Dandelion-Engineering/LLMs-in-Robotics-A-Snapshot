"""Bounded adversarial OS checks. Fixtures are not experiment evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from sandbox import CandidateSandbox, SandboxError, SandboxLimits, _wsl_path


FIXTURE = r'''
import json, os, resource, socket, subprocess, time
from pathlib import Path
class Candidate:
    def __init__(self, kind, episode_dir, persistent):
        self.directory=episode_dir; self.events=[]; self.last=None
    def accept_model(self, response):
        self.last=response; self.events.append({'event':'model_received','text':response})
    def accept_feedback(self, feedback):
        self.events.append({'event':'feedback_received','feedback':feedback})
    def drain_events(self):
        events=self.events; self.events=[]; return events
    def step(self, packet):
        mode=packet['mode']; answer={'type':'wait'}
        if mode=='boundaries':
            checks={}
            checks['unmounted_outside']=not Path(packet['outside']).exists()
            checks['unmounted_repository']=not Path(packet['repository']).exists()
            checks['no_host_mount']=not Path('/mnt/c').exists()
            checks['clean_env']=set(os.environ).issubset({'PATH','HOME','LANG','LC_CTYPE','PWD'}) and os.environ.get('PWD')=='/work'
            checks['copied_code_only']=sorted(x.name for x in Path('/code').iterdir())==['candidate_worker.py','candidates.py']
            checks['private_proc']=not Path('/proc/1/root/mnt/c').exists()
            answer['checks']=checks
            answer['limits']={str(k):list(resource.getrlimit(k)) for k in [resource.RLIMIT_CPU,resource.RLIMIT_AS,resource.RLIMIT_NPROC,resource.RLIMIT_FSIZE,resource.RLIMIT_NOFILE]}
            answer['uid']=os.getuid()
            answer['environment_keys']=sorted(os.environ)
        elif mode=='forbidden':
            try:
                attempt=packet['attempt']
                if attempt=='read':Path(packet['outside']).read_text()
                elif attempt=='write':Path('/code/candidates.py').write_text('changed')
                elif attempt=='network':socket.socket()
                elif attempt=='fork':os.fork()
                elif attempt=='subprocess':subprocess.run(['/usr/bin/true'])
                elif attempt=='native':
                    import ctypes
                    ctypes.CDLL(None)
            except BaseException:
                answer['caught_and_hidden']=True
        elif mode=='continuity':
            path=self.directory/'count.txt'; prior=int(path.read_text()) if path.exists() else 0
            path.write_text(str(prior+1)); tmp=Path('/tmp/witness')
            answer.update(count=prior+1,tmp_seen=tmp.exists(),last=self.last); tmp.write_text('now')
        elif mode=='file_limit':
            try:
                with open(self.directory/'large.bin','wb') as f: f.write(b'x'*16384)
                answer['blocked']=False
            except OSError: answer['blocked']=True
        elif mode=='memory_limit':
            try:
                blob=bytearray(128*1024*1024); answer['blocked']=False
            except MemoryError: answer['blocked']=True
        elif mode=='output_limit':
            os.write(1,b'x'*200000)
        elif mode=='invalid_json':
            os.write(1,b'{"value":NaN}\n')
        elif mode=='sleep':
            time.sleep(10)
        elif mode=='cpu':
            while True: pass
        elif mode=='heartbeat':
            while True:
                (self.directory/'heartbeat').write_text(str(time.monotonic())); time.sleep(.02)
        return answer
'''


class SandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sandbox-boundary-tests-")
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / "candidate_fixture.py"
        cls.source.write_text(FIXTURE, encoding="utf-8")
        cls.sentinel = cls.root / "evaluator-sentinel.txt"
        cls.sentinel.write_text("private-evaluator-fixture-must-not-be-visible", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def sandbox(self, name, persistent=True, **limits):
        return CandidateSandbox("boundary-fixture", self.root / name, persistent,
                                candidate_path=self.source, limits=SandboxLimits(**limits))

    def ask(self, worker, mode, **packet):
        worker.send({"type":"step", "packet":{"mode":mode, **packet}})
        return worker.receive(5)["response"]

    def test_actual_filesystem_network_process_and_environment_boundary(self):
        with self.sandbox("boundaries") as worker:
            result=self.ask(worker,"boundaries",outside=_wsl_path(self.sentinel),repository=_wsl_path(Path(__file__)))
            self.assertTrue(all(result["checks"].values()),json.dumps(result,indent=2))
            self.assertIn("clone3",worker.ready["restrictions"]["seccomp_denied_syscalls"])
            self.assertTrue(all(pair[0]==pair[1] for pair in result["limits"].values()))
            self.assertEqual(worker.ready["restrictions"]["cwd"],"/work")
            print("\nVerified OS restrictions:",json.dumps(result["checks"],sort_keys=True))
        self.assertIn(worker.termination,{"terminated","already_exited"})
        self.assertIsNotNone(worker.process.poll())

    def test_denied_python_operations_cannot_be_caught_as_success(self):
        for attempt in ('read','write','network','fork','subprocess','native'):
            with self.subTest(attempt=attempt), self.sandbox('denied-'+attempt) as worker:
                worker.send({'type':'step','packet':{'mode':'forbidden','attempt':attempt,'outside':_wsl_path(self.sentinel)}})
                with self.assertRaisesRegex(SandboxError,'CANDIDATE_CONTRACT_VIOLATION'):
                    worker.receive(5)
                self.assertIn('candidate_contract_violation',worker.stderr)

    def test_persistence_and_ephemeral_channels_across_real_restarts(self):
        for persistent,expected in ((True,[1,2]),(False,[1,1])):
            counts=[]
            for _ in range(2):
                with self.sandbox("persistent" if persistent else "ephemeral",persistent) as worker:
                    result=self.ask(worker,"continuity")
                    counts.append(result["count"])
                    self.assertFalse(result["tmp_seen"])
                    if not persistent:
                        self.assertNotEqual(worker.work_dir,worker.episode_dir)
                if not persistent:
                    self.assertFalse(worker.work_dir.exists())
            self.assertEqual(counts,expected)

    def test_opaque_model_feedback_and_drained_events(self):
        opaque='line one\n</script> "quote" Ω \\ path'
        with self.sandbox("ipc") as worker:
            self.assertIsNone(worker.poll())
            worker.send({"type":"model_response","text":opaque})
            reply=worker.receive(5)
            self.assertEqual(reply["events"],[{"event":"model_received","text":opaque}])
            self.assertEqual(self.ask(worker,"continuity")["last"],opaque)
            worker.send({"type":"feedback","feedback":{"outcome":"failed","sequence":7}})
            self.assertEqual(worker.receive(5)["events"][0]["feedback"]["sequence"],7)
            worker.send({"type":"step","packet":{"mode":"continuity"}})
            self.assertEqual(worker.receive(5)["events"],[])

    def test_actual_file_size_and_address_space_limits(self):
        with self.sandbox("resource",file_bytes=8192,memory_bytes=64*1024*1024) as worker:
            self.assertTrue(self.ask(worker,"file_limit")["blocked"])
            self.assertLessEqual((worker.work_dir/"large.bin").stat().st_size,8192)
            self.assertTrue(self.ask(worker,"memory_limit")["blocked"])

    def test_output_limit_terminates_candidate(self):
        with self.sandbox("output",output_bytes=65536,line_bytes=262144) as worker:
            worker.send({"type":"step","packet":{"mode":"output_limit"}})
            with self.assertRaisesRegex(SandboxError,"output cap"):
                worker.receive(5)
        self.assertIn(worker.termination,{"terminated","already_exited"})

    def test_wall_timeout_terminates_candidate(self):
        with self.sandbox("wall",wall_seconds=2,startup_seconds=10) as worker:
            worker.send({"type":"step","packet":{"mode":"sleep"}})
            with self.assertRaisesRegex(SandboxError,"wall timeout"):
                worker.receive(5)
        self.assertIn(worker.termination,{"terminated","already_exited"})

    def test_nonstandard_json_cannot_cross_ipc_boundary(self):
        with self.sandbox("invalid-json") as worker:
            worker.send({"type":"step","packet":{"mode":"invalid_json"}})
            with self.assertRaisesRegex(SandboxError,"IPC violation"):
                worker.receive(5)

    def test_cpu_limit_terminates_busy_candidate(self):
        with self.sandbox("cpu",cpu_seconds=1) as worker:
            worker.send({"type":"step","packet":{"mode":"cpu"}})
            with self.assertRaises(SandboxError):
                worker.receive(5)
        self.assertIsNotNone(worker.process.poll())

    def test_close_stops_linux_process_without_stopping_distribution(self):
        worker=self.sandbox("termination").start()
        worker.send({"type":"step","packet":{"mode":"heartbeat"}})
        heartbeat=worker.work_dir/"heartbeat"
        deadline=time.monotonic()+3
        while not heartbeat.exists() and time.monotonic()<deadline:
            time.sleep(.02)
        self.assertTrue(heartbeat.exists())
        worker.close()
        before=heartbeat.read_bytes()
        time.sleep(.1)
        self.assertEqual(before,heartbeat.read_bytes())
        self.assertIn(worker.termination,{"terminated","already_exited"})
        with self.sandbox("after-termination") as following:
            self.assertEqual(self.ask(following,"continuity")["count"],1)


if __name__=="__main__":
    unittest.main(verbosity=2)
