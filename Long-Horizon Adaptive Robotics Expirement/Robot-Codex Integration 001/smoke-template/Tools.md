# Tools for the filesystem-only smoke check

Use the installed client shell/file tools to read the required local Markdown/JSON/JSONL and to write Continuity.md, notes/, and programs/. These writes are allowed; all other workspace documents and live/ are protected. Use UTF-8. No robot interface, generated-program service, robot sensor or external service is exposed.

For this non-actuating check a direct write of Continuity.md is sufficient. This does not test atomic continuity or crash recovery. Do not read outside the workspace, inspect credentials, call external apps, use the internet, or spawn subagents. Do not try to infer model settings; the launcher records these independently.
