
## Database Session Isolation (Future)

Currently the MCP server uses a single global database at `~/.dml/memory.db`. This causes conflicts when multiple Claude sessions run concurrently.

**Proposed Solution:**
- Add `DML_SESSION_ID` environment variable support
- Key database path by session: `~/.dml/sessions/{session_id}/memory.db`
- Or key by cwd hash: `~/.dml/sessions/{hash(cwd)}/memory.db`
- Add `--session` flag to `dml serve` command
- Consider memory scopes: global, project, session

**Benefits:**
- Validator can run isolated from other sessions
- Multiple demos can run in parallel
- Future: cross-session memory sharing with explicit scoping
