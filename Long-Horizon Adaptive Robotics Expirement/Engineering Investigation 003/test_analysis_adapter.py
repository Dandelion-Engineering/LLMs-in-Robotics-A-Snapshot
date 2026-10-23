"""Temporary synthetic fixtures only; no fixture is written to project evidence."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import analysis_adapter as adapter
import build_workspace as builder


def synthetic_report():
    empty = {"paired_table": {"both_success": 0, "left_only": 0, "right_only": 0, "both_failure": 0},
             "paired_run_count": 0, "case_units": 0, "scenario_families": 0,
             "left_success_count": 0, "right_success_count": 0,
             "left_success_rate": None, "right_success_rate": None, "paired_success_difference": None,
             "bootstrap": {"interval": None, "confidence": .95, "cluster_key": "scenario_family_id", "cluster_count": 0,
                           "draws": 0, "seed": 0, "missing_reason": "fewer than two observed clusters"},
             "missing_reason": "no jointly observed valid terminal outcomes"}
    comparisons = []
    for left, right in adapter.CONTRASTS:
        comparisons.append({"name": "/".join(left) + " minus " + "/".join(right),
                            "left": dict(zip(("architecture", "condition"), left)),
                            "right": dict(zip(("architecture", "condition"), right)),
                            **copy.deepcopy(empty), "strata": {"horizon": {"short": copy.deepcopy(empty)}},
                            "paired_rows": [], "unavailable_pairs": [
                                {"case_id": "synthetic-case", "replicate": 1,
                                 "left_run_id": "synthetic-left", "right_run_id": "synthetic-right",
                                 "left_reason": "paired_block_infrastructure_invalid", "right_reason": "unrun"}]})
    return {"schema_version": "robot-evaluation-analysis-1.0", "release_id": "SYNTHETIC-TEST-ONLY",
            "planned_counts": {"runs": 264, "main_runs": 192, "ablation_runs": 72, "case_units": 24,
                               "scenario_families": 20, "paired_blocks": 48},
            "result_records_supplied": 1, "dispositions": {"unrun": 258, "paired_block_infrastructure_invalid": 6},
            "excluded_paired_blocks": [{"paired_block_id": "synthetic-block", "triggering_results": [
                {"run_id": "synthetic-left", "reason": "synthetic infrastructure failure"}]}],
            "entrants": [], "comparisons": comparisons, "time_observations": [], "bootstrap_draws": 100,
            "analysis_seed": 0, "limitations": ["Temporary synthetic test fixture; no measured robot results."]}


class AnalysisAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / "view.html"

    def save(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_absent_analysis_stays_unavailable(self):
        data = adapter.read_analysis(None, self.output)
        self.assertEqual(data["state"], "unavailable")
        self.assertIsNone(data["report"])

    def test_report_denominator_and_every_contrast_are_retained(self):
        report = synthetic_report()
        data = adapter.read_analysis(self.save("analysis.json", report), self.output)
        self.assertEqual(data["report"], report)
        self.assertEqual(len(data["source"]["sha256"]), 64)
        self.assertEqual(sum(data["report"]["dispositions"].values()), 264)
        self.assertEqual(len(data["report"]["comparisons"]), 9)

    def test_inconsistent_denominator_missing_contrast_and_nonfinite_are_rejected(self):
        for change in (lambda r: r["dispositions"].update(unrun=0),
                       lambda r: r["comparisons"].pop(),
                       lambda r: r["comparisons"][0].update(paired_run_count=1),
                       lambda r: r.update(analysis_seed=float("nan"))):
            report = synthetic_report();change(report)
            with self.assertRaises(ValueError):
                adapter.read_analysis(self.save("invalid.json", report), self.output)

    def test_metadata_reads_no_events_motion_or_images_and_preserves_missing_result(self):
        root = self.root / "raw";root.mkdir()
        for identity in ("test-a", "test-b"):
            run = root / identity;run.mkdir()
            (run / "manifest.json").write_text(json.dumps({"run_id": identity, "stage": "development", "architecture": "baseline"}))
            (run / "events.jsonl").write_bytes(b"INTENTIONALLY INVALID TEST DATA: MUST NOT READ")
        (root / "test-a" / "result.json").write_text(json.dumps({"run_id": "test-a", "outcome": "success", "validity": "invalid", "timing": ["bulky fixture"], "actual_host_timing_pass": False}))
        (root / "unfinished-directory").mkdir()
        with patch.object(adapter, "read_object", wraps=adapter.read_object) as read:
            data = adapter.read_run_metadata(root, self.output)
        self.assertEqual({Path(call.args[0]).name for call in read.call_args_list}, {"manifest.json", "result.json"})
        self.assertEqual(len(data["runs"]), 2)
        self.assertEqual(data["runs"][0]["result"]["outcome"], "success")
        self.assertEqual(data["runs"][0]["result"]["validity"], "invalid")
        self.assertNotIn("timing", data["runs"][0]["result"])
        self.assertIsNone(data["runs"][1]["result"])
        self.assertEqual(data["directories_without_manifest"], ["unfinished-directory"])

    def test_trace_limit_and_declaration_are_checked_before_loading(self):
        with self.assertRaisesRegex(ValueError, "capped"):
            adapter.select_traces(None, [self.root / str(i) for i in range(13)])
        selection = {"schema_version": "investigation-trace-selection-1.0", "declared_at": "2026-01-01T00:00:00Z",
                     "selection_basis": "Synthetic test only", "runs": [{"run_id": "test-a", "path": "raw/test-a", "reason": "test"}]}
        directories, record = adapter.select_traces(self.save("selection.json", selection))
        self.assertEqual(directories, [(self.root / "raw/test-a").resolve()])
        self.assertFalse(record["selection_is_statistical_denominator"])
        selection["runs"].append(selection["runs"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            adapter.select_traces(self.save("selection.json", selection))

    def test_release_attempt_evidence_shape_and_missing_outcome_are_supported_without_recursion(self):
        root=self.root/'attempts';root.mkdir()
        for identity,has_result in (("planned-a",True),("planned-b",False)):
            evidence=root/identity/'evidence';evidence.mkdir(parents=True)
            (evidence/'manifest.json').write_text(json.dumps({'run_id':identity,'stage':'evaluation'}))
            if has_result:(evidence/'result.json').write_text(json.dumps({'run_id':identity,'outcome':'failure','validity':'invalid'}))
            (evidence/'events.jsonl').write_bytes(b'NOT READ')
        deeper=root/'ignored'/'arbitrary'/'nested';deeper.mkdir(parents=True)
        (deeper/'manifest.json').write_text(json.dumps({'run_id':'must-not-discover'}))
        data=adapter.read_run_metadata(root,self.output)
        self.assertEqual([r['run_id'] for r in data['runs']],['planned-a','planned-b'])
        self.assertTrue(all(r['directory_shape']=='release attempt/evidence' for r in data['runs']))
        self.assertIsNone(data['runs'][1]['result'])
        self.assertEqual(data['directories_without_manifest'],['ignored'])
        (root/'planned-a'/'manifest.json').write_text(json.dumps({'run_id':'ambiguous'}))
        with self.assertRaisesRegex(ValueError,'Ambiguous'):adapter.read_run_metadata(root,self.output)

    def test_hostile_analysis_stays_data_and_default_build_is_unavailable(self):
        from test_workspace import ScriptCollector, unpack_snapshot
        snapshot = {"records": {"architecture": [], "revision": [], "run": [], "result": [], "note": []}}
        report = synthetic_report();report["release_id"] = '</script><img src=x onerror="boom">'
        snapshot["paired_analysis"] = {"state": "available", "report": report}
        parsed = ScriptCollector();html = builder.render(snapshot);parsed.feed(html)
        self.assertEqual(parsed.tags.count("script"), 2)
        self.assertNotIn("img", parsed.tags)
        self.assertEqual(unpack_snapshot(parsed.data)["paired_analysis"]["report"], report)
        self.assertNotIn("innerHTML", html)

    @unittest.skipUnless(shutil.which("node"), "Node.js needed for small DOM fixture checks")
    def test_display_denominators_unavailable_pairs_censoring_and_missing_success_time(self):
        report = synthetic_report()
        report["time_observations"] = [
            {"run_id": "synthetic-failure", "architecture": "A1", "condition": "persistent", "case_id": "case", "replicate": 1,
             "task_success": False, "completion_time_s": None, "right_censored": True, "observed_censor_time_s": 12.,
             "observed_wall_duration_s": 12., "plot_time_s": 300., "cap_s": 300,
             "plot_basis": "failed_run_at_protocol_cap_not_measured_completion", "time_missing_reason": None},
            {"run_id": "synthetic-success", "architecture": "A2", "condition": "persistent", "case_id": "case", "replicate": 1,
             "task_success": True, "completion_time_s": None, "right_censored": False, "observed_censor_time_s": None,
             "observed_wall_duration_s": 20., "plot_time_s": None, "cap_s": 300,
             "plot_basis": "missing_success_time", "time_missing_reason": "success time was not measured"}]
        source = (builder.HERE / "workspace.html").read_text(encoding="utf-8")
        source = source.split("<script>\n", 1)[1].split("/*__PLAYBACK_CODE__*/", 1)[0]
        source += (builder.HERE / "playback.js").read_text(encoding="utf-8")
        source += (builder.HERE / "analysis.js").read_text(encoding="utf-8")
        snapshot = {"records": {k: [] for k in ("architecture", "revision", "run", "result", "note")},
                    "paired_analysis": {"state": "available", "report": report}, "run_metadata": {"state": "unavailable", "runs": []}}
        raw = {"run_id": "synthetic-history", "outcome": "success", "validity": "invalid", "execution_status": "completed", "independent_outcome": {"accepted_count": 3}, "completion_time_s": 142.9}
        snapshot["records"]["result"] = [
            {"id": "old-result", "run_id": "synthetic-history", "outcome": "success", "validity": "invalid", "supersedes_result_id": None},
            {"id": "corrected-result", "run_id": "synthetic-history", "outcome": "partial", "validity": "invalid", "supersedes_result_id": "old-result",
             "validity_reason": "synthetic strict predicate missing", "details": {"correction": "synthetic historical completion withdrawn"}}]
        snapshot["evidence_runs"] = [{"run_id": "synthetic-history", "manifest": {"architecture": "baseline", "stage": "development"}, "result": raw, "events": []}]
        snapshot["run_metadata"] = {"state": "available", "directories_without_manifest": [], "scope": "synthetic metadata only", "runs": [
            {"run_id": "synthetic-history", "manifest": {"architecture": "baseline", "stage": "development"}, "result": raw}]}
        harness = r'''
Object.defineProperty(globalThis,'crypto',{value:require('node:crypto').webcrypto,writable:true,configurable:true});
const registry=new Map();
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.nodeType=1;this.value='';this.text='';}
 set id(value){this._id=value;registry.set(value,this);} get id(){return this._id;}
 set textContent(value){this.text=String(value);this.children=[];} get textContent(){return this.text+this.children.map(c=>c.textContent).join(' ');}
 append(...children){this.children.push(...children);} replaceChildren(...children){this.text='';this.children=children;}
 setAttribute(){} addEventListener(){} get firstChild(){return this.children[0];}
 querySelector(){return new Element('select');} querySelectorAll(){return [];}
}
const data=new Element('script');data.textContent=SNAPSHOT;
const tabs=new Element('nav'),content=new Element('main');
const document={createElement:tag=>new Element(tag),getElementById:id=>id==='map-data'?data:registry.get(id),querySelector:s=>s==='.tabs'?tabs:content};
const location={hash:''};
'''.replace("SNAPSHOT", json.dumps(json.dumps(builder.pack_snapshot(snapshot))))
        assertions = r'''
const assert=require('node:assert/strict');renderAnalysis();
const text=$('panel-analysis').textContent;
for(const value of ['264','192','72','24','20','48','Six main contrasts','Three persistence contrasts','synthetic-block','synthetic infrastructure failure','1 unavailable planned pairs','12.000 s','300.000 s','right-censored','success time was not measured'])assert.ok(text.includes(value),value);
assert.equal(expectedContrasts.length,9);
assert.equal(timeObservationRow(analysisBundle.report.time_observations[0])[3],'Missing');
assert.equal(timeObservationRow(analysisBundle.report.time_observations[1])[5],'Missing');
assert.ok(text.includes('Current canonical assessment: partial outcome'));
assert.ok(text.includes('Immutable raw outcome claim: success'));
renderPlayback();const timeline=$('panel-playback').textContent;
assert.ok(timeline.includes('Current canonical assessment: partial outcome'));
assert.ok(timeline.includes('synthetic historical completion withdrawn'));
assert.ok(timeline.includes('Immutable raw result.json: completed execution · success outcome'));
assert.ok(timeline.indexOf('Current canonical assessment')<timeline.indexOf('Immutable raw result.json'));
assert.ok(timeline.includes('Historical raw accepted count: 3'));
playbackRuns.push({run_id:'synthetic-missing-slot',manifest:null,result:null,events:[],motion:[],sampling:null,source_files:[],
 selection_entry:{run_id:'synthetic-missing-slot',path:'absent/synthetic',reason:'Fixed synthetic slot'},
 trace_availability:{state:'unavailable',reason_code:'missing_required_files',reason:'Required manifest.json is absent.'}});
playbackState.run='synthetic-missing-slot';playbackState.eventType='';playbackState.index=0;renderPlayback();
const missing=$('panel-playback').textContent;
for(const value of ['synthetic-missing-slot','trace unavailable','Selected trace unavailable','Required manifest.json is absent.','has not been replaced','Fixed synthetic slot'])assert.ok(missing.includes(value),value);
assert.ok(!missing.includes('Select an actual recorded event'));
assert.ok(!missing.includes('Recorded motion sample'));
assert.ok(!missing.includes('Historical raw accepted count: 0'));
assert.ok(!missing.includes('Immutable raw result.json:'));
assert.deepEqual(traceCounts(),{selected:2,available:1,unavailable:1});
renderAnalysis();assert.ok($('panel-analysis').textContent.includes('2 selected trace slots; 1 bundles loaded, 1 unavailable'));
assert.equal(snapshot.trace_selection,undefined); // Rendering never writes a replacement declaration.
playbackRuns[1].manifest={run_id:'synthetic-missing-slot',architecture:'A1',stage:'evaluation'};
playbackRuns[1].result={run_id:'synthetic-missing-slot',outcome:'failure',validity:'invalid',execution_status:'failed'};
renderPlayback();assert.ok($('panel-playback').textContent.includes('failed execution · failure outcome · invalid validity'));
assert.ok($('panel-playback').textContent.includes('Selected trace unavailable'));
analysisBundle.report=null;renderAnalysis();assert.ok($('panel-analysis').textContent.includes('Paired analysis unavailable'));
assert.ok(!$('panel-analysis').textContent.includes('synthetic-failure'));
'''
        process = subprocess.run([shutil.which("node"), "-"], input=harness + source + assertions + "\n})();",
                                 encoding="utf-8", capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == "__main__":
    unittest.main()
