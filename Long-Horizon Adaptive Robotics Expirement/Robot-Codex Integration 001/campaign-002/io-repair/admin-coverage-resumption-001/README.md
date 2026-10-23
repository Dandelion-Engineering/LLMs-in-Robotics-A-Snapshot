# Session18: elevation succeeded; packet coverage failed

Randy's September29 20:21PDT message authorized one more execution of the exact
Session17 helper. [Preflight](preflight-001.json) verified all three runtime
source hashes, the twelve-check test receipt, the unchanged launcher, preservation
of the canceled first attempt, and absence of the declared output directory.
[Elevation attempt002](elevation-attempt-002.json) returned a launched process
and actual integer exit0 after Windows consent.

The [independent assessment](assessment-001.json) found that both synthetic
controls passed, all commands used the exact loopback port59911, the40-byte
prefix and16MiB ceiling were preserved, and the owned capture stopped after
0.7343255seconds. Both retained process handles signaled; the private job was
empty, Packet Monitor was idle and its two owned filters were removed.

**Coverage failed.** The11,960-byte ETL contains only a header and two partition
metadata events: zero manifest/provider packet events. It cannot identify either
the FIN or RST control. Reported zero loss and orderly cleanup do not make it
adequate for the Smoke027 diagnosis. All29 small original files have verified
copies in [evidence](evidence); the external originals remain unchanged.
The raw ETL copy is retained locally and explicitly ignored by Git, even
though it contained no connection events. Its measured hash remains recorded.

The separately declared [TCP event diagnostic](../tcp-event-coverage-001/README.md)
subsequently observed the intended closures but failed its collection-scope
check. Neither diagnostic launched a model, a queue job, a qualifier, a pilot or
a scored slot. Campaign002 remains unqualified with zero scored starts, V29
stays stopped, and Campaign001 remains frozen.
