"""Compact playback regression fixtures are synthetic and never map records."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from evidence_adapter import read_run


def event(number, kind, timestamp, payload, parents=None):
    return {"schema_version":"robot-evidence-1.0","run_id":"test-only-run","event_id":number,
            "event_type":kind,"source":"test-only-fixture","sim_time_s":timestamp,
            "sim_tick":round(timestamp/.002),"wall_elapsed_s":timestamp,
            "parent_ids":parents or [],"payload":payload,
            "payload_sha256":hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()}


def clock_start(number=2, sim=.5, wall=.00001):
    record=event(number,"episode_clock_started",sim,{"monotonic_s":100.,"base_sim_time_s":sim})
    record.update(source="supervisor",wall_elapsed_s=wall)
    return record


class EvidenceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="test-only-evidence-")
        self.root=Path(self.temp.name)/"run";self.root.mkdir()
        self.output=self.root.parent/"view"/"index.html"
        (self.root/"manifest.json").write_text(json.dumps({"run_id":"test-only-run","stage":"development","scope":"Synthetic test fixture only"}),encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def write_events(self,records):
        (self.root/"events.jsonl").write_text("".join(json.dumps(record)+"\n" for record in records),encoding="utf-8")

    def test_sampling_preserves_parent_linked_capture_and_real_zero(self):
        observations=[event(i+1,"observation",i*.1,{"packet":{"sequence":i},"rgb":"missing.png","depth":"missing.npz"}) for i in range(10)]
        dispatched=event(11,"candidate_input",1.,{"message":{"type":"step","packet":{"sequence":1}}},[2])
        self.write_events(observations+[dispatched])
        samples=[{"sim_time_s":i*.01,"q":[0]*7,"dq":[0]*7,"effort":[0]*7,"target":[0]*7,"tcp":[0,0,0],"contact_peak_N":0} for i in range(101)]
        (self.root/"motion.jsonl").write_text("".join(json.dumps(x)+"\n" for x in samples),encoding="utf-8")
        result=read_run(self.root,self.output)
        self.assertEqual(result["sampling"]["event_records"],11)
        self.assertLess(result["sampling"]["retained_events"],11)
        self.assertIn(2,[e["event_id"] for e in result["events"]])
        self.assertEqual(result["motion"][-1]["sim_time_s"],1.)
        self.assertEqual(result["motion"][0]["contact_peak_N"],0)
        self.assertEqual(result["sampling"]["motion_records"],101)
        self.assertEqual(result["sampling"]["retained_motion"],6)
        self.assertIsNone(result["result"])

    def test_missing_frame_is_explicit_and_no_placeholder_created(self):
        self.write_events([event(1,"observation",0,{"packet":{},"rgb":"frames/not-there.png","depth":"frames/not-there.npz"})])
        result=read_run(self.root,self.output)
        self.assertEqual(result["events"][0]["artifact_refs"]["rgb"]["state"],"missing")
        self.assertIsNone(result["events"][0]["artifact_refs"]["rgb"]["href"])
        self.assertFalse((self.root/"frames").exists())

    def test_event_gaps_are_retained_as_missingness(self):
        self.write_events([event(1,"initial_world",0,{}),event(4,"final_world",1,{})])
        result=read_run(self.root,self.output)
        self.assertEqual(result["sampling"]["event_gaps"],[{"after_event_id":1,"before_event_id":4,"missing_count":2}])

    def test_payload_tampering_is_rejected(self):
        record=event(1,"initial_world",0,{"value":1})
        record["payload"]["value"]=2
        self.write_events([record])
        with self.assertRaisesRegex(ValueError,"hash mismatch"):
            read_run(self.root,self.output)

    def test_artifact_path_escape_is_rejected(self):
        self.write_events([event(1,"observation",0,{"packet":{},"rgb":"../outside.png","depth":None})])
        with self.assertRaisesRegex(ValueError,"escapes"):
            read_run(self.root,self.output)

    def test_original_artifact_reference_includes_checked_bytes(self):
        frame=self.root/"frame with space.png";frame.write_bytes(b"synthetic test bytes, not a sensor image")
        self.write_events([event(1,"observation",0,{"packet":{},"rgb":frame.name,"depth":None})])
        result=read_run(self.root,self.output)
        ref=result["events"][0]["artifact_refs"]["rgb"]
        self.assertEqual(ref["state"],"available")
        self.assertIn("frame%20with%20space.png",ref["href"])
        self.assertEqual(ref["sha256"],hashlib.sha256(frame.read_bytes()).hexdigest())

    def test_explicit_wall_epoch_keeps_original_order_clocks_and_payload_hashes(self):
        before=event(1,"initial_world_validation",.5,{"valid":True})
        before["wall_elapsed_s"]=2.13
        boundary=clock_start()
        after=event(3,"initial_world",.5,{})
        after["wall_elapsed_s"]=.0005
        original=[before,boundary,after]
        self.write_events(original)
        source=(self.root/"events.jsonl").read_bytes()
        result=read_run(self.root,self.output)
        self.assertEqual([e["event_id"] for e in result["events"]],[1,2,3])
        self.assertEqual([e["wall_elapsed_s"] for e in result["events"]],[2.13,.00001,.0005])
        self.assertEqual([e["wall_clock_scope"] for e in result["events"]],["initialization","task","task"])
        for expected,actual in zip(original,result["events"]):
            self.assertEqual({key:actual[key] for key in expected},expected)
        self.assertEqual(result["sampling"]["episode_clock_started_event_id"],2)
        self.assertEqual([e["scope"] for e in result["sampling"]["wall_clock_epochs"]],["initialization","task"])
        self.assertEqual((self.root/"events.jsonl").read_bytes(),source)

    def test_legacy_clock_is_unclassified_without_inventing_an_epoch(self):
        self.write_events([event(1,"initial_world",.5,{}),event(2,"final_world",1,{})])
        result=read_run(self.root,self.output)
        self.assertTrue(all(e["wall_clock_scope"]=="unclassified" for e in result["events"]))
        self.assertIsNone(result["sampling"]["episode_clock_started_event_id"])

    def test_arbitrary_wall_reversals_are_rejected_in_either_epoch(self):
        for records in ([event(1,"initial_world",1,{}),event(2,"world_snapshot",.5,{})],
                        [clock_start(1),event(2,"world_snapshot",.6,{})]):
            records[-1]["wall_elapsed_s"]=0
            with self.subTest(records=records):
                self.write_events(records)
                with self.assertRaisesRegex(ValueError,"clocks move backwards"):
                    read_run(self.root,self.output)

    def test_clock_boundary_does_not_permit_simulation_reset(self):
        self.write_events([event(1,"initial_world_validation",1,{}),clock_start()])
        with self.assertRaisesRegex(ValueError,"clocks move backwards"):
            read_run(self.root,self.output)

    def test_second_origin_is_rejected_even_without_a_reversal(self):
        self.write_events([clock_start(1),clock_start(2,sim=.6,wall=.1)])
        with self.assertRaisesRegex(ValueError,"Multiple episode clock origins"):
            read_run(self.root,self.output)

    def test_candidate_or_incomplete_origin_does_not_authorize_reset(self):
        candidate=clock_start();candidate["source"]="candidate"
        incomplete=event(2,"episode_clock_started",.5,{})
        incomplete["source"]="supervisor"
        mismatch=clock_start();mismatch["sim_time_s"]=.6
        for bad in (candidate,incomplete,mismatch):
            with self.subTest(record=bad):
                self.write_events([event(1,"initial_world_validation",.5,{}),bad])
                with self.assertRaises(ValueError):
                    read_run(self.root,self.output)

    def test_protected_scenario_record_list_is_retained_without_flattening(self):
        records=[{"event_id":"late-A","trigger":"deadline"},{"event_id":"rework","trigger":"inspection"}]
        exposure=event(1,"scenario_exposure",420.5,records)
        exposure["source"]="evaluator"
        self.write_events([exposure])
        result=read_run(self.root,self.output)
        self.assertEqual(result["events"][0]["payload"],records)
        self.assertEqual(result["events"][0]["payload_sha256"],exposure["payload_sha256"])
        self.assertEqual(result["sampling"]["event_type_counts"],{"scenario_exposure":1})

    def test_undeclared_lists_and_malformed_scenario_records_are_rejected(self):
        for kind,source,payload in (("candidate_reply","candidate",[{}]),
                                    ("scenario_exposure","candidate",[{}]),
                                    ("scenario_exposure","evaluator",[]),
                                    ("scenario_exposure","evaluator",[None]),
                                    ("scenario_exposure","evaluator",[{},1]),
                                    ("scenario_exposure","evaluator",None)):
            with self.subTest(kind=kind,source=source,payload=payload):
                record=event(1,kind,0,payload);record["source"]=source
                self.write_events([record])
                with self.assertRaisesRegex(ValueError,"Unsupported event payload"):
                    read_run(self.root,self.output)

    def test_scenario_list_payload_hash_is_still_verified(self):
        record=event(1,"scenario_exposure",0,[{"event_id":"late-A"}])
        record["source"]="evaluator";record["payload"].append({"event_id":"tampered"})
        self.write_events([record])
        with self.assertRaisesRegex(ValueError,"hash mismatch"):
            read_run(self.root,self.output)


if __name__=="__main__":
    unittest.main(verbosity=2)
