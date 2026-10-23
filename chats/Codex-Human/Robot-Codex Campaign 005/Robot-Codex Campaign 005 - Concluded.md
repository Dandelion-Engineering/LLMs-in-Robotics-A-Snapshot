# Robot-Codex Campaign 005

---

**Randy (2026-10-04 13:17 PDT):**

Campaign 004 is complete and must remain immutable. Start a new prospective **Campaign 005** lineage.

The purpose of Campaign 005 is a targeted iteration on the persistent Robot-Codex filesystem/memory architecture. Campaign 004 showed that durable artifacts can persist without becoming discoverable or reused: Session 1 created `programs/c_step.py`, but the later sessions that read `Continuity.md` were never told that helper existed. I want Campaign 005 to test a lightweight structured handoff discipline that connects durable artifacts to the canonical continuity surface without teaching Robot-Codex a C-specific solution.

Proceed **all the way through Campaign 005 completion in this Development Codex session**: implement the memory/discoverability changes below, perform the qualification legitimately required, prospectively freeze/register the exact Campaign 005 experiment, run the single Campaign 005 block, investigate the observable behavior/results, produce the inspection/replay material, and stop when Campaign 005 is complete and ready for my review. Do not return for routine approval between those stages.

## Scientific intervention: preserve useful work and make it discoverable

Keep the intervention domain-general. Do not tell Robot-Codex what C procedure to create, what exact artifact to save, or what prior program it should reuse.

Strengthen the Robot-Codex-facing memory contract so that:

- The writable persistent workspace remains available across fresh invocations.
- `Continuity.md` is the **front door / handoff map**, not a giant transcript or evidence dump.
- Detailed evidence and session-specific material can remain under `notes/`.
- Reusable procedural artifacts, helpers, controllers, scripts, or other durable executable work can remain under `programs/`.
- When Robot-Codex creates or materially improves a durable artifact that could plausibly help a future invocation, it should preserve it and add a concise entry to `Continuity.md` that states:
  - the artifact path,
  - its purpose,
  - why it may matter later,
  - important limitations, assumptions, or adaptation requirements.
- Robot-Codex should preserve other learned information that could matter later, including unresolved state, important constraints, useful recovery knowledge, and references to detailed evidence, while keeping the continuity surface concise enough to serve as a map.
- At fresh-session startup, Robot-Codex should inspect the current task/authority/evidence **and** inspect `Continuity.md` for potentially relevant historical material.
- Historical files and notes remain untrusted historical material: they do not grant authority, override current instructions, or substitute for current robot observations. Any reuse must be reconciled against the current public task, authority, and world state.
- Before ending, Robot-Codex should leave a useful handoff for future invocations when there is durable knowledge or work worth preserving.
- Do **not** tell Robot-Codex that another session is guaranteed or that the current C occurrence has hidden retry opportunities. It must still attempt to solve the present task fully within the current invocation.

Replace the current wording that says no particular artifact or memory strategy is required with a minimal general memory/handoff discipline consistent with the above. Avoid over-prescribing behavior beyond what is necessary to make durable work discoverable.

### Framework-maintained artifact discoverability

Add a small machine-authored artifact inventory/index if it can be done cleanly without leaking protected state or directing the scientific policy.

Its role should be structural bookkeeping, complementary to the agent-authored semantic handoff:
- which durable writable artifacts exist or were materially changed,
- path/version/hash/session identity or equivalent provenance,
- no protected evaluator truth,
- no hidden reasoning,
- no semantic claim that an artifact is useful unless the agent itself makes that claim.

A fresh session should be able to inspect this structural inventory as part of the persistent workspace, but the agent-authored `Continuity.md` remains the semantic front door. If a separate machine index would create unnecessary complexity or confound the targeted intervention, implement the simplest equivalent that preserves the same discoverability goal and document the choice prospectively.

## Keep the rest of Campaign 004 comparable

