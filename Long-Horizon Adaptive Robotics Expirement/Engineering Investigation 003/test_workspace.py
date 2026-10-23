"""Regression checks use temporary synthetic stores, never project evidence."""
from html.parser import HTMLParser
import base64
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("workspace_builder", HERE / "build_workspace.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
amap = builder.load_map_module()


def unpack_snapshot(data):
    envelope=json.loads(data)
    compressed=base64.b64decode(envelope["data"],validate=True)
    raw=gzip.decompress(compressed)
    assert len(compressed)==envelope["compressed_bytes"]
    assert len(raw)==envelope["uncompressed_bytes"]
    assert hashlib.sha256(raw).hexdigest()==envelope["sha256"]
    return json.loads(raw)


class ScriptCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_data = False
        self.data = ""
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.in_data = tag == "script" and dict(attrs).get("id") == "map-data"

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_data = False

    def handle_data(self, data):
        if self.in_data:
            self.data += data


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.map_root = self.root / "Map with spaces"
        self.map_root.mkdir()
        self.output = self.root / "workspace" / "index.html"
        for filename in amap.KINDS.values():
            (self.map_root / filename).write_bytes(b"")

    def tearDown(self):
        self.tmp.cleanup()

    def architecture(self, title):
        record = amap.template("architecture")
        record.update(id="fixture-a", author="temporary synthetic test fixture",
                      recorded_at="2026-01-01T00:00:00+00:00", title=title,
                      summary="Test fixture, not a proposed architecture.")
        (self.map_root / "architectures.jsonl").write_text(
            json.dumps(record, ensure_ascii=True) + "\n", encoding="utf-8")
        return record

    def test_empty_store_builds_without_inventing_records(self):
        before = {f.name: f.read_bytes() for f in self.map_root.iterdir()}
        result = builder.build(self.map_root, self.output)
        self.assertEqual(set(result["counts"].values()), {0})
        parsed = ScriptCollector()
        parsed.feed(self.output.read_text(encoding="utf-8"))
        data = unpack_snapshot(parsed.data)
        self.assertEqual(data["records"], {kind: [] for kind in amap.KINDS})
        self.assertEqual(data["map_base"], "../Map%20with%20spaces/")
        self.assertEqual(data["paired_analysis"]["state"], "unavailable")
        self.assertIsNone(data["paired_analysis"]["report"])
        self.assertEqual(data["evidence_runs"], [])
        self.assertFalse(data["trace_selection"]["selection_is_statistical_denominator"])
        self.assertEqual(before, {f.name: f.read_bytes() for f in self.map_root.iterdir()})

    def test_hostile_record_text_cannot_close_embedded_script(self):
        hostile = '</script><img src=x onerror="alert(1)"><script> & \u2028 \u2029'
        original = self.architecture(hostile)
        builder.build(self.map_root, self.output)
        parsed = ScriptCollector()
        html = self.output.read_text(encoding="utf-8")
        parsed.feed(html)
        self.assertNotIn("img", parsed.tags)
        self.assertEqual(parsed.tags.count("script"), 2)
        self.assertEqual(unpack_snapshot(parsed.data)["records"]["architecture"][0], original)
        self.assertNotIn(hostile, html)
        self.assertNotIn("innerHTML", html)

    def test_invalid_store_cannot_replace_previous_workspace(self):
        builder.build(self.map_root, self.output)
        previous = self.output.read_bytes()
        (self.map_root / "architectures.jsonl").write_text('{"id":"broken"}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Map validation failed"):
            builder.build(self.map_root, self.output)
        self.assertEqual(previous, self.output.read_bytes())

    def test_entire_snapshot_archive_is_lossless_deterministic_and_safe(self):
        snapshot=builder.load_snapshot(self.map_root,self.output)
        runs=[{"run_id":"synthetic-only","events":[{"text":"</script> & Ω\u2028\u2029","payload_sha256":"b"*64}],
               "source_files":[{"sha256":"c"*64}]}]
        snapshot["evidence_runs"]=runs
        snapshot["run_metadata"]={"runs":[{"raw_result":{"diagnostic":"Repeated fixture only. "*10000}}]}
        before=json.loads(json.dumps(snapshot))
        parsed=ScriptCollector();parsed.feed(builder.render(snapshot))
        archive=json.loads(parsed.data)
        raw=gzip.decompress(base64.b64decode(archive["data"]))
        self.assertEqual(archive["format"],"robot-investigation-snapshot-1.0")
        self.assertEqual(raw,builder.safe_json(snapshot).encode("utf-8"))
        self.assertEqual(unpack_snapshot(parsed.data),before)
        self.assertEqual(snapshot,before)
        self.assertEqual(len(raw),archive["uncompressed_bytes"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),archive["sha256"])
        self.assertEqual(builder.pack_snapshot(snapshot),archive)
        self.assertEqual(builder.render(snapshot),builder.render(snapshot))
        self.assertLess(len(archive["data"]),len(raw)//5)
        self.assertNotIn(b"</script>",raw)
        self.assertEqual(base64.b64decode(archive["data"])[4:8],b"\0"*4)
        self.assertEqual(parsed.tags.count("script"),2)

    def test_nonfinite_snapshot_is_rejected_before_render(self):
        with self.assertRaises(ValueError):
            builder.render({"invalid":float("nan")})

    @unittest.skipUnless(shutil.which("node"), "Native JavaScript decoder checks need Node.js")
    def test_native_decoder_roundtrip_and_fail_closed_paths(self):
        template=(HERE/"workspace.html").read_text(encoding="utf-8")
        decoder=template.split("/*__SNAPSHOT_LOADER_START__*/")[1].split("/*__SNAPSHOT_LOADER_END__*/")[0]
        snapshot=builder.load_snapshot(self.map_root,self.output)
        snapshot["evidence_runs"]=[{"run_id":"synthetic-only","text":"</script> & Ω","payload_sha256":"a"*64}]
        encoded=builder.pack_snapshot(snapshot)
        invalid=builder.pack_snapshot({"records":None})
        setup="const assert=require('node:assert/strict');Object.defineProperty(globalThis,'crypto',{value:require('node:crypto').webcrypto,writable:true,configurable:true});\n"
        setup+="const packed="+json.dumps(encoded)+",expected="+json.dumps(snapshot)+",invalid="+json.dumps(invalid)+";\n"
        checks=r'''
(async()=>{
 assert.deepEqual(await decodeSnapshot(packed),expected);
 for(const change of [{format:'unknown'}, {encoding:'plain'}, {compressed_bytes:packed.compressed_bytes+1},
   {uncompressed_bytes:packed.uncompressed_bytes+1}, {uncompressed_bytes:packed.uncompressed_bytes-1},
   {uncompressed_bytes:NaN}, {sha256:'0'.repeat(64)}, {data:'not base64 !'}]){
   await assert.rejects(()=>decodeSnapshot({...packed,...change}));
 }
 const corrupt=Buffer.from(packed.data,'base64');corrupt[corrupt.length-8]^=1;
 await assert.rejects(()=>decodeSnapshot({...packed,data:corrupt.toString('base64')}));
 await assert.rejects(()=>decodeSnapshot(invalid),/canonical record collections/);
 const native=globalThis.DecompressionStream;globalThis.DecompressionStream=undefined;
 await assert.rejects(()=>decodeSnapshot(packed),/DecompressionStream support/);
 globalThis.DecompressionStream=native;
 const crypto=globalThis.crypto;globalThis.crypto=undefined;
 await assert.rejects(()=>decodeSnapshot(packed),/cannot verify/);globalThis.crypto=crypto;
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        process=subprocess.run([shutil.which("node"),"-"],input=setup+decoder+checks,
                               encoding="utf-8",capture_output=True,timeout=20)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertIn('inert aria-busy="true"',template)
        self.assertIn("Loading embedded snapshot",template)
        self.assertIn("workspace.inert=true",template)
        self.assertNotIn("fetch(",decoder)

    def test_changed_attachment_bytes_are_rejected(self):
        self.architecture("Temporary fixture")
        attachment = self.map_root / "fixture.md"
        attachment.write_text("Changed bytes", encoding="utf-8")
        revision = amap.template("revision")
        revision.update(id="fixture-r", author="temporary synthetic test fixture",
                        recorded_at="2026-01-01T00:00:00+00:00", architecture_id="fixture-a",
                        title="Fixture revision", summary="Only a fixture.", mechanism="No robot mechanism.",
                        attachments=[{"label": "Fixture attachment", "uri": "fixture.md", "sha256": "a" * 64,
                                      "state": "available", "access": "operator", "locator": None}])
        (self.map_root / "revisions.jsonl").write_text(json.dumps(revision) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Map validation failed"):
            builder.build(self.map_root, self.output)
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(shutil.which("node"), "Optional JavaScript checks need Node.js")
    def test_javascript_corrections_associations_filters_and_unsafe_links(self):
        template = (HERE / "workspace.html").read_text(encoding="utf-8")
        javascript = re.findall(r"<script>([\s\S]*?)</script>", template)[0]
        self.assertIn("/*__PLAYBACK_CODE__*/", javascript)
        javascript = javascript.split("/*__PLAYBACK_CODE__*/")[0]
        fixture = {"map_base": "../Architecture%20Map/", "records": {
            "architecture": [{"id": "a", "title": "Fixture", "details": {}}],
            "revision": [{"id": "v", "architecture_id": "a", "details": {}}],
            "run": [{"id": "r", "revision_id": "v", "stage": "development"},
                    {"id": "pending", "revision_id": "v", "stage": "development"}],
            "result": [{"id": "old", "run_id": "r", "supersedes_result_id": None,
                        "outcome": "success", "validity": "valid"},
                       {"id": "new", "run_id": "r", "supersedes_result_id": "old",
                        "outcome": "failure", "validity": "invalid"}],
            "note": [{"id": "n1", "target_ids": ["old"], "supersedes_note_id": None},
                     {"id": "n2", "target_ids": ["a"], "supersedes_note_id": "n1"}]
        }}
        harness = "globalThis.crypto=require('node:crypto').webcrypto;const elements=new Map();const packed="+json.dumps(builder.pack_snapshot(fixture))+";\n"
        harness += "const document={getElementById:id=>{if(!elements.has(id))elements.set(id,{textContent:id==='map-data'?JSON.stringify(packed):'',setAttribute(){}});return elements.get(id);}};\n"
        assertions = r'''
const assert = require('node:assert/strict');
assert.equal(currentResults.length, 1);
assert.equal(currentResult('r').id, 'new');
assert.equal(supersededNotes.has('n1'), true);
assert.equal(noteSubjects(byId.get('n2')).has('old'), true);
assert.equal(linkedIds('a').has('new'), true);
state.outcome='success'; assert.equal(filteredRuns().length, 0);
state.outcome='failure'; assert.equal(filteredRuns()[0].id, 'r');
state.outcome='no_result'; assert.equal(filteredRuns()[0].id, 'pending');
for (const uri of ['javascript:alert(1)', 'data:text/html,test', '//evil.test/x', 'file:///C:/test', 'C:\\secret', 'https://user:pass@example.org', '\njava\tscript:alert(1)']) assert.equal(safeHref(uri), null, uri);
assert.equal(safeHref('mechanisms/a 1.md'), '../Architecture%20Map/mechanisms/a%201.md');
assert.equal(safeHref('https://example.org/paper'), 'https://example.org/paper');
'''
        process = subprocess.run([shutil.which("node"), "-"], input=harness + javascript + assertions + "\n})();",
                                 encoding="utf-8", capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == "__main__":
    unittest.main()
