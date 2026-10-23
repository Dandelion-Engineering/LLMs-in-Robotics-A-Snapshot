"""Retain an operator receipt and append one operational Architecture Map note."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tomllib

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE))
from common import read, save, sha, canonical
from register import append, base, ref

pair = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
op = pair / 'operator/resume-session34-001'
out = Path(__file__).parent
startup = pair / 'operator/startup/observation-3b88ec779e0d47399f964ff04151a4c9.json'
assert read(startup)['passed'] is True
assert read(op / 'continuation-verification.json')['passed'] is True
config_path = Path('C:/Users/cresp/.codex/automations/apartment-v2-baseline-observations/automation.toml')
automation = tomllib.loads(config_path.read_text(encoding='utf-8'))
assert automation['status'] == 'ACTIVE' and automation['target_thread_id'] == '01a11bda-ab28-7290-842e-df267284ba99'
monitor = dict(automation_id=automation['id'], status=automation['status'], target_thread=automation['target_thread_id'],
               interval_minutes=30, kind='heartbeat', queue_job=read(op / 'resume-queue.json')['id'],
               recorded_utc=datetime.now(timezone.utc).isoformat(), pair=str(pair), session_open=True,
               stop_conditions=['Verified Baseline endpoint', 'Verified human-requested hibernation', 'Genuine blocker requiring human input'])
save(op / 'monitoring-restored.json', monitor)
save(out / 'monitoring.json', monitor)
ui = dict(observed_utc=datetime.now(timezone.utc).isoformat(), url='http://127.0.0.1:51023', browser='Codex in-app browser', tab_id='1',
          passed=True, apartment_robot_rendered=True, session_displayed=24, battery_displayed_percent=99.6,
          visible_task='Find the cup on one of the three kitchen countertop mats and put it inside drawer A.',
          protected_journal_updates_visible=True, observer_only=True, tab_kept_open=True,
          evidence_kind='Direct browser accessibility and screenshot inspection; no scientific interpretation')
save(op / 'ui-observation.json', ui)
save(out / 'ui-observation.json', ui)
receipt = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), pair=str(pair), root=str(pair / 'baseline'),
               queue_job=monitor['queue_job'], checkpoint=read(op / 'continuation-verification.json')['checkpoint'],
               checkpoint_session=23, first_resumed_session=24, assignments_preserved=15, assignments_total=21,
               reset=False, reroll=False, recovery_branch=False, model_retry=False, maps_pristine=True,
               viewer_url=ui['url'], monitoring=monitor, endpoint_complete=False, endpoint_session_count=None,
               verification=dict(pre_resume_audit=read(op / 'audit-terminal-queue.json')['id'],
                                 pre_resume_checks=read(op / 'audit/result.json')['checks'],
                                 continuation_checks=read(op / 'continuation-verification.json')['checks'],
                                 startup_checks=read(startup)['checks']))
save(op / 'verified-resume.json', receipt)
save(out / 'verified-resume.json', receipt)
note = {**base('APARTMENT-v2-baseline-resume-001'), 'tags':['apartment','official','resume','verified-checkpoint','observational'],
        'target_ids':['APARTMENT-v2-baseline'], 'claim_type':'observation', 'supersedes_note_id':None,
        'body':'Randy explicitly authorized clean continuation on October 8 at 07:08 PDT. A fresh queued independent hibernation readback passed all five gates; Windows/Linux process and queue checks found no duplicate. The existing baseline resumed once at 07:16 PDT from checkpoint 23, preserving 15 of 21 assignments, world/RNG, exact files/inodes and recording lineage. Session 24 resumed at the exact event/simulation boundary and passed native startup, isolation, tool, physics, journal and recording checks. The live viewer rendered correctly and same-thread 30-minute monitoring was restored. This is continuation health only; no completed endpoint or condition comparison is available. Maps remains pristine and unlaunched. Human-requested deferred hibernation remains available.',
        'details':dict(queue_job=monitor['queue_job'], checkpoint_session=23, assignments_preserved=15, endpoint_session_count=None),
        'evidence':[ref('Explicit human resume instruction',op/'authority.json'),ref('Pre-resume independent readback',op/'audit/result.json'),
                    ref('Readback queue terminal',op/'audit-terminal-queue.json'),ref('Fresh process and duplicate check',op/'preresume-idle.json'),
                    ref('Exclusive resume submission',op/'resume-intent.json'),ref('Resume queue',op/'resume-queue.json'),
                    ref('Exact continuation checks',op/'continuation-verification.json'),ref('Passed native startup',startup),
                    ref('Rendered viewer observation',op/'ui-observation.json'),ref('Restored monitoring',op/'monitoring-restored.json')]}
append('note',note,out)
print(canonical(dict(receipt=str(op/'verified-resume.json'),registered=note['id'],monitoring=monitor['status'])).decode())
