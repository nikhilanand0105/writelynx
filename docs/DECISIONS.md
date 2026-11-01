# Decisions

- Preserve the existing Python/React stack and local deployment. No hosted service is needed.
- Use conservative, transparent heuristics in no-LLM mode. Unknown research facts remain unresolved.
- Preserve all imported detector reports; writing analysis must not erase manual highlight mappings.
- Ambiguous duplicate text requires manual alignment. Extraction confidence and alignment confidence describe distinct operations.
- Persist complete version snapshots for recovery; record every edit as an append-only event. Original files remain untouched.
- Do not silently drop styles or complex XML to make an edit succeed. Block unsupported edits with an explanation.
- Gate all remote provider use on explicit server configuration and user-selected privacy mode. Secrets stay on the server.
- Isolate tests from existing storage and SQLite data. Add adversarial tests for claims the original happy-path suite did not establish.
