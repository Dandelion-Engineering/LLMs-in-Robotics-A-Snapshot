# Source lookup scope correction

During the September 28 quiescence design, a repository text lookup for ThreadUnsubscribeResponse and handler names was inadvertently scoped to all JSON/Markdown/Rust files under io-repair. It traversed generated result and source-binding JSON files in addition to retained source packets, and produced excessive truncated output. Those historical jobs were not freshly authenticated for this search.

The lookup was used only to locate protocol schema/source paths. No empirical outcome, historical verdict, qualification result or admission decision is inferred from its matches. This was an operator search-scope mistake, not a new assessment of those outputs. Subsequent reads are restricted to the exact retained native schema files and explicitly named Rust source packets. Any later empirical use still requires its own fresh official queue authentication.
