"""Exercise exact plain-print form through all inherited adversarial controls."""
import unittest
import initial_read_composition as reader
import test_initial_read_composition as prior

class PlainPrintContracts(prior.InitialReadCompositionTests):
    def prefix(self,note=None,tail=b'/workspace/notes/a\n',command=None,**kwargs):
        return super().prefix(note,tail,command or 'cat /workspace/Continuity.md && '+reader.PRINT_FIND_SCRIPT,**kwargs)

    def test_plain_print_proves_only_full_initial_prefix(self):
        self.prefix(tail=b'unattributed suffix\n/workspace/programs/file\n')
        proof=self.accepted()
        self.assertEqual(proof['excluded_find_initial_prefixes'],['/workspace/notes','/workspace/programs'])
        self.assertEqual(proof['segment']['bytes'],len(self.note))
        self.assertFalse(proof['whole_current_file_identity_claimed'])
        self.assertFalse(proof['remainder_listing_snapshot_claimed'])

    def test_plain_print_mutations_are_not_recipes(self):
        valid='cat /workspace/Continuity.md && '+reader.PRINT_FIND_SCRIPT
        invalid=[valid+'\n',valid+'\r',valid+'; echo injected',valid+' #comment',valid+' > notes/x',
            valid.replace('&&','||'),valid.replace('find ','find -L '),valid.replace('-print','-print0'),
            valid.replace('-print','-printf x'),valid.replace('-type f','-type d'),
            valid.replace('-maxdepth 3','-maxdepth 4'),valid.replace('/workspace/notes','/workspace/live'),
            valid.replace('cat ','/tmp/cat '),valid.replace('cat ','cat -n '),
            valid.replace('find ','$(echo find) '),valid+' && cat Tasks.md']
        for command in invalid:
            with self.subTest(command=command):
                self.prefix(command=command);self.rejected()

    def test_plain_print_partial_or_forged_initial_bytes_rejected(self):
        for output in (self.note[:-1],self.note.replace(b'\n',b' ',1),b'forged\n'+self.note):
            with self.subTest(output=output):
                self.prefix()
                self.f.make_capture('cat /workspace/Continuity.md && '+reader.PRINT_FIND_SCRIPT,output=output.decode())
                self.rejected()

if __name__=='__main__':unittest.main()
