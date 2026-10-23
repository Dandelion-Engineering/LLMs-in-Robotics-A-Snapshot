"""Synthetic process metadata only; no CIM query, queue job or signal."""
import copy
from pathlib import Path
import unittest

import calibration_authority as authority


def fixture():
    launcher=str(Path('venv/Scripts/python.exe').resolve());base=str(Path('base/python.exe').resolve())
    script=str(Path('physical_calibration.py').resolve());argv=[launcher,'-X','utf8','-B',script,'--mode','held-recovery','--output','protected']
    times=[f'2026-09-23T04:00:0{i}+00:00' for i in range(5)]
    def row(pid,ppid,executable,args,created):return {'pid':pid,'parent_pid':ppid,'executable':executable,'argv':args,'created_at':created}
    job={'id':'synthetic-job','state':'running','child_pid':200,'worker_pid':100,'resolved_executable':launcher,
         'argv':argv,'cwd':str(Path.cwd()),'started_at':times[0]}
    command=authority.child_command(launcher,script,'held-recovery','protected/held-recovery',0,'protected/manifest.json','a'*64)
    rows={200:row(200,100,launcher,argv,times[1]),300:row(300,200,base,[base,*argv[1:]],times[2]),
          400:row(400,300,launcher,command,times[3]),500:row(500,400,base,[base,*command[1:]],times[4])}
    proof={'job_id':job['id'],'pid':300,'parent_pid':200,'queue_job':copy.deepcopy(job),
           'driver_metadata':copy.deepcopy(rows[300]),'driver_parent_metadata':copy.deepcopy(rows[200]),
           'launcher_executable':launcher,'base_executable':base,'script':script}
    return {'queue':proof},job,rows,command


class QueueChainTests(unittest.TestCase):
    def verify(self,manifest,job,rows,command):return authority.validate_child_chain(manifest,job,500,400,rows,command)
    def test_exact_two_launcher_interpreter_pairs_pass(self):
        manifest,job,rows,command=fixture()
        result=self.verify(manifest,job,rows,command)
        self.assertEqual(result['driver_pid'],300);self.assertEqual(result['probe_launcher_pid'],400)
    def test_arbitrary_descendant_or_wrong_parent_fails(self):
        for pid,new_parent in ((500,450),(400,350),(300,199),(200,99)):
            with self.subTest(pid=pid):
                manifest,job,rows,command=fixture();rows[pid]['parent_pid']=new_parent
                with self.assertRaises(authority.CalibrationAuthorityError):self.verify(manifest,job,rows,command)
    def test_child_wrapper_or_argument_drift_fails(self):
        for pid in (400,500):
            for mutation in ('wrapper','different-mode','different-output','executable'):
                with self.subTest(pid=pid,mutation=mutation):
                    manifest,job,rows,command=fixture()
                    if mutation=='wrapper':rows[pid]['argv'].insert(1,'wrapper.py')
                    elif mutation=='different-mode':rows[pid]['argv'][rows[pid]['argv'].index('held-recovery')]='adapters'
                    elif mutation=='different-output':rows[pid]['argv'][rows[pid]['argv'].index('--output')+1]='other'
                    else:rows[pid]['executable']=str(Path('other-python.exe').resolve())
                    with self.assertRaises(authority.CalibrationAuthorityError):self.verify(manifest,job,rows,command)
    def test_parent_pid_reuse_or_argument_drift_fails(self):
        for pid in (200,300):
            with self.subTest(pid=pid):
                manifest,job,rows,command=fixture();rows[pid]['created_at']='2026-09-23T04:00:09+00:00'
                with self.assertRaises(authority.CalibrationAuthorityError):self.verify(manifest,job,rows,command)
    def test_ended_replaced_or_rewritten_queue_job_fails(self):
        for field,value in (('state','succeeded'),('child_pid',201),('worker_pid',101),('id','other'),('argv',['wrapper.py'])):
            with self.subTest(field=field):
                manifest,job,rows,command=fixture();job[field]=value
                with self.assertRaises(authority.CalibrationAuthorityError):self.verify(manifest,job,rows,command)
    def test_creation_order_and_timezone_required(self):
        for timestamp in ('2026-09-23T03:00:00+00:00','2026-09-23T04:00:04'):
            with self.subTest(timestamp=timestamp):
                manifest,job,rows,command=fixture();rows[500]['created_at']=timestamp
                with self.assertRaises(authority.CalibrationAuthorityError):self.verify(manifest,job,rows,command)
    def test_missing_exact_metadata_fails(self):
        manifest,job,rows,command=fixture();del rows[200]
        with self.assertRaises(authority.CalibrationAuthorityError):self.verify(manifest,job,rows,command)


if __name__=='__main__':unittest.main()
