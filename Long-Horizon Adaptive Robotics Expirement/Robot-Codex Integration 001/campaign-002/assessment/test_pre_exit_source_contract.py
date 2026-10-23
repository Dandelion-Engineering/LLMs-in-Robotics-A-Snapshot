"""Only the exact old/current mirror producer identities are accepted."""
import io
from pathlib import Path
import unittest
import zipfile

import literal_read_segments as subject
import canary_readback_proof as canary

class SourceContractTests(unittest.TestCase):
    def source(self):
        campaign=Path(__file__).resolve().parents[1]
        return (campaign/'harness/runtime.py').read_bytes(),campaign

    def verify(self,records):
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as archive:
            for name,raw in records:archive.writestr(name,raw)
        with zipfile.ZipFile(io.BytesIO(output.getvalue())) as archive:
            return subject.mirror_source_contract(archive)

    def test_old_and_current_return_the_actual_consumed_identity(self):
        current,campaign=self.source()
        archive=campaign.parent.parent/'Architecture Map/releases/RCI001-C02-dev-092/code.zip'
        with zipfile.ZipFile(archive) as source:
            names=[n for n in source.namelist() if n.endswith(subject.MIRROR_SOURCE)]
            self.assertEqual(len(names),1);old=source.read(names[0])
        addition=b'                args.native_exit_barrier=self.native_exit_barrier\n'
        selection=b'                args.native_process_drain=True\n'
        self.assertEqual(current.count(selection),1)
        prior=current.replace(selection,b'')
        self.assertEqual(prior.count(addition),1);self.assertEqual(prior.replace(addition,b''),old)
        for raw in (old,prior,current):
            proof=self.verify([('source'+subject.MIRROR_SOURCE,raw)])
            self.assertEqual(proof['sha256'],subject.sha(raw))
            self.assertIn(proof['sha256'],canary.REVIEWED_RUNTIME_HASHES)

    def test_unknown_missing_duplicate_sources_rejected(self):
        current,_=self.source()
        for records in ([],[('source'+subject.MIRROR_SOURCE,current+b'\n')],
                [('a'+subject.MIRROR_SOURCE,current),('b'+subject.MIRROR_SOURCE,current)]):
            with self.subTest(count=len(records)),self.assertRaises(ValueError):self.verify(records)

if __name__=='__main__':unittest.main()
