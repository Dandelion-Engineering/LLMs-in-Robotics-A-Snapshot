"""Destructive-path safeguards tested only in temporary fixture roots."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('retention',Path(__file__).with_name('retention.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class Safeguards(unittest.TestCase):
    def gate(self,p,m):
        return {'status':'passed','partition_sha256':r.sha(p),'deletion_manifest_sha256':r.sha(m),'checks':dict.fromkeys(r.GATES,True),'evidence_refs':[{'path':p.relative_to(r.ROOT).as_posix(),'sha256':r.sha(p)}]}
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.old=r.ROOT,r.EXP,r.HERE,r.R4,r.ATTEMPTS
        r.ROOT=self.root;r.EXP=self.root/'experiment';r.HERE=r.EXP/'implementation';r.R4=r.EXP/'Evidence/releases/batch01-eval-r4';r.ATTEMPTS=r.R4/'attempts'
        self.frame=r.ATTEMPTS/'run/evidence/frames/000001.png';self.frame.parent.mkdir(parents=True);self.frame.write_bytes(b'fixture RGB')
        self.rel=self.frame.relative_to(r.ROOT).as_posix()
        r.checked_directory.cache_clear()
    def tearDown(self):
        r.checked_directory.cache_clear()
        r.ROOT,r.EXP,r.HERE,r.R4,r.ATTEMPTS=self.old;self.temp.cleanup()
    def validation_fixture(self,retained_count=1):
        """A real bounded tree with retained, retired and non-frame evidence."""
        refs={};retained=[]
        for index in range(1,retained_count+1):
            p=self.frame.parent/f'{index:06d}.png'
            if index!=1:p.write_bytes(f'RGB fixture {index:06d}'.encode())
            retained.append(p)
        retired=self.frame.parent/'900000-depth.npz';retired.write_bytes(b'fixture depth')
        for kind,paths in [('retained',retained),('deletion',[retired])]:
            manifest=r.HERE/'manifests'/f'validation-{kind}.jsonl.gz';writer=r.Writer(manifest)
            for p in paths:
                st=p.stat();row={'path':p.relative_to(r.ROOT).as_posix(),'logical_bytes':st.st_size,'mtime_ns':st.st_mtime_ns}
                if kind=='retained':row['sha256']=r.sha(p)
                writer.put(row)
            writer.close()
            refs[kind]={'path':manifest.relative_to(r.ROOT).as_posix(),'sha256':r.sha(manifest),'files':writer.count,'logical_bytes':writer.bytes}
        protected=self.frame.parent.parent/'events.jsonl';protected.write_bytes(b'{"protected":true}\n')
        st=protected.stat()
        r.emit(r.HERE/'records/fixture-census/protected-metadata.json',[
            {'path':protected.relative_to(r.ROOT).as_posix(),'logical_bytes':st.st_size,'mtime_ns':st.st_mtime_ns}])
        r.emit(r.HERE/'records/validation-partition.json',{'census':'fixture-census','manifests':refs})
        return retained,retired,protected,refs
    def validate_fixture(self,phase,after=False):
        with contextlib.redirect_stdout(io.StringIO()):
            r.validate(argparse.Namespace(name='validation',phase=phase,after=after))
        return r.read(r.HERE/'records'/f'validation-{phase}-validation.json')
    def test_exact_frame_leaf_only(self):
        self.assertEqual(r.safe_frame(self.rel),self.frame)
        for bad in ['../escape.png',str(self.frame),self.rel.replace('frames/000001.png','events.jsonl'),self.rel.replace('000001.png','000001.png.bak'),self.rel.replace('/','\\')]:
            with self.assertRaises((ValueError,FileNotFoundError)):r.safe_frame(bad)
    def test_missing_leaf_is_not_substituted(self):
        missing=self.rel.replace('000001','000002')
        with self.assertRaises(FileNotFoundError):r.safe_frame(missing)
        self.assertFalse(r.safe_frame(missing,False).exists())
    def test_deterministic_gzip_and_metadata(self):
        paths=[r.HERE/'one.gz',r.HERE/'two.gz']
        row={'path':self.rel,'logical_bytes':11}
        for p in paths:
            w=r.Writer(p);w.put(row);w.close()
        self.assertEqual(paths[0].read_bytes(),paths[1].read_bytes())
        self.assertEqual(list(r.rows(paths[0])),[row])
        with self.assertRaises(FileExistsError):r.Writer(paths[0])
    def test_gate_required_before_unlink(self):
        part=r.HERE/'records/test-partition.json';r.emit(part,{'manifests':{}})
        gate=r.HERE/'records/gate.json';r.emit(gate,{'status':'failed'})
        with self.assertRaises(ValueError):r.delete(argparse.Namespace(name='test',gate=str(gate)))
        self.assertTrue(self.frame.exists())
    def test_identity_mismatch_stops_and_records_failure(self):
        st=self.frame.stat();m=r.HERE/'manifests/deletion.jsonl.gz';w=r.Writer(m)
        w.put({'path':self.rel,'logical_bytes':st.st_size+1,'mtime_ns':st.st_mtime_ns});w.close()
        ref={'path':m.relative_to(r.ROOT).as_posix(),'sha256':r.sha(m),'files':1,'logical_bytes':st.st_size+1}
        p=r.HERE/'records/test-partition.json';r.emit(p,{'manifests':{'deletion':ref}})
        gate=r.HERE/'records/gate.json';r.emit(gate,self.gate(p,m))
        with self.assertRaises(ValueError):r.delete(argparse.Namespace(name='test',gate=str(gate)))
        self.assertTrue(self.frame.exists())
        self.assertEqual(r.read(r.HERE/'records/test-deletion-receipts/00000-failure.json')['removed'],[])
    def test_only_manifest_leaf_deleted(self):
        protected=self.frame.parent.parent/'events.jsonl';protected.write_bytes(b'keep exact events')
        st=self.frame.stat();m=r.HERE/'manifests/deletion.jsonl.gz';w=r.Writer(m)
        w.put({'path':self.rel,'logical_bytes':st.st_size,'mtime_ns':st.st_mtime_ns});w.close()
        ref={'path':m.relative_to(r.ROOT).as_posix(),'sha256':r.sha(m),'files':1,'logical_bytes':st.st_size}
        p=r.HERE/'records/test-partition.json';r.emit(p,{'manifests':{'deletion':ref}})
        gate=r.HERE/'records/gate.json';r.emit(gate,self.gate(p,m))
        r.delete(argparse.Namespace(name='test',gate=str(gate)))
        self.assertFalse(self.frame.exists());self.assertEqual(protected.read_bytes(),b'keep exact events')
        receipt=r.read(r.HERE/'records/test-deletion-receipts/00000-complete.json')
        self.assertEqual(receipt['count'],1)
        self.assertEqual(receipt['removed_paths_sha256'],hashlib.sha256((self.rel+'\n').encode()).hexdigest())

    def test_validate_pre_and_post_exact_totals_across_batch_boundary(self):
        retained,retired,protected,refs=self.validation_fixture(retained_count=260)
        before_protected=protected.read_bytes()
        pre=self.validate_fixture('pre')
        self.assertEqual(pre['status'],'passed');self.assertEqual(pre['phase'],'pre')
        for kind,ref in refs.items():
            self.assertEqual(pre['counts'][kind],{'files':ref['files'],'logical_bytes':ref['logical_bytes']})
        self.assertEqual(pre['protected_nonframe_metadata_checked'],1)
        self.assertTrue(retired.exists())
        # Only a file under this test's TemporaryDirectory is retired.
        self.assertTrue(retired.is_relative_to(self.root));retired.unlink()
        post=self.validate_fixture('post',after=True)
        self.assertEqual(post['status'],'passed');self.assertEqual(post['phase'],'post')
        self.assertEqual(pre['counts'],post['counts'])
        self.assertEqual(pre['partition_sha256'],post['partition_sha256'])
        self.assertEqual(protected.read_bytes(),before_protected)
        self.assertTrue(all(p.exists() for p in retained))

    def test_validate_detects_same_size_same_mtime_retained_corruption(self):
        retained,retired,protected,_=self.validation_fixture()
        path=retained[0];st=path.stat();original=path.read_bytes()
        path.write_bytes(bytes([original[0]^1])+original[1:])
        os.utime(path,ns=(st.st_atime_ns,st.st_mtime_ns))
        self.assertEqual((path.stat().st_size,path.stat().st_mtime_ns),(st.st_size,st.st_mtime_ns))
        with self.assertRaises(RuntimeError):self.validate_fixture('corrupt')
        report=r.read(r.HERE/'records/validation-corrupt-validation.json')
        self.assertEqual(report['status'],'failed')
        self.assertEqual([x[0] for x in report['errors']],[path.relative_to(r.ROOT).as_posix()])
        self.assertIn('SHA',report['errors'][0][1])
        self.assertTrue(retired.exists());self.assertTrue(protected.exists())

    def test_validate_post_refuses_a_deletion_leaf_that_still_exists(self):
        _,retired,_,_=self.validation_fixture()
        with self.assertRaises(RuntimeError):self.validate_fixture('still-present',after=True)
        report=r.read(r.HERE/'records/validation-still-present-validation.json')
        self.assertEqual(report['status'],'failed')
        self.assertEqual([x[0] for x in report['errors']],[retired.relative_to(r.ROOT).as_posix()])
        self.assertTrue(retired.exists())

    def test_validate_refuses_protected_nonframe_metadata_change(self):
        retained,retired,protected,_=self.validation_fixture()
        protected.write_bytes(b'changed protected event evidence')
        with self.assertRaises(RuntimeError):self.validate_fixture('protected-change')
        report=r.read(r.HERE/'records/validation-protected-change-validation.json')
        self.assertEqual(report['status'],'failed')
        self.assertEqual([x[0] for x in report['errors']],[protected.relative_to(r.ROOT).as_posix()])
        self.assertTrue(retired.exists());self.assertTrue(all(p.exists() for p in retained))

    def test_validate_rejects_tampered_manifest_before_using_rows(self):
        retained,retired,_,refs=self.validation_fixture()
        manifest=r.ROOT/refs['retained']['path']
        with manifest.open('ab') as stream:stream.write(b'tampered')
        with self.assertRaises((AssertionError,ValueError,RuntimeError)):
            self.validate_fixture('manifest-tamper')
        self.assertFalse((r.HERE/'records/validation-manifest-tamper-validation.json').exists())
        self.assertTrue(retired.exists());self.assertTrue(all(p.exists() for p in retained))

    def test_validate_parallel_errors_keep_manifest_order(self):
        retained,retired,_,_=self.validation_fixture(retained_count=260)
        changed=[retained[17],retained[259]]
        for path in changed:path.write_bytes(b'corrupted and changed size')
        with self.assertRaises(RuntimeError):self.validate_fixture('ordered-errors')
        report=r.read(r.HERE/'records/validation-ordered-errors-validation.json')
        self.assertEqual([x[0] for x in report['errors']],[p.relative_to(r.ROOT).as_posix() for p in changed])
        self.assertTrue(retired.exists())

if __name__=='__main__':unittest.main()
