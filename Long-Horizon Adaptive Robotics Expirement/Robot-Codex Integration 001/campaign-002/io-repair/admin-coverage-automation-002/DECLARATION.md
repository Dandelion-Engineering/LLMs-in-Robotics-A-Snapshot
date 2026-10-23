# Bounded coverage helper repair — Session 17

This is a no-model infrastructure diagnostic. Preserve both user-run attempts
and the exact helpers in `../admin-guidance-handoff-001/`. V29 remains stopped;
no old qualification pass authorizes scoring.

Before elevation, reproduce the venv launch/ready PID relationship using the
unchanged synthetic fixture. Bind the launch to a private Windows Job Object
at process creation, with kill-on-close and no breakaway. Accept a ready PID
only when its retained process handle is in that job, its executable matches
the project venv or its base interpreter, its creation time follows the
launcher, and its ancestry is the launcher (or the launcher itself). Record
both identities. Require an empty job and signaled retained handles on cleanup.
PID inequality alone is neither failure nor adequate identity evidence.

Exercise successful release, interruption before release, malformed identity,
and partial capture-command failures without elevated commands or a model.
Simulated capture commands establish control flow only, never OS coverage.

Only then launch the fixed helper once using Windows RunAs/UAC. This is one
bounded process, not an administrator command service. No terminal automation,
new account, credential retrieval, security-setting change, or model invocation
is involved. Use a fresh `coverage-managed-YYYYMMDD-NNN` output beneath the
already authorized `C:/Users/cresp/Documents/Campaign002 TCP Trace` root, keeping
the native ETL path below legacy Windows path limits. Read output files directly.
Capture only the original two FIN/RST
filters on the fresh fixture's exact IPv4 loopback port; retain the 40-byte
prefix, 16 MiB ceiling, 30-second bound, idle/empty preflight, and owned cleanup.
Unknown capture/filter ownership prevents blanket stop or removal. Do not
automatically broaden capture or launch native work after collection.

Independently check both controls, endpoint/clock correlation, loss/wrap, bounds,
and cleanup. Inadequate coverage remains inadequate. A further TCP/IP event
trace needs a separate prospective scope before execution. Any native
diagnostic must ask a distinct declared question, and any resulting repair
requires full fresh qualification before Campaign 002.

References: [Windows job membership at process creation](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute),
[job lifetime](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
[Python venv redirectors](https://docs.python.org/3.12/library/venv.html).
