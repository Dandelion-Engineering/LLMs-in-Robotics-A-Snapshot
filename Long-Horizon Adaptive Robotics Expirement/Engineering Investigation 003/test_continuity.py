"""Synthetic counterexamples only. Never run a simulator or read actual traces."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import continuity as c


class Fixture:
    def __init__(self):
        self.manifest = {"run_id": "SYNTHETIC-ONLY", "stage": "development", "scenario": "restart", "condition": "persistent",
                         "part_count": 3, "cap_s": 300., "restart_opportunity": {"enabled": True, "cut": "after_release", "fallback_s": 60.}}
        self.result = {"run_id": self.manifest["run_id"], "outcome": "success", "validity": "unknown", "execution_status": "completed",
                       "wall_duration_s": 50., "independent_outcome": {"success": True}}
        self.events = [];self.t = 0.;self.order = {"version": 1, "requirements": [{"family": "A", "recipe": "A", "count": 2, "tray": "tray1"}]}
        self.add("episode_clock_started", {"base_sim_time_s": 0., "monotonic_s": 900.}, t=0.)

    def add(self, kind, payload, *, source="supervisor", parents=(), t=None):
        self.t = self.t + .1 if t is None else t
        event = {"schema_version": "robot-evidence-1.0", "run_id": self.manifest["run_id"], "event_id": len(self.events) + 1,
                 "event_type": kind, "source": source, "sim_time_s": self.t, "sim_tick": round(self.t / .002),
                 "wall_elapsed_s": self.t, "parent_ids": list(parents), "payload": copy.deepcopy(payload)}
        event["payload_sha256"] = hashlib.sha256(c.canonical(event["payload"])).hexdigest()
        self.events.append(event);return event

    def restart(self, *, ready=True, fallback=False):
        cut = self.add("restart_begin", {"incarnation": 1, "active_request": {"request_id": "interrupted", "part_id": "A1"},
                                       "exposure": {"actual_cut": "deadline_fallback" if fallback else "after_release",
                                                    "fallback_used": fallback, "configured_milestone_exercised": not fallback}}, source="evaluator")
        returned = self.add("restart_ready", {"incarnation": 2, "reply": {}}, parents=[cut["event_id"]]) if ready else None
        return cut, returned

    def step(self, *, incarnation=2, delivered=True, acknowledged=True, capture_time=None, visible=True, report=None):
        packet = {"incarnation": incarnation, "sequence": len(self.events), "order": self.order,
                  "capture_sim_time_s": self.t + .1 if capture_time is None else capture_time,
                  "capture_wall_elapsed_s": self.t + .1 if capture_time is None else capture_time,
                  "detections": [{"id": "A1"}] if visible else []}
        observation = self.add("observation", {"packet": packet}, source="sensor_gateway")
        if not delivered:return packet, observation, None, None
        dispatch = self.add("candidate_input", {"message": {"type": "step", "packet": packet}}, source="candidate_gateway", parents=[observation["event_id"]])
        report = [{"sequence": packet["sequence"], **entry} for entry in (report or [])]
        reply = self.add("candidate_reply", {"type": "step", "supervisor_input_event_id": dispatch["event_id"], "response": None,
                                           "events": report or []}, source="candidate", parents=[dispatch["event_id"]]) if acknowledged else None
        return packet, observation, dispatch, reply

    def world(self, histories=None, inspections=None):
        return self.add("world_snapshot", {"objects": {"A1": {"pos": [.4, 0, .02], "cycle_history": histories or [],
                                                                "inspection_history": inspections or []}}}, source="evaluator")

    def command(self, packet, reply, *, rid="new-cycle", operation="cycle", suppressed=False):
        request = self.add("action_requested", {"request_id": rid, "operation": operation, "part_id": "A1", "recipe": "A",
                                               "incarnation": packet["incarnation"], "observation_sequence": packet["sequence"], "order_version": 1},
                           source="candidate", parents=[reply["event_id"]])
        admission = self.add("action_admission", {"request_id": rid, "status": "accepted", "duplicate_suppressed": suppressed},
                             source="gateway", parents=[request["event_id"]])
        return request, admission

    def processing(self, packet, reply, *, rework=False, before=True):
        prior = {"cycle_id": 1, "part_id": "A1", "recipe": "A", "accepted": True, "completed": True, "accepted_at": 0., "completed_at": .01}
        inspections = [{"inspection_id": "authorized-rework", "status": "rework", "cycle_id": 1, "observed_at": .02}] if rework else []
        if before:self.world([prior] if rework else [], inspections)
        request, admission = self.command(packet, reply)
        start = self.add("physical_service_event", {"type": "feedback", "request_id": "new-cycle", "status": "completed", "reason": "cycle accepted", "cycle_id": 2, "sim_time": self.t + .1}, source="gateway", parents=[admission["event_id"]])
        complete = self.add("physical_service_event", {"type": "cycle_complete", "cycle_id": 2, "sim_time": self.t + .1}, source="gateway", parents=[start["event_id"]])
        history = {"cycle_id": 2, "part_id": "A1", "recipe": "A", "accepted": True, "completed": True,
                   "accepted_at": start["sim_time_s"], "completed_at": complete["sim_time_s"]}
        if rework:history["rework_authorization_inspection_id"] = "authorized-rework"
        snapshot = self.world(([prior] if rework else []) + [history], inspections)
        return request, admission, start, complete, snapshot

    def run(self, annotations=()):
        return c.extract(self.manifest, self.result, self.events, annotations=annotations, rubric_sha256="synthetic-rubric-hash")


def annotation(label, refs, *, verdict="established", bounds=None, suffix="1"):
    row = {"annotation_id": "synthetic-" + label + suffix, "opportunity_id": "restart-1", "label": label, "verdict": verdict,
           "reviewer": "synthetic test only", "rule": "b01-continuity-rubric-1/test", "basis": "Temporary explicit counterexample predicate",
           "evidence_event_ids": [e["event_id"] for e in refs]}
    if bounds:row["time_event_ids"] = [e["event_id"] for e in bounds]
    return row


class ContinuityCounterexamples(unittest.TestCase):
    def test_capture_without_delivery_and_dispatch_without_acknowledgment_do_not_qualify(self):
        for delivered in (False, True):
            f=Fixture();f.restart();f.step(delivered=delivered, acknowledged=False)
            row=f.run()["rows"][0]
            self.assertEqual(row["landmarks"]["first_fresh_delivery"]["state"], "unknown")
            self.assertEqual(row["landmarks"]["first_fresh_dispatch"]["state"], "established" if delivered else "unknown")

    def test_stale_capture_and_occluded_relevant_part_stay_distinct(self):
        f=Fixture();cut,_=f.restart();f.step(capture_time=0.)
        self.assertEqual(f.run()["rows"][0]["landmarks"]["first_fresh_delivery"]["state"], "unknown")
        packet,observation,dispatch,reply=f.step(visible=False)
        row=f.run()["rows"][0]
        self.assertEqual(row["landmarks"]["first_fresh_delivery"]["state"], "established")
        self.assertEqual(row["landmarks"]["first_relevant_visible_delivery"]["state"], "unknown")
        self.assertEqual(row["landmarks"]["first_fresh_delivery"]["ingestion_wall_bounds_s"], [dispatch["wall_elapsed_s"],reply["wall_elapsed_s"]])

    def test_late_old_incarnation_output_cannot_establish_detection_or_resolution(self):
        f=Fixture();f.restart();f.step(incarnation=1,report=[{"type":"candidate_action_resolution","request_id":"interrupted","operation":"cycle","resolved":True,"sim_time":1.}])
        f.add("late_candidate_reply", {"reply":{"events":[{"type":"candidate_action_resolution","resolved":True}]},"after_episode_end":True},source="candidate_runtime")
        row=f.run()["rows"][0]
        self.assertFalse(row["candidate_resolution_claims"][0]["current_runtime_output"])
        self.assertEqual(row["landmarks"]["correct_reconciliation"]["state"],"unknown")
        self.assertEqual(row["landmarks"]["behavioral_detection"]["state"],"unknown")

    def test_suppressed_duplicate_is_not_executed_duplicate(self):
        f=Fixture();f.restart();packet,_,_,reply=f.step()
        f.command(packet,reply,rid="same");f.command(packet,reply,rid="same",suppressed=True)
        row=f.run()["rows"][0]
        self.assertEqual(sum(r["accepted"] for r in row["command_facts"]),1)
        self.assertEqual(sum(r["duplicate_suppressed"] for r in row["command_facts"]),1)
        self.assertEqual(row["repeated_cycle_admissions"],[])
        self.assertEqual(row["avoidable_duplicate_work"]["state"],"unknown")

    def test_repeated_admission_is_not_duplicate_physical_work(self):
        f=Fixture();f.restart();packet,_,_,reply=f.step();f.command(packet,reply,rid="one");f.command(packet,reply,rid="two")
        row=f.run()["rows"][0]
        self.assertEqual(len(row["repeated_cycle_admissions"]),1)
        self.assertEqual(row["landmarks"]["resumed_useful_work"]["state"],"unknown")

    def test_required_rework_can_be_new_useful_work_without_avoidable_duplication(self):
        f=Fixture();f.restart();packet,_,_,reply=f.step();f.processing(packet,reply,rework=True)
        row=f.run()["rows"][0]
        self.assertTrue(row["landmarks"]["resumed_useful_work"]["authorized_rework"])
        self.assertEqual(row["avoidable_duplicate_work"]["state"],"unknown")

    def test_cut_never_reached_has_no_latency_even_with_final_success(self):
        f=Fixture();f.step(incarnation=1)
        report=f.run();row=report["rows"][0]
        self.assertEqual(report["coverage"]["planned_but_unobserved"],1)
        self.assertEqual(row["recovery"]["state"],"not_exposed")
        self.assertIsNone(row["recovery"]["latency"])

    def test_deadline_fallback_and_milestone_do_not_prove_admissibility(self):
        for fallback in (False,True):
            f=Fixture();f.restart(fallback=fallback);f.step()
            row=f.run()["rows"][0]
            self.assertEqual(row["exposure"]["fallback_used"],fallback)
            self.assertEqual(row["admissibility"]["state"],"unknown")
            self.assertEqual(row["recovery"]["state"],"unknown")

    def test_process_completion_during_absence_is_not_resumed_candidate_work(self):
        f=Fixture();packet,_,_,reply=f.step(incarnation=1);f.world()
        request,admission=f.command(packet,reply)
        start=f.add("physical_service_event",{"type":"feedback","request_id":"new-cycle","status":"completed","reason":"cycle accepted","cycle_id":2,"sim_time":f.t+.1},source="gateway",parents=[admission["event_id"]])
        cut,_=f.restart(ready=False)
        complete=f.add("physical_service_event",{"type":"cycle_complete","cycle_id":2,"sim_time":f.t+.1},source="gateway",parents=[start["event_id"]])
        f.world([{"cycle_id":2,"part_id":"A1","recipe":"A","accepted":True,"completed":True,"accepted_at":start["sim_time_s"],"completed_at":complete["sim_time_s"]}])
        f.add("restart_ready",{"incarnation":2,"reply":{}},parents=[cut["event_id"]]);f.step()
        row=f.run()["rows"][0]
        self.assertTrue(row["autonomous_processing"][0]["completed_during_runtime_absence"])
        self.assertEqual(row["landmarks"]["resumed_useful_work"]["state"],"unknown")

    def test_wrong_candidate_cycle_resolution_is_refuted_by_protected_fault(self):
        f=Fixture();f.restart();packet,_,_,reply=f.step();request,admission=f.command(packet,reply,rid="interrupted")
        start=f.add("physical_service_event",{"type":"feedback","request_id":"interrupted","status":"completed","reason":"cycle accepted","cycle_id":3,"sim_time":f.t+.1},source="gateway",parents=[admission["event_id"]])
        fault=f.add("physical_service_event",{"type":"cycle_fault","cycle_id":3,"sim_time":f.t+.1},source="gateway",parents=[start["event_id"]])
        f.step(report=[{"type":"candidate_action_resolution","request_id":"interrupted","operation":"cycle","resolved":True,"sim_time":fault["sim_time_s"]}])
        row=f.run()["rows"][0]
        self.assertEqual(row["candidate_resolution_claims"][0]["correctness"],"incorrect")
        self.assertEqual(row["landmarks"]["correct_reconciliation"]["state"],"unknown")

    def test_useful_progress_without_explicit_recognition_does_not_invent_detection(self):
        f=Fixture();f.restart();packet,_,_,reply=f.step();_,_,_,complete,_=f.processing(packet,reply)
        row=f.run()["rows"][0]
        self.assertEqual(row["landmarks"]["resumed_useful_work"]["state"],"established")
        self.assertEqual(row["landmarks"]["resumed_useful_work"]["sim_bounds_s"],[complete["sim_time_s"]]*2)
        self.assertEqual(row["landmarks"]["behavioral_detection"]["state"],"unknown")
        self.assertEqual(row["recognition_mechanism"]["state"],"unknown")
        self.assertEqual(row["recovery"]["state"],"unknown")

    def test_safe_hold_and_trajectory_completion_are_not_useful_resumption(self):
        f=Fixture();f.restart();packet,_,_,reply=f.step();request,admission=f.command(packet,reply,operation="observe")
        f.add("physical_service_event",{"type":"trajectory_complete","request_id":"new-cycle","sim_time":f.t+.1},source="gateway",parents=[admission["event_id"]]);f.world()
        row=f.run()["rows"][0]
        self.assertEqual(row["landmarks"]["resumed_useful_work"]["state"],"unknown")
        self.assertEqual(row["landmarks"]["restored_validity"]["state"],"unknown")

    def test_snapshot_bounded_correction_retains_bounds_and_unknown_detection_relative_time(self):
        f=Fixture();cut,_=f.restart();packet,_,_,reply=f.step();lower=f.world();_,_,_,complete,upper=f.processing(packet,reply)
        annotations=[annotation("admissibility",[cut]),annotation("restored_validity",[lower,upper],bounds=[lower,upper])]
        row=f.run(annotations)["rows"][0]
        self.assertEqual(row["landmarks"]["restored_validity"]["sim_bounds_s"],[lower["sim_time_s"],upper["sim_time_s"]])
        self.assertEqual(row["recovery"]["sim_bounds_s"],[complete["sim_time_s"],upper["sim_time_s"]])
        self.assertIsNone(row["recovery"]["from_detection_sim_bounds_s"])
        self.assertIsNone(row["recovery"]["physical_wall_latency_s"])

    def test_conflicting_annotations_remain_unknown_and_both_survive(self):
        f=Fixture();cut,_=f.restart()
        a=annotation("admissibility",[cut]);b=annotation("admissibility",[cut],verdict="inadmissible",suffix="2")
        row=f.run([a,b])["rows"][0]
        self.assertEqual(row["admissibility"]["state"],"unknown");self.assertEqual(len(row["operator_annotations"]),2)

    def test_optional_full_snapshot_is_preserved_without_admissibility_inference(self):
        f=Fixture();cut,_=f.restart();cut["payload"]["protected_snapshot"]={"objects":[{"id":"A1","bounds":{"min":[0,0,0],"max":[1,1,1]}}]}
        cut["payload_sha256"]=hashlib.sha256(c.canonical(cut["payload"])).hexdigest()
        row=f.run()["rows"][0]
        self.assertTrue(row["protected_exposure_snapshot"]["available"])
        self.assertEqual(row["admissibility"]["state"],"unknown")

    def test_corrupt_hash_gap_or_parent_is_an_integrity_failure_not_reconstructed(self):
        for mutation in (lambda f:f.events[-1].update(payload_sha256="0"*64),lambda f:f.events[-1].update(event_id=9),lambda f:f.events[-1].update(parent_ids=[999])):
            f=Fixture();f.restart();mutation(f)
            with self.assertRaises(ValueError):f.run()

    def test_operator_output_cannot_overwrite_sources_or_candidate_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);episode=root/"run";episode.mkdir()
            for path in (episode/"derived.json",root/"candidate_state"/"derived.json"):
                with self.assertRaises(ValueError):c.write_report({"sources":{}},path,episode)

    def test_order_delivery_is_separate_from_new_visual_acquisition(self):
        f=Fixture();f.manifest.update(scenario="order_change",restart_opportunity={"enabled":False})
        f.add("scenario_configuration",{"private_parameters":{"required_order_events":["reroute-B"],"reroute_time_s":40.}},source="evaluator")
        f.step(incarnation=1)
        f.order={**f.order,"version":2}
        event=f.add("order_amendment",{"event_id":"order-event-reroute-B","parent_order_version":1,"order_version":2,"order":f.order},source="public_order_service")
        f.add("scenario_exposure",[{"event_id":"order-event-reroute-B","order_version":2,"trigger":"fixed_elapsed_order_change","fallback_used":False}],source="evaluator")
        f.step(incarnation=1,capture_time=0.)
        row=f.run()["rows"][0]
        self.assertEqual(row["exposure"]["state"],"exercised")
        self.assertEqual(row["landmarks"]["public_order_delivery"]["state"],"established")
        self.assertEqual(row["landmarks"]["first_fresh_delivery"]["state"],"unknown")
        f.step(incarnation=1)
        self.assertEqual(f.run()["rows"][0]["landmarks"]["first_fresh_delivery"]["state"],"established")

    def test_uncorrelated_order_exposure_is_missing_evidence_not_an_exercised_denominator(self):
        f=Fixture();f.manifest.update(scenario="order_change",restart_opportunity={"enabled":False})
        f.add("order_amendment",{"event_id":"order-event-reroute-B","parent_order_version":1,"order_version":2,"order":{**f.order,"version":2}},source="public_order_service")
        report=f.run()
        self.assertEqual(report["coverage"]["missing_exposure_correlation"],1)
        self.assertEqual(report["coverage"]["exercised"],0)

    def test_directory_extraction_hashes_sources_and_writes_immutable_operator_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);episode=root/"run";episode.mkdir();f=Fixture();f.restart();f.step()
            (episode/"manifest.json").write_text(json.dumps(f.manifest),encoding="utf-8")
            (episode/"result.json").write_text(json.dumps(f.result),encoding="utf-8")
            (episode/"events.jsonl").write_text(''.join(json.dumps(e)+'\n' for e in f.events),encoding="utf-8")
            (episode/"motion.jsonl").write_bytes(b'SYNTHETIC UNPARSED MOTION BYTES\n')
            report=c.extract_directory(episode)
            self.assertEqual(len(report["sources"]["events.jsonl"]["sha256"]),64)
            self.assertEqual(report["rows"][0]["source_sha256"]["motion.jsonl"],hashlib.sha256((episode/"motion.jsonl").read_bytes()).hexdigest())
            output=root/"annotations"/"derived.json";c.write_report(report,output,episode)
            with self.assertRaises(FileExistsError):c.write_report(report,output,episode)
            (episode/"result.json").write_text('{}',encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Input changed"):c.write_report(report,root/"another.json",episode)

    def test_explicit_episode_origin_reset_is_allowed_but_unexplained_regression_is_not(self):
        f=Fixture();f.restart()
        initialization={**f.events[0],"event_type":"candidate_ready","source":"candidate_runtime","wall_elapsed_s":8.,"sim_time_s":0.,"payload":{}}
        initialization["payload_sha256"]=hashlib.sha256(c.canonical({})).hexdigest()
        events=[initialization]+copy.deepcopy(f.events)
        for i,e in enumerate(events,1):
            e["event_id"]=i;e["parent_ids"]=[p+1 for p in e["parent_ids"]]
        report=c.extract(f.manifest,f.result,events)
        self.assertEqual(report["rows"][0]["landmarks"]["runtime_return"]["state"],"established")
        events[-1]["wall_elapsed_s"]=-1.
        with self.assertRaisesRegex(ValueError,"regressed"):c.extract(f.manifest,f.result,events)


if __name__ == "__main__":
    unittest.main()
