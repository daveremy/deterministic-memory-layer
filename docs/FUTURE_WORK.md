# DML Future Work

## Session Injection (Persistent Memory Across Sessions)

### The Problem
Currently DML state is preserved in the database, but Claude doesn't automatically know about it when starting a new session. Users have to re-explain context.

### Proposed Solution
Inject DML state summary at session start, giving Claude immediate awareness of facts, constraints, and recent decisions.

### Design Considerations

#### Scope Control
Not everything should be injected. Need scoping mechanisms:

| Scope | Description | Example |
|-------|-------------|---------|
| `session` | Dies with session | Temporary calculations |
| `project` | Scoped to project/directory | Project-specific constraints |
| `user` | Follows user across projects | Preferences, accessibility needs |
| `global` | Always active | Safety constraints |

#### TTL (Time-To-Live)
Facts/constraints may become stale:
- `ttl: 7d` - Expires after 7 days
- `ttl: session` - Dies with session
- `ttl: permanent` - Never expires

#### Relevance Filtering
Don't inject everything - use relevance:
- Recent events (last N events or last N days)
- Events matching current project/context
- High-priority constraints only
- Semantic search for relevant facts

#### Injection Format
```markdown
## DML Memory State

### Active Constraints (2)
- ⚠️ wheelchair accessible required [user scope, permanent]
- dietary: vegetarian [user scope, 30d TTL]

### Key Facts (5 most relevant)
- budget: $5000 (was: $4000) [project scope]
- destination: Japan [project scope]
- travel_dates: April 12-19, 2026 [project scope]

### Recent Decisions (last 3)
- ✓ [accommodation] Book accessible onsen hotel
- ✗ [accommodation] Book Ryokan Kurashiki (BLOCKED)
- ✓ [dates] Travel April 12-19

### Session Note
Use DML tools to update this state. Query with `memory.query()`.
```

#### Implementation Options

1. **MCP Resource**: `dml://context` resource that returns formatted state
2. **Skill Hook**: Skill that runs on session start, queries DML, outputs context
3. **CLAUDE.md Generation**: Dynamically update CLAUDE.md with state
4. **Hooks Integration**: Claude Code hooks to inject on session start

#### Security Considerations
- Who can set `global` scope constraints?
- How to prevent injection attacks via stored facts?
- Should sensitive facts be redacted in injection?

#### Open Questions
- How to detect "new session" vs "continuing session"?
- Should injection be opt-in or opt-out?
- How to handle conflicting facts across scopes?
- Token budget for injection (max tokens to use)?

### MVP Scope
For v1, keep it simple:
1. Add `scope` field to facts/constraints (default: `project`)
2. Add `get_injection_context()` to MemoryAPI
3. Create MCP resource `dml://context`
4. Document how to use in skill/CLAUDE.md

### Future Enhancements
- Semantic relevance filtering
- Cross-project knowledge sharing
- Team/org shared constraints
- Automatic TTL expiration daemon

---

## Other Future Work

### Decision Supersession
- Add `topic` field to decisions ✅ DONE
- Track supersession within same topic
- Show "was: previous decision" like facts

### Constraint Hierarchies
- Constraint priorities with override rules
- Inherited constraints from parent scopes
- Constraint conflict resolution

### Multi-Agent Support
- Correlation IDs for agent-to-agent handoffs
- Shared memory spaces
- Agent-specific views of shared state

### Observability Integration
- Weave integration (started, needs auth fix)
- OpenTelemetry export
- Dashboard for memory visualization

### Performance
- Event compaction for old events
- Snapshot checkpoints for faster replay
- Async event appending

---

*Last updated: Jan 31, 2026*
