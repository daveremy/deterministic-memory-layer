# DML: Deterministic Memory Layer
## Quick Guide for Hackathon Judges

### What It Does (30 seconds)
DML gives AI agents **structured, auditable memory** instead of a growing text blob.

- **Event-driven**: Every fact, constraint, and decision is an immutable event
- **Deterministic**: Replay events → get same state every time
- **Self-improving**: Agent learns constraints from mistakes, enforced automatically
- **Observable**: Full Weave integration - every operation is traced

### Watch the Demo (2 minutes)

[![asciicast](https://asciinema.org/a/poksmLtZA784MzjQ.svg)](https://asciinema.org/a/poksmLtZA784MzjQ)

A dinner party planning scenario showing:
1. **Facts captured** from natural conversation (guest count, date)
2. **Fact updates** with history preserved (not overwritten)
3. **Constraints recorded** from casual mentions ("Sarah is vegetarian")
4. **Provenance queries** showing change history
5. **Constraint-aware reasoning** before agreeing to suggestions

### Key Moments to Watch

| Moment | What Happens | Why It Matters |
|--------|--------------|----------------|
| Fact recorded | Claude calls `add_fact` | Structured data from natural language |
| Fact updated | New event references old | History preserved, not overwritten |
| Constraint added | "vegetarian" becomes a rule | Casual mention → enforceable constraint |
| Provenance shown | "Guest count changed from 6 to 8" | Full audit trail |
| Constraint checked | Claude considers dietary needs | Memory informs decisions |

### Try It Yourself

```bash
# Clone and install
git clone https://github.com/daveremy/deterministic-memory-layer.git
cd deterministic-memory-layer
uv sync

# Run the interactive demo
uv run dml live

# Or run tests
uv run pytest tests/ -v
```

### Architecture (10 seconds)

```
Agent ←→ MCP Tools ←→ EventStore (SQLite)
              ↓
         PolicyEngine (blocks violations)
              ↓
         ReplayEngine (deterministic state)
              ↓
         Weave (observability)
```

### The MCP Tools

| Tool | Purpose |
|------|---------|
| `add_fact` | Record learned information |
| `add_constraint` | Add requirements/rules |
| `record_decision` | Make decisions (auto-checked against constraints) |
| `query_memory` | Search and verify |
| `get_memory_context` | Full state snapshot |
| `trace_provenance` | Explain how facts came to be |
| `time_travel` | View historical state |
| `simulate_timeline` | What-if analysis |

### Technical Highlights

- **124 tests** covering core functionality
- **SQLite + WAL** for concurrent access
- **Monotonic timestamps** for deterministic replay
- **Weave integration** - events are isomorphic to spans
- **MCP server** - standard protocol for AI tool access

### Weave Integration

DML events map directly to observability spans:

| DML Event | Observability Span |
|-----------|-------------------|
| `global_seq` | Span ID |
| `caused_by` | Parent span ID |
| `correlation_id` | Trace ID |
| `type` | Operation name |

This means you can see both "what the LLM did" (Weave) and "what the agent knew" (DML) in one dashboard.

### Links
- [White Paper](WHITE_PAPER.md) - Full technical details
- [FAQ](FAQ.md) - Tough questions and honest answers
- [README](../README.md) - Getting started

### The Self-Improvement Loop

```
Agent makes decision → Decision has bad outcome
                              ↓
                    DML records what happened
                              ↓
                    Agent reviews history (time travel)
                              ↓
                    Agent adds constraint: "Verify X before Y"
                              ↓
                    Next time: Policy blocks Y without X
```

**You can't improve if you can't remember what you did wrong.** DML makes that memory structured, queryable, and enforceable.