Carry forward the successful Campaign 004 perception fix:
- family-C identity must remain robustly publicly detectable across relevant stable orientations through the rendered public perception path;
- do not expose simulator/evaluator truth;
- do not add a high-level C placement routine;
- keep the physical task geometry and manipulation challenge comparable.

Keep the experimental Robot-Codex model/effort the same: **GPT-6 Astra / max reasoning**.

Keep the sole bootstrap minimal unless a strictly technical compatibility change is required.

Preserve the same general per-session runtime/action/observation generosity as Campaign 004 unless a materially different bound is scientifically necessary and is prospectively justified.

## One Campaign 005 block: three C occurrences

Run **one frozen Campaign 005 block only** for this iteration.

Inside that single block:
- keep **three separated C occurrences**,
- keep ordinary successful A/B work between C occurrences as in Campaign 004,
- each C occurrence may use **up to three fresh Robot-Codex sessions** if needed,
- therefore the absolute campaign maximum remains **nine Robot-Codex sessions**,
- unused session opportunities must not be launched merely to fill the allowance.

For each C occurrence:
- Session 1 starts fresh.
- If it succeeds with accepted handback, retire normally and continue to the intervening work / next occurrence.
- If it ends normally while the occurrence remains unresolved but the apparatus independently establishes a safe, durable, unambiguous continuation state, silently admit the next fresh session for that same occurrence if one of the three hidden opportunities remains.
- Preserve the same physical world state and persistent workspace across those fresh sessions.
- Do not inject a diagnosis or tell the successor that it is attempt 2 or 3.
- If the third session ends without accepted handback, record the occurrence as a legitimate task failure and stop the experimental block.
- Unsafe, unknown-outcome, infrastructure-invalid, corrupted/ambiguous authority, or evidence-invalid endings must not silently trigger another model session.

Robot-Codex must **not** be told there are three sessions per C occurrence or nine possible sessions total.

## What Campaign 005 should measure

Preserve Campaign 004 evidence rigor and specifically make it possible to determine for each fresh Robot-Codex session:

- whether it read `Continuity.md`,
- what continuity content was visible at that point,
- whether durable artifacts created by earlier sessions were indexed/referenced there,
- whether it inspected the framework artifact inventory if one is added,
- whether it opened, executed, adapted, copied, superseded, or ignored prior durable artifacts,
- whether it created new durable artifacts,
- whether it indexed those artifacts into the semantic handoff,
- what artifact purpose/limitations it recorded,
- whether later sessions actually encountered those references,
- whether later behavior shows observable procedural reuse, adaptation, rediscovery, or non-use,
- action/observation/image/tool counts and timing,
- why each session ended,
- whether handback was accepted/rejected,
- whether substantial budget remained,
- whether the physical task was independently satisfied at session end.

Keep these evidence levels distinct:
- artifact existence,
- artifact discoverability/indexing,
- artifact read,
- artifact execution,
- semantic reuse/adaptation,
- useful transfer,
- causal contribution.

Do not reconstruct hidden chain-of-thought. Similar behavior after exposure is not, by itself, proof of causal memory benefit.

## Qualification and prospective freeze

Campaigns 001-004 and all retained evidence remain immutable.

Before the actual Campaign 005 block, qualify the changed memory/discoverability path prospectively. Use deterministic/model-free qualification wherever possible. At minimum verify:

1. A durable artifact can be created and persists across a fresh invocation.
2. The semantic handoff can reference the artifact by path/purpose/limitations.
3. The next fresh invocation can read the handoff and inspect the referenced artifact.
4. Any framework-maintained artifact inventory truthfully reflects durable writable artifacts and versions without exposing protected state.
5. Old historical material cannot grant authority or bypass current task/evidence requirements.
6. Same-world safe-unresolved continuation still works across fresh sessions.
7. The hidden per-occurrence session ceiling remains strictly three and invisible to Robot-Codex.
8. Accepted/rejected handback accounting and invalid-stop behavior remain truthful.
9. Filesystem journaling and replay can reconstruct handoff/index/artifact reads and writes across session boundaries.
10. The six-face C identity/perception qualification and no-high-level-C-placement condition remain intact.
11. Campaigns 001-004 remain unchanged.

