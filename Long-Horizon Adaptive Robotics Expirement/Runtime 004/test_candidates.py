"""Synthetic packet/unit checks. These are NOT robot experiments or model runs.

PacketFixture applies symbolic state changes only to test candidate bookkeeping.
It is deliberately kept out of production imports, run records and results.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from candidates import Candidate, StateCorruptionError


class PacketFixture:
    """Hand-authored public input fixture; no physical simulation is claimed."""

    def __init__(self, count=3, two_families=False, rework=False):
        self.packet = {
            "run_id": "unit-only", "incarnation": "inc1", "sequence": 0, "sim_time": 0.0,
            "order": {"version": 1, "closed": True, "requirements": []},
            "detections": [],
            "station": {"busy": False, "ready": True, "fault": False, "cycle_id": 0,
                        "completed_cycle_id": 0, "fixture_insert": "A", "occupied_visible_id": None},
            "gripper": {"holding_visible_id": None, "width": 0.08},
            "inspection": None, "last_feedback": None,
        }
        n_a = (count + 1) // 2 if two_families else count
        n_b = count - n_a
        for family, number, tray in (("A", n_a, "tray1"), ("B", n_b, "tray2")):
            if number:
                self.packet["order"]["requirements"].append({"family": family, "recipe": "recipe" + family,
                                                             "count": number, "tray": tray})
            for n in range(number):
                self.packet["detections"].append({"id": family + str(n), "family": family, "pos": [0.1 + n * 0.1, 0.2, 0.03],
                                                  "zone": "raw", "visible_mark": "raw", "age_s": 0.0})
        self.inspection_count = 0
        self.rework = rework
        self.reworked = False

    def next(self, seconds=1.0):
        self.packet["sequence"] += 1
        self.packet["sim_time"] += seconds
        return copy.deepcopy(self.packet)

    def detection(self, part_id):
        return next(d for d in self.packet["detections"] if d["id"] == part_id)

    def apply_symbolic(self, action):
        """Expected public response fixture, not an executor implementation."""
        op = action["operation"]
        feedback = {"request_id": action["request_id"], "status": "completed"}
        if op == "transport":
            item = self.detection(action["part_id"])
            old = item["zone"]
            item["zone"] = action["destination"]
            if old == "fixture":
                self.packet["station"]["occupied_visible_id"] = None
            if item["zone"] == "fixture":
                self.packet["station"]["occupied_visible_id"] = item["id"]
        elif op == "setup":
            self.packet["station"]["fixture_insert"] = action["family"]
        elif op == "cycle":
            self.packet["station"]["cycle_id"] += 1
            self.packet["station"]["completed_cycle_id"] = self.packet["station"]["cycle_id"]
            self.detection(action["part_id"])["visible_mark"] = "processed"
            feedback["cycle_id"] = self.packet["station"]["cycle_id"]
        elif op == "inspect":
            self.inspection_count += 1
            status = "pass"
            if self.rework and not self.reworked:
                status, self.reworked = "rework", True
            self.packet["inspection"] = {"part_id": action["part_id"], "status": status,
                                         "inspection_id": self.inspection_count}
        self.packet["last_feedback"] = feedback
        return feedback


class CandidateUnitChecks(unittest.TestCase):
    def test_restart_held_recovery_is_shared_and_does_not_infer_identity(self):
        for kind in ('baseline','A1','A2','A3'):
            fixture=PacketFixture(count=3)
            fixture.packet.update(restart_generation=1,incarnation='after-crash')
            fixture.packet['gripper']['width']=.042
            candidate=self.new(kind,name='held-'+kind)
            reply=candidate.step(fixture.next())
            self.assertEqual(reply['action']['operation'],'recover_held')
            self.assertNotIn('part_id',reply['action'])
            self.assertEqual(candidate.step(fixture.next())['type'],'wait')
            candidate.accept_feedback({'request_id':reply['action']['request_id'],'status':'completed'})
            fixture.packet['gripper']['width']=.08
            candidate.step(fixture.next())
            self.assertIsNone(candidate.state['recovery_pending'])
            self.assertTrue(all(p['cycle'] is None for p in candidate.state['parts'].values()))

    def test_public_action_menu_keeps_choices_and_excludes_visible_noops(self):
        fixture=PacketFixture(count=3)
        candidate=self.new('A1')
        candidate._ingest(fixture.next())
        menu=candidate._admissible_actions()
        self.assertTrue(all(candidate._validate(action) is None for action in menu))
        loads=[a for a in menu if a['operation']=='transport' and a['destination']=='fixture']
        self.assertEqual({a['part_id'] for a in loads},{'A0','A1','A2'})
        fixture.detection('A0')['zone']='fixture'
        fixture.packet['station']['occupied_visible_id']='A0'
        candidate._ingest(fixture.next())
        menu=candidate._admissible_actions()
        self.assertNotIn({'operation':'transport','part_id':'A0','destination':'fixture'},menu)
        self.assertIn({'operation':'cycle','part_id':'A0','recipe':'recipeA'},menu)
        self.assertIn({'operation':'transport','part_id':'A0','destination':'parking1'},menu)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def new(self, kind="baseline", name="candidate", persistent=True):
        return Candidate(kind, self.root / name, persistent)

    def run_symbolic_baseline(self, count, two_families=False, rework=False):
        fixture, candidate = PacketFixture(count, two_families, rework), self.new(name="baseline" + str(count))
        actions = []
        for _ in range(160):
            result = candidate.step(fixture.next())
            self.assertNotEqual(result["type"], "model")
            if result["type"] != "action":
                continue
            action = result["action"]
            actions.append(action)
            self.assertNotEqual(action["operation"], "help", action)
            if action["operation"] == "done":
                return candidate, fixture, actions
            candidate.accept_feedback(fixture.apply_symbolic(action))
        self.fail("synthetic bookkeeping fixture did not finish")

    def test_baseline_synthetic_3_6_9_part_packet_sequences(self):
        for count in (3, 6, 9):
            with self.subTest(count=count):
                candidate, _, actions = self.run_symbolic_baseline(count, two_families=count > 3)
                self.assertEqual(sum(a["operation"] == "cycle" for a in actions), count)
                self.assertEqual(sum(a["operation"] == "inspect" for a in actions), count)
                self.assertTrue(all(p["inspection"]["status"] == "pass" for p in candidate.state["parts"].values()))

    def test_baseline_one_rework_preserves_cycle_inspection_correlation(self):
        candidate, _, actions = self.run_symbolic_baseline(3, rework=True)
        self.assertEqual(sum(a["operation"] == "cycle" for a in actions), 4)
        self.assertEqual(sum(p["reworks"] for p in candidate.state["parts"].values()), 1)

    def test_restart_view_retreat_preserves_unknown_transport_and_is_once(self):
        fixture,candidate=PacketFixture(1),self.new()
        original=candidate.step(fixture.next())["action"]
        fixture.packet.update(incarnation="inc2",restart_generation=1,detections=[])
        view=candidate.step(fixture.next())["action"]
        self.assertEqual(view["operation"],"observe")
        self.assertTrue(view["clear_view"])
        self.assertEqual(candidate.state["pending"]["action"]["request_id"],original["request_id"])
        again=candidate.step(fixture.next())
        self.assertFalse((again.get("action") or {}).get("clear_view",False))

    def test_restart_view_cannot_open_a_held_part(self):
        fixture,candidate=PacketFixture(1),self.new()
        fixture.packet.update(incarnation="inc2",restart_generation=1)
        fixture.packet["gripper"]={"holding_visible_id":"A0","width":.03}
        proposal=candidate.step(fixture.next())
        self.assertFalse((proposal.get("action") or {}).get("clear_view",False))
        self.assertIsNotNone(candidate._validate({"operation":"observe","clear_view":True}))

    def test_transport_feedback_is_not_physical_success(self):
        fixture, candidate = PacketFixture(1), self.new()
        action = candidate.step(fixture.next())["action"]
        candidate.accept_feedback({"request_id": action["request_id"], "status": "completed"})
        self.assertIsNotNone(candidate.state["pending"])
        self.assertFalse(candidate._proof("A0"))
        self.assertEqual(candidate.step(fixture.next())["type"], "wait")
        self.assertIsNotNone(candidate.state["pending"])

    def test_closed_gripper_prevents_place_verification(self):
        fixture, candidate = PacketFixture(1), self.new()
        action = candidate.step(fixture.next())["action"]
        candidate.accept_feedback(fixture.apply_symbolic(action))
        fixture.packet["gripper"]["width"] = 0.04
        self.assertEqual(candidate.step(fixture.next())["type"], "wait")
        self.assertIsNotNone(candidate.state["pending"])

    def test_intent_is_durable_before_action_return(self):
        fixture, candidate = PacketFixture(1), self.new()
        action = candidate.step(fixture.next())["action"]
        envelope = json.loads(candidate.state_path.read_text(encoding="utf-8"))
        self.assertEqual(envelope["state"]["pending"]["action"]["request_id"], action["request_id"])
        events = candidate.drain_events()
        self.assertTrue(any(e["type"] == "context_write" and action["request_id"] in e["content_utf8"] for e in events))
        self.assertEqual(candidate.drain_events(), [])

    def test_restart_after_release_does_not_duplicate_transport(self):
        fixture, candidate = PacketFixture(1), self.new()
        action = candidate.step(fixture.next())["action"]
        fixture.apply_symbolic(action)  # acknowledgement deliberately withheld
        fixture.packet["last_feedback"] = None
        fixture.packet["incarnation"] = "inc2"
        restarted = self.new()
        result = restarted.step(fixture.next(seconds=5))
        self.assertEqual(result["type"], "action")
        self.assertEqual(result["action"]["operation"], "cycle")
        self.assertNotEqual(result["action"]["request_id"], action["request_id"])

    def test_restart_moved_part_resolves_current_state_without_replay(self):
        fixture, candidate = PacketFixture(1), self.new()
        action = candidate.step(fixture.next())["action"]
        fixture.detection("A0")["zone"] = "parking1"
        fixture.packet["incarnation"] = "inc2"
        restarted = self.new()
        restarted.step(fixture.next(seconds=5))
        restarted.step(fixture.next())
        result = restarted.step(fixture.next())
        self.assertEqual(result["type"], "action")
        self.assertNotEqual(result["action"]["request_id"], action["request_id"])
        self.assertEqual(result["action"]["part_id"], "A0")
        events = restarted.drain_events()
        self.assertTrue(any(e["type"] == "candidate_action_resolution" and not e["resolved"] for e in events))

    def test_cycle_acceptance_needs_public_completion(self):
        fixture, candidate = PacketFixture(1), self.new()
        load = candidate.step(fixture.next())["action"]
        candidate.accept_feedback(fixture.apply_symbolic(load))
        cycle = candidate.step(fixture.next())["action"]
        candidate.accept_feedback({"request_id": cycle["request_id"], "status": "accepted", "cycle_id": 7})
        fixture.packet["station"].update({"busy": True, "cycle_id": 7})
        fixture.packet["last_feedback"] = None
        self.assertEqual(candidate.step(fixture.next())["type"], "wait")
        self.assertIsNone(candidate.state["parts"]["A0"]["cycle"])
        fixture.packet["station"].update({"busy": False, "completed_cycle_id": 7})
        fixture.detection("A0")["visible_mark"] = "processed"
        result = candidate.step(fixture.next())
        self.assertEqual(result["action"]["destination"], "inspection")
        self.assertTrue(candidate.state["parts"]["A0"]["cycle"]["complete"])

    def test_processed_mark_and_pass_do_not_invent_lost_recipe_history(self):
        fixture, candidate = PacketFixture(1), self.new(persistent=False)
        fixture.detection("A0").update({"zone": "inspection", "visible_mark": "processed"})
        fixture.packet["inspection"] = {"part_id": "A0", "status": "pass", "inspection_id": 4}
        result = candidate.step(fixture.next())
        self.assertEqual(result["action"]["operation"], "help")
        self.assertIsNone(candidate.state["parts"]["A0"]["cycle"])

    def test_public_invariant_and_new_inspection_restore_eligibility_not_history(self):
        fixture, candidate = PacketFixture(1), self.new(persistent=False)
        fixture.packet["process_contract"] = {"family_recipes": {"A": "recipeA", "B": "recipeB"},
                                                "processed_mark_requires_eligible_cycle": True}
        fixture.detection("A0").update({"zone": "inspection", "visible_mark": "processed"})
        fixture.packet["inspection"] = {"part_id": "A0", "status": "pass", "inspection_id": "old"}
        result = candidate.step(fixture.next())
        self.assertEqual(result["action"]["operation"], "inspect")
        self.assertFalse(candidate._proof("A0"))
        candidate.accept_feedback(fixture.apply_symbolic(result["action"]))
        result = candidate.step(fixture.next())
        self.assertEqual(result["action"]["destination"], "tray1")
        part = candidate.state["parts"]["A0"]
        self.assertIsNone(part["cycle"])
        self.assertIsNone(part["eligibility_inference"]["historical_cycle_id"])
        self.assertTrue(candidate._proof("A0"))

    def test_no_persistence_reconstructs_partly_completed_job_with_public_invariant(self):
        fixture, candidate = PacketFixture(3, two_families=True), self.new(name="before-restart", persistent=False)
        fixture.packet["process_contract"] = {"family_recipes": {"A": "recipeA", "B": "recipeB"},
                                                "processed_mark_requires_eligible_cycle": True}
        restarted = False
        operations = []
        for _ in range(100):
            result = candidate.step(fixture.next())
            if result["type"] != "action":
                continue
            action = result["action"]
            operations.append(action["operation"])
            self.assertNotEqual(action["operation"], "help", action)
            if action["operation"] == "done":
                self.assertTrue(restarted)
                self.assertEqual(operations.count("cycle"), 3)  # No duplicate processing.
                self.assertGreater(operations.count("inspect"), 3)  # Legitimate reconstruction overhead.
                return
            candidate.accept_feedback(fixture.apply_symbolic(action))
            if not restarted and sum(d["zone"].startswith("tray") for d in fixture.packet["detections"]) == 1:
                # An empty new directory models supervisor erasure. The old
                # checkpoint remains in this test's temp folder for inspection.
                candidate = self.new(name="after-empty-restart", persistent=False)
                fixture.packet["incarnation"] = "inc2"
                restarted = True
        self.fail("public-only post-restart bookkeeping did not finish")

    def test_process_invariant_cannot_be_inferred_from_current_order(self):
        fixture, candidate = PacketFixture(1), self.new(persistent=False)
        fixture.packet["process_contract"] = {"family_recipes": {"A": "otherRecipe"},
                                                "processed_mark_requires_eligible_cycle": True}
        fixture.detection("A0").update({"zone": "inspection", "visible_mark": "processed"})
        request = candidate.step(fixture.next())
        candidate.accept_feedback(fixture.apply_symbolic(request["action"]))
        result = candidate.step(fixture.next())
        self.assertNotEqual(result["action"].get("destination"), "tray1")
        self.assertEqual(candidate._recipe("A0"), "otherRecipe")

    def test_insert_tags_are_not_workpieces_or_fixture_obstructions(self):
        fixture, candidate = PacketFixture(1), self.new()
        fixture.packet["detections"].append({"id": "insert_A", "kind": "insert", "family": "A", "pos": [.5, 0., .01],
                                                "zone": "fixture", "age_s": 0., "visible_mark": "raw"})
        result = candidate.step(fixture.next())
        self.assertEqual(result["action"]["operation"], "transport")
        self.assertEqual(result["action"]["part_id"], "A0")
        self.assertNotIn("insert_A", candidate.state["parts"])

    def test_loaded_part_can_occlude_previously_observed_insert(self):
        fixture, candidate = PacketFixture(1), self.new()
        load = candidate.step(fixture.next())["action"]
        candidate.accept_feedback(fixture.apply_symbolic(load))
        fixture.packet["station"]["fixture_insert"] = None
        result = candidate.step(fixture.next())
        self.assertEqual(result["action"]["operation"], "cycle")
        self.assertEqual(candidate.state["fixture_belief"]["basis"], "public observed insert tag")

    def test_lost_insert_belief_reveals_insert_by_unloading(self):
        fixture, candidate = PacketFixture(1), self.new(persistent=False)
        fixture.detection("A0")["zone"] = "fixture"
        fixture.packet["station"].update({"fixture_insert": None, "occupied_visible_id": "A0"})
        result = candidate.step(fixture.next())
        self.assertEqual(result["action"]["operation"], "transport")
        self.assertEqual(result["action"]["destination"], "parking1")
        self.assertIsNone(candidate.state["fixture_belief"])

    def test_idle_station_without_correlated_cycle_does_not_verify_processing(self):
        fixture, candidate = PacketFixture(1), self.new()
        load = candidate.step(fixture.next())["action"]
        candidate.accept_feedback(fixture.apply_symbolic(load))
        cycle = candidate.step(fixture.next())["action"]
        candidate.accept_feedback({"request_id": cycle["request_id"], "status": "accepted"})
        fixture.packet["last_feedback"] = None
        fixture.packet["station"]["busy"] = False
        result = candidate.step(fixture.next())
        self.assertEqual(result["type"], "wait")
        self.assertIsNone(candidate.state["parts"]["A0"]["cycle"])

    def test_repeated_semantically_invalid_model_actions_are_bounded(self):
        fixture, candidate = PacketFixture(1), self.new("A1")
        result = candidate.step(fixture.next())
        for _ in range(3):
            self.assertEqual(result["type"], "model")
            candidate.accept_model('{"action":{"operation":"done"}}')
            result = candidate.step(fixture.next())
        self.assertEqual(result["action"]["operation"], "help")

    def test_corrupt_checkpoint_fails_without_erasing_evidence(self):
        candidate = self.new()
        candidate.state_path.write_text('{"broken":true}', encoding="utf-8")
        with self.assertRaises(StateCorruptionError):
            self.new()
        self.assertEqual(candidate.state_path.read_text(encoding="utf-8"), '{"broken":true}')

    def test_episode_and_candidate_directories_cannot_be_reused_silently(self):
        fixture, candidate = PacketFixture(1), self.new()
        candidate.step(fixture.next())
        fixture.packet["run_id"] = "different-run"
        with self.assertRaises(ValueError):
            candidate.step(fixture.next())
        with self.assertRaises(StateCorruptionError):
            self.new("A1")

    def test_a1_model_has_action_authority_not_baseline_override(self):
        fixture, candidate = PacketFixture(2), self.new("A1")
        request = candidate.step(fixture.next())
        self.assertEqual(request["type"], "model")
        candidate.accept_model(json.dumps({"action": {"operation": "transport", "part_id": "A1", "destination": "fixture"}}))
        result = candidate.step(fixture.next())
        self.assertEqual(result["action"]["part_id"], "A1")  # sequencer would choose A0

    def test_a1_stale_order_output_cannot_execute(self):
        fixture, candidate = PacketFixture(1), self.new("A1")
        candidate.step(fixture.next())
        candidate.accept_model(json.dumps({"action": {"operation": "transport", "part_id": "A0", "destination": "fixture", "order_version": 1}}))
        fixture.packet["order"]["version"] = 2
        result = candidate.step(fixture.next())
        self.assertEqual(result["type"], "model")
        self.assertIsNone(candidate.state["pending"])

    def test_a1_false_done_is_rejected_locally(self):
        fixture, candidate = PacketFixture(1), self.new("A1")
        candidate.step(fixture.next())
        candidate.accept_model('{"action":{"operation":"done"}}')
        self.assertEqual(candidate.step(fixture.next())["type"], "model")
        self.assertIn("completion", candidate.state["last_error"])

    def test_a2_runs_two_guarded_nodes_without_second_model_call(self):
        fixture, candidate = PacketFixture(1), self.new("A2")
        self.assertEqual(candidate.step(fixture.next())["type"], "model")
        candidate.accept_model(json.dumps({"steps": [
            {"guards": [{"predicate": "at_zone", "part_id": "A0", "zone": "raw"}],
             "action": {"operation": "transport", "part_id": "A0", "destination": "fixture"}},
            {"guards": [{"predicate": "at_zone", "part_id": "A0", "zone": "fixture"}, {"predicate": "station_idle"}],
             "action": {"operation": "cycle", "part_id": "A0", "recipe": "recipeA"}},
        ]}))
        load = candidate.step(fixture.next())["action"]
        candidate.accept_feedback(fixture.apply_symbolic(load))
        result = candidate.step(fixture.next())
        self.assertEqual(result["type"], "action")
        self.assertEqual(result["action"]["operation"], "cycle")
        self.assertEqual(candidate.state["program"]["completed"], [0])

    def test_a2_program_reloads_but_rechecks_current_state(self):
        fixture, candidate = PacketFixture(1), self.new("A2")
        candidate.step(fixture.next())
        candidate.accept_model(json.dumps({"steps": [
            {"guards": [{"predicate": "at_zone", "part_id": "A0", "zone": "raw"}],
             "action": {"operation": "transport", "part_id": "A0", "destination": "fixture"}}
        ]}))
        restarted = self.new("A2")
        fixture.packet["incarnation"] = "inc2"
        fixture.detection("A0")["zone"] = "parking1"
        result = restarted.step(fixture.next())
        self.assertEqual(result["action"]["operation"], "observe")
        self.assertIsNone(restarted.state["pending"])

    def test_a2_rejects_executable_code_and_unbounded_programs(self):
        for value in ({"steps": [{"guards": [], "action": {"operation": "exec", "code": "x"}}]},
                      {"steps": [{"guards": [], "action": {"operation": "observe"}}] * 9}):
            fixture, candidate = PacketFixture(1), self.new("A2", name="a2" + str(len(str(value))))
            candidate.step(fixture.next())
            candidate.accept_model(json.dumps(value))
            self.assertIsNone(candidate.state["program"])
            self.assertEqual(candidate.state["model_failures"], 1)

    def test_a3_passes_actual_model_objective_to_executor(self):
        fixture, candidate = PacketFixture(1), self.new("A3")
        request = candidate.step(fixture.next())
        self.assertEqual(request["type"], "model")
        objective = {"clearance": 0.18, "speed_scale": 0.6, "approach": "vertical", "avoid_zones": ["parking1"]}
        candidate.accept_model(json.dumps(objective))
        result = candidate.step(fixture.next())
        self.assertEqual(result["action"]["operation"], "transport")
        self.assertEqual(result["action"]["objective"], objective)

    def test_a3_rejects_nonfinite_and_infeasible_objectives(self):
        fixture, candidate = PacketFixture(1), self.new("A3")
        for response in ('{"clearance":NaN,"speed_scale":0.6,"approach":"vertical","avoid_zones":[]}',
                         '{"clearance":0.18,"speed_scale":0.6,"approach":"vertical","avoid_zones":["fixture"]}'):
            self.assertEqual(candidate.step(fixture.next())["type"], "model")
            candidate.accept_model(response)
            self.assertIsNone(candidate._queued)
        self.assertEqual(candidate.state["model_failures"], 2)

    def test_model_failure_is_bounded_and_never_uses_fake_fallback(self):
        fixture, candidate = PacketFixture(1), self.new("A1")
        for _ in range(3):
            self.assertEqual(candidate.step(fixture.next())["type"], "model")
            candidate.accept_model("not JSON")
        result = candidate.step(fixture.next())
        self.assertEqual(result["action"]["operation"], "help")

    def test_baseline_corrects_amended_destination(self):
        candidate, fixture, _ = self.run_symbolic_baseline(3)
        fixture.packet["order"]["version"] = 2
        fixture.packet["order"]["requirements"][0]["tray"] = "tray3"
        result = candidate.step(fixture.next())
        self.assertEqual(result["action"]["operation"], "transport")
        self.assertEqual(result["action"]["destination"], "tray3")
        self.assertEqual(result["action"]["order_version"], 2)

    def test_current_observation_is_required_for_completion(self):
        candidate, fixture, _ = self.run_symbolic_baseline(3)
        for item in fixture.packet["detections"]:
            item["age_s"] = 20.0
        result = candidate.step(fixture.next())
        self.assertNotEqual(result.get("action", {}).get("operation"), "done")

    def test_no_persistence_uses_identical_policy_before_restart(self):
        fixture = PacketFixture(1)
        first, second = self.new(name="yes"), self.new(name="no", persistent=False)
        packet = fixture.next()
        a = first.step(packet)["action"]
        b = second.step(packet)["action"]
        for action in (a, b):
            action.pop("request_id")
        self.assertEqual(a, b)

    def test_new_human_answer_resumes_model_attempt_and_duplicate_does_not(self):
        fixture,candidate=PacketFixture(1),self.new('A1')
        candidate.step(fixture.next())
        candidate._model_context=None
        candidate.state['halted']=True;candidate.state['model_failures']=3
        answer={'answer_id':'help-answer-1','content':'Reobserve public evidence','simulated_assistance':True}
        fixture.packet['human_answers']=[answer]
        result=candidate.step(fixture.next())
        self.assertEqual(result['type'],'model')
        self.assertFalse(candidate.state['halted'])
        self.assertEqual(candidate.state['model_failures'],0)
        self.assertEqual(candidate._context()['human_answers'],[answer])
        candidate._model_context=None;candidate.state['halted']=True
        self.assertEqual(candidate.step(fixture.next())['type'],'wait')
        restarted=self.new('A1')
        self.assertEqual(restarted.step(fixture.next())['type'],'wait')

    def test_human_advice_cannot_clear_unresolved_action_or_create_history(self):
        fixture,candidate=PacketFixture(1),self.new()
        action=candidate.step(fixture.next())['action']
        candidate.state['halted']=True
        fixture.packet['human_answers']=[{'answer_id':'help-1','content':'Reobserve public evidence'}]
        candidate.step(fixture.next())
        self.assertEqual(candidate.state['pending']['action']['request_id'],action['request_id'])
        self.assertIsNone(candidate.state['parts']['A0']['cycle'])
        self.assertIsNone(candidate.state['parts']['A0']['inspection'])

    def test_help_action_contains_structured_public_evidence(self):
        fixture,candidate=PacketFixture(1),self.new()
        candidate.step(fixture.next())
        result=candidate._issue({'operation':'help','reason':'unknown outcome'})
        self.assertEqual(result['action']['evidence']['observation_sequence'],fixture.packet['sequence'])
        self.assertTrue(result['action']['evidence']['pending_outcome_unknown'])
        self.assertIn('requested_information_or_action',result['action'])


if __name__ == "__main__":
    unittest.main(verbosity=2)
