# Chats

Chats are subject-focused communication between project participants.

They exist to exchange information, coordinate work, ask focused questions, request another perspective, and communicate with the human director. They are not approval systems.

## Structure

```text
chats/
├── Claude-Codex/
├── Claude-Codex-Human/
├── Claude-Human/
└── Codex-Human/
```

A channel folder names its participants with hyphens. Inside it, each subject has its own folder:

```text
chats/<participants>/<Subject>/
├── <Subject> - Active.md
└── Summary.md                 # created when concluded
```

While active, the transcript is named:

```text
<Subject> - Active.md
```

When its immediate purpose has been served, rename it:

```text
<Subject> - Concluded.md
```

and create `Summary.md` with the date range, durable outcome, important uncertainty, and any context future work needs.

## Meaning of the lifecycle

- **Active:** the conversation may still require attention or a response.
- **Concluded:** no immediate response is expected; the record remains available as history.

Concluded does **not** mean every participant approved the same conclusion or now holds the same belief.

Conclude a chat when the needed information has been exchanged, the question has been answered, one participant has what it needs to continue, or a recorded disagreement no longer blocks current work.

If the same subject becomes relevant later, begin a new focused chat rather than reviving a concluded transcript.

## Naming subjects

Use a short descriptive noun phrase that identifies the question or coordination topic, such as:

- `Dataset Access`
- `Architecture Alternatives`
- `Unexpected Validation Result`
- `Improve Technical Report`

Avoid generic names such as `Discussion`, `Updates`, or `Review` when a more specific subject exists.

## Writing transcripts

After an active transcript is created, do not hand-edit it. Read and append through `Tools/chat.py`, documented in `Tools/chat.md`.

For a human participant, the safe path is one interactive command from the project root:

```shell
python -B Tools/chat.py human
```

It lists active human chats, prompts for the destination, name, and message, adds the local date and time, and verifies the append. A human can therefore contribute without editing transcript syntax or coordinating byte counts manually.

The inbox discovers files ending in `Active.md` inside channel folders naming the agent. Concluded transcripts are intentionally absent from the active inbox.
