"""Port the already-proven controls to explicit production wiring."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]
P = HERE.parent/'graceful-process-drain-001'

def remove_method(text, name):
    start = text.index('    def '+name)
    end = text.find('\n    def ', start+1)
    if end == -1: end = text.index("\nif __name__", start)
    return text[:start]+text[end:]

def write(path, text):
    with path.open('x', encoding='utf-8', newline='\n') as stream: stream.write(text)

def main():
    text = (P/'test_candidate.py').read_text(encoding='utf-8')
    text = text.replace("sys.path.insert(0, str(HERE.parents[1]/'harness'))\n", '')
    text = text.replace('import build_candidate\n', '').replace('import candidate_native as native', 'import native_process_quiescence as native')
    text = remove_method(text, 'test_exact_derivation_preserves_the_rest_of_controller')
    text = text.replace('            return native.close(client, 32*1024*1024)',
        '            client.args.native_process_drain = True\n            return client.close()')
    text = text.replace('        self.bridge.native_exit_barrier = lambda request: subject.bridge_join(self.bridge, request)\n', '')
    text = text.replace('            client.args.native_exit_barrier = lambda request: subject.bridge_join(self.bridge, request)',
                        '            client.args.native_exit_barrier = self.fixture.native_exit_barrier')
    marker = "    def test_normal_order_and_hash_binding(self):"
    checks = '''    def test_production_implementation_matches_diagnostic(self):
        candidate = HERE.parent/'io-repair/graceful-process-drain-001'
        self.assertEqual((HERE/'native_process_quiescence.py').read_bytes(), (candidate/'candidate_native.py').read_bytes())
        self.assertEqual((HERE/'process_drain.py').read_bytes(), (candidate/'process_drain.py').read_bytes())
        self.assertEqual(native.GRACEFUL_SECONDS, 5); self.assertEqual(native.TOTAL_SECONDS, 10)

    def test_selection_is_boolean_and_legacy_default_is_retained(self):
        client, _ = self.client(); client.args.native_process_drain = 'true'
        with self.assertRaises(RuntimeError): client.close()
        self.assertFalse(client.cleanup_started)
        client.args.native_process_drain = False
        self.assertTrue(client.close()['qualified'])

'''
    text = text.replace(marker, checks+marker)
    write(C/'harness/test_native_process_quiescence.py', text)
    text = (P/'test_reader.py').read_text(encoding='utf-8')
    start, end = text.index('HERE = '), text.index('from test_cleanup_transport')
    text = text[:start]+'''HERE = Path(__file__).resolve().parent
import transport_integrity_v3 as transport
import process_integrity as subject
'''+text[end:]
    text = remove_method(text, 'test_every_original_reader_check_is_preserved')
    text = remove_method(text, 'test_actual_overlay_is_process_local_and_restores_on_exception')
    marker = "if __name__ == '__main__': unittest.main()"
    text = text.replace(marker, '''    def test_partial_declaration_never_falls_back_to_legacy(self):
        for missing in subject.EXCLUSIVE:
            f = self.make(); del f.frozen['sources'][missing]
            with self.assertRaisesRegex(ValueError, 'incomplete'): self.verify(f)

    def test_original_unmarked_transport_remains_legacy(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        f = upgrade(Fixture(root, count=2)); f.write()
        with patch.object(transport, 'REPO', f.repo):
            result = transport.verify_transport_integrity(f.stage, f.frozen)
        self.assertTrue(result['passed']); self.assertNotIn('native_process_drain', result)

'''+marker)
    write(C/'assessment/test_process_integrity.py', text)

if __name__ == '__main__': main()