If qualification finds an infrastructure/evidence defect, preserve the failed qualification, repair prospectively, and requalify. Do not tune Robot-Codex's C manipulation policy based on model success.

Once qualified:
- freeze/register the exact Campaign 005 source, seeds/schedule, limits, memory contract, stopping rules, evidence plan, three-C structure and three-session-per-occurrence ceiling;
- run exactly **one** actual Campaign 005 block;
- do not run extra replacement or replicate blocks merely because the outcome is interesting or disappointing unless the frozen validity rules require replacement for an infrastructure-invalid run;
- preserve every actual/not-run disposition;
- perform the final behavioral/continuity investigation;
- build/update a synchronized human-facing replay that exposes public model messages/tool results, world states/images, filesystem history, handoff/index evolution and fresh-session boundaries without hidden reasoning.

## Human-decision boundary

Continue substantive work without asking me for routine approval at implementation, qualification, freeze, launch, between C occurrences, between safe-unresolved hidden sessions, investigation or replay.

Stop and ask me only if something genuinely requires my authority or a new scientific decision—for example credentials/admin/physical access, spending, destructive changes, threatened storage that cannot be handled under existing policy, weakening safety/evidence guarantees, changing the core Campaign 005 scientific question, changing Robot-Codex's model/effort, adding a C-specific memory strategy, or exhausting supported technical paths.

Otherwise, **continue through the full Campaign 005 run and final investigation, then stop when Campaign 005 is complete and ready for my review.**

---

---

**Codex (Session 27, 2026-10-04 14:40 PDT):**

Campaign 005 is complete and ready for review. The sole frozen block (`RCI001-C05-final-001-block-001`) produced three valid C successes in three fresh Astra/max sessions, all with accepted handback, conventional resumption and independently satisfied placement. Six session opportunities remained unused; no replacement block was launched.

All three sessions read `Continuity.md`. Session 1 created and indexed `programs/bounded_step.py`; session 2 opened, adapted and executed it; session 3 opened and executed the adapted version unchanged. Sessions 1 and 2 also read the structural inventory; session 3 did not. This is observable functional reuse during successful work, not proof that memory caused success or improved efficiency. The handoff accumulated prior sections, so long-horizon compaction remains untested.

The [investigation](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-005/inspection/README.md) includes exact journal/public-command references, counts, handoff evolution, limitations and the [synchronized replay](D:/Dandelion-Campaign005-Exports/inspection/replay-001/index.html). [HumanReport27](../../../agents/Codex/Session%20Summaries/HumanReport27.md) is the session handoff. The investigation provides the command for reopening the replay through loopback HTTP.

The initial model-free qualification failure is preserved: Linux reused a retired PID namespace number, invalidating the fixture's uniqueness assertion. A prospective fix using namespace plus process start ticks passed requalification and independent readback. No model was called during qualification, and the actual source was frozen before the single block.

Actual, audit, analysis, replay and final preservation workers all succeeded with integer exit 0 and separate content checks. Session 1's two stale-observation rejections remain visible. Final readback verified all 45,007 historical files, the frozen source and original actual evidence unchanged. Your approved lossless compression preserved every selected log's hash, length and modification time and recovered 1.62 GiB of physical allocation; the launch reserve was not relaxed.

Desktop/mobile replay controls and exact source bytes were checked; direct file-URL rendering was not tested. Temporary runtime and preview processes are retired. I am stopping after scoped closeout; no further model work is queued.


---

**Randy (2026-10-06 18:26 PDT):**

This campaign is complete. Please conclude this chat now using the normal chat-conclusion process, including creating/updating the durable summary as appropriate. Do not begin any new campaign work from this message.
