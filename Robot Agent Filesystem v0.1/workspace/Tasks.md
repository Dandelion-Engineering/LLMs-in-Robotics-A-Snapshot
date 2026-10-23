# Tasks

**Status:** UNCONFIGURED TEMPLATE — no robot operation authorized by this file.

**Writer during operation:** trusted operator/task service. The robot agent records its plan and progress elsewhere.

## Current job

- Task ID and revision: `{{TASK_ID_AND_REVISION}}`
- Goal and required deliverables: `{{TASK_DESCRIPTION}}`
- Objects, resources, destinations, and identifiers: `{{RELEVANT_ENTITIES}}`
- Dependencies and constraints that must remain satisfied: `{{TASK_RULES}}`
- What observable evidence supports completion: `{{COMPLETION_EVIDENCE}}`
- Allowed recovery, substitution, rework, and task-change permissions: `{{RECOVERY_PERMISSIONS}}`
- Conditions that require waiting or human help: `{{ESCALATION_RULES}}`
- Time, model-use, program-execution, and intervention budgets: `{{RUN_BUDGETS}}`

## Normal operation and handback

Describe the nominal procedure in plain language, including expected processing waits. Point to the actual skills in `Tools.md`. Describe a valid state in which normal automation can resume; do not provide solutions to hidden test exceptions.

`{{NORMAL_WORKFLOW_AND_HANDBACK_CONDITIONS}}`

## Task updates

The supervisor publishes authorized revisions here and records their origin in public history. Commands refer to the effective revision where relevant. Editing a progress note cannot change the order, authorize a substitution, or declare the job complete.
