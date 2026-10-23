import unittest
from recover import mutations, python_literals, workspace_path


class EvidenceBoundaries(unittest.TestCase):
    def test_unknown_append_never_becomes_an_empty_before_state(self):
        writes,_,gaps=mutations("cat >> notes/a.md <<'EOF'\nsuffix\nEOF",{})
        self.assertEqual(writes,[])
        self.assertEqual(len(gaps),1)

    def test_copy_append_preserves_bytes_and_source(self):
        writes,ops,gaps=mutations("cp notes/a.md notes/b.md && cat >> notes/b.md <<'EOF'\nmore\nEOF",{'notes/a.md':b'prior\n'})
        self.assertEqual(writes[-1][1],b'prior\nmore\n')
        self.assertEqual(ops,[{'operation':'cp','from':'notes/a.md','to':'notes/b.md'}])
        self.assertFalse(gaps)

    def test_retained_code_can_never_execute(self):
        with self.assertRaises(ValueError):
            python_literals("from pathlib import Path; __import__('os').system('whoami')",{})

    def test_unsupported_expression_cannot_read_live_files(self):
        with self.assertRaises((KeyError,ValueError)):
            python_literals("from pathlib import Path; p=Path('notes/missing.md'); s=p.read_text(); p.write_text(s)",{})

    def test_literal_edit_with_embedded_newline(self):
        known={'notes/a.md':b'old\n'}
        out=python_literals("from pathlib import Path; p=Path('notes/a.md'); s=p.read_text(); s=s.replace('old','new'); p.write_text(s+'tail\\n')",known)
        self.assertEqual(out[0][1],b'new\ntail\n')

    def test_semicolon_inside_sed_replacement_is_content(self):
        writes,_,_=mutations("sed -i 's/old/new; still one replacement/' notes/a.md",{'notes/a.md':b'old\n'})
        self.assertEqual(writes[0][1],b'new; still one replacement\n')

    def test_line_delete_precedes_append(self):
        writes,_,_=mutations("sed -i '/^Next consequential step:/d' notes/a.md\ncat >> notes/a.md <<'EOF'\ndone\nEOF",{'notes/a.md':b'keep\nNext consequential step: move\n'})
        self.assertEqual(writes[-1][1],b'keep\ndone\n')

    def test_copy_after_heredoc_is_also_recovered(self):
        writes,_,_=mutations("cat >> notes/a.md <<'EOF'\nmore\nEOF\ncp notes/a.md notes/result.md",{'notes/a.md':b'prior\n'})
        self.assertEqual(writes[-1],('notes/result.md',b'prior\nmore\n','literal_cp'))

    def test_traversal_and_absolute_path_rejected(self):
        for p in ('../x','/etc/passwd','file:///proc/1/root/secret'):
            with self.assertRaises(ValueError): workspace_path(p)


if __name__=='__main__': unittest.main()
