"""Deterministic owner identity and read-only TCP table admission checks."""
import copy
from pathlib import Path
import tempfile
import threading
import unittest

from codehost_owner import OwnerRegistry, OwnerError


class Process:
    pid = 271
    def __init__(self): self.exit = None
    def poll(self): return self.exit


class API:
    def __init__(self, binary):
        self.identity = {'pid':271, 'process_creation_filetime':9001,'queried_executable_path':str(binary)}
        self.rows = [{'state':5,'pid':271,'local':('127.0.0.1',41000),'remote':('127.0.0.1',42000)}]
    def process(self, pid): return dict(self.identity)
    def tcp4(self): return copy.deepcopy(self.rows)


class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.binary = Path(self.temp).resolve()/'native.exe'; self.binary.write_bytes(b'fixed test binary')
        self.api = API(self.binary); self.process = Process(); self.time = 0
        self.owner = OwnerRegistry(api=self.api, process_type=Process, clock=lambda:self.time, sleep=self.advance)
    def advance(self, seconds): self.time += seconds
    def auth(self): return self.owner.authenticate(('127.0.0.1',41000),('127.0.0.1',42000))
    def register(self): return self.owner.register(self.process,self.binary)

    def test_registration_exact_process_creation_binary_and_tuple(self):
        record=self.register(); proof=self.auth()
        self.assertEqual(record['owner_kind'],'model_client')
        self.assertEqual(record['pid'],proof['owner_pid'])
        self.assertEqual(record['process_creation_filetime'],proof['process_creation_filetime'])
        self.assertEqual(record['executable']['sha256'],proof['executable_sha256'])
        self.assertEqual(proof['lookup_attempts'],1)
        record['executable']['sha256']='mutated'; self.assertNotEqual(self.owner.owner['executable']['sha256'],'mutated')

    def test_missing_and_repeated_registration(self):
        with self.assertRaisesRegex(OwnerError,'not_registered'): self.auth()
        self.register()
        with self.assertRaisesRegex(OwnerError,'duplicate'): self.register()

    def test_foreign_ambiguous_and_non_established_owners(self):
        self.register(); original=copy.deepcopy(self.api.rows)
        for rows in ([{**original[0],'pid':999}],original*2,[{**original[0],'state':8}]):
            self.api.rows=rows
            with self.assertRaises(OwnerError): self.auth()

    def test_missing_owner_lookup_has_quarter_second_bound(self):
        self.register(); self.api.rows=[]
        with self.assertRaisesRegex(OwnerError,'missing'): self.auth()
        self.assertAlmostEqual(self.time,.250)

    def test_bounded_metadata_race_retry_then_exact_match(self):
        self.register(); original=self.api.tcp4; calls=[]
        def table():
            calls.append(1); return [] if len(calls)<3 else original()
        self.api.tcp4=table
        self.assertEqual(self.auth()['lookup_attempts'],3)
        self.assertLess(self.time,.250)

    def test_pid_reuse_owner_death_and_executable_replacement(self):
        self.register(); self.api.identity['process_creation_filetime']+=1
        with self.assertRaisesRegex(OwnerError,'reused'): self.auth()
        self.api.identity['process_creation_filetime']-=1; self.process.exit=0
        with self.assertRaisesRegex(OwnerError,'exited'): self.auth()
        self.process.exit=None; self.binary.write_bytes(b'changed executable')
        with self.assertRaisesRegex(OwnerError,'file_changed'): self.auth()

    def test_wrong_executable_non_popen_and_non_loopback_fail(self):
        self.api.identity['queried_executable_path']=str(self.binary.with_name('other.exe'))
        with self.assertRaisesRegex(OwnerError,'executable_mismatch'): self.register()
        with self.assertRaisesRegex(OwnerError,'actual_popen'): self.owner.register(object(),self.binary)
        with self.assertRaisesRegex(OwnerError,'loopback'): self.owner.authenticate(('::1',41000),('127.0.0.1',42000))

    def test_parallel_registration_has_exactly_one_winner(self):
        successes=[];failures=[]
        def register():
            try: successes.append(self.register())
            except OwnerError as error: failures.append(str(error))
        threads=[threading.Thread(target=register) for _ in range(4)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual((len(successes),len(failures)),(1,3))
        self.assertEqual(set(failures),{'duplicate_owner_registration'})


if __name__=='__main__': unittest.main()
