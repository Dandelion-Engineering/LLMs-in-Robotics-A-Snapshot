# Prospective transport repair

Campaign 001 stock05 remains infrastructure-invalid. Its protected host reached
task success before the last continuity command began; the upstream connection
then refused a request and the broker aborted the unfinished model turn. The
retained sparse failure record cannot establish the failed request's exact route.
The original [investigation](../campaign-001/investigation/stock05-transport-investigation.md),
sources, assessments and outcomes remain unchanged.

The additive [runtime](harness/runtime.py) prevents further upstream access after
a trusted receipt establishes that the invocation lost authority. An accepted
handback must match the request identity, pinned authority generation, completed
terminal handback command, conventional owner and next generation. Alternatively,
an upstream HTTP403 with the specific capability-denial code establishes
revocation. A malformed or rejected handback, a local wrong-token denial, or an
unrelated HTTP403 does not establish revocation.

Once revoked, later robot requests receive HTTP403 from a local fence, including
continuity writes. The mirror stops. A mirror connection request already in
flight may finish with a nonfatal transport exception only after the revocation
has been established; publication and other failures remain fatal. Pre-revocation
transport failures still abort the invocation. The bootstrap client still requires
an actual completed model turn. This changes infrastructure lifecycle handling;
it does not change model instructions, recovery behavior, control permissions,
continuity authorization, evaluator results or disposition rules.

No protected host grace interval is necessary for this repair. The protected
host may close normally. A local revocation fence is explicitly identified and
cannot substitute for a missing late HTTP403 receipt from that host. The
prospective assessor must still authenticate host closure and namespace
retirement through their independent evidence.

Every validated request now receives a durable pre-dispatch record in
`broker-requests.jsonl`. Its unique `trace_id` links to the completed
`broker-events.jsonl` record or `broker-failure.json`, with method, route,
request identity and timestamps. Completed records identify `protected_host`,
`local_capability_fence` or `local_revocation_fence` origin. The first revocation
witness is retained in `authority-revocation.json`. Local route rejections and
the bounded mirror race have separate receipts. Ephemeral tokens remain redacted.

An additional fail-closed correction distinguishes request-validation errors
from upstream JSON errors: malformed upstream JSON now produces a transport
failure rather than being mislabeled as a local route denial.

The [15 deterministic tests](harness/test_transport.py) cover late continuity and
actuation denials; real loopback closure after handback; narrow receipt matching;
unrelated HTTP403 and wrong-token controls; pre-revocation failure; malformed
upstream JSON; pre-dispatch provenance; mirror races; publication failure; and
immutable first-revocation evidence. Run with the project interpreter:

```powershell
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s "Long-Horizon Adaptive Robotics Expirement\Robot-Codex Integration 001\campaign-002\harness" -p test_transport.py -v
```

These tests use mocks and one real loopback HTTP server. They invoke no model,
WSL namespace, simulator or campaign. Passing them establishes the tested
infrastructure logic, not qualification of the complete apparatus or robot
repeatability. Full requalification and exact source binding remain separate
Campaign 002 admission requirements.
