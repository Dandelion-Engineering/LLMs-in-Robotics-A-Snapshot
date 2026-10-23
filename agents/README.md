# Agent Workspaces

Each AI agent has a continuity workspace under `agents/<AgentName>/`.

The workspace exists because model sessions are reinitialized. It preserves what the next session needs without forcing the agent to reread the full project history.

A typical workspace contains:

```text
agents/<AgentName>/
├── README.md
├── Summary of Only Necessary Context.md
└── Session Summaries/
```

Projects and agents may add research notes, references, scratch analyses, or other durable material when useful.

Agent workspaces are not private. Other participants may read and use them. Live edits still follow the work-claim rules.
