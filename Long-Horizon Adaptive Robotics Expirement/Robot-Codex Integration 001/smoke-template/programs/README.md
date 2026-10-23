# Agent-created programs

Write or revise recovery programs here using the actual API and interpreter documented in `../Tools.md`. This draft supplies no executable robot example because no adapter has been bound yet.

Programs can use normal language constructs, inspect permitted observations, call existing skills, and combine bounded manual actions. Keep code readable and preserve the reason for material changes. Do not modify a program while its pinned version is executing; submit a new version after the documented transition.

Every physical action still passes through the protected gateway. The shell, imported libraries, subprocesses, file edits, and custom code cannot grant a second route to actuators. A stopped program does not automatically undo its actions or safely release a held object.

Retain the program run ID, code version/hash, relevant inputs, outcome evidence, and limitations for reuse. The agent may reuse an appropriate program within the authorized job. Automatic installation into the conventional skill library across future runs is outside this first version.
