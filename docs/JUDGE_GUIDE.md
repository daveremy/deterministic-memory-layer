# DML: Deterministic Memory Layer
## Quick Guide for Hackathon Judges

### What It Does (30 seconds)
DML gives AI agents **structured, auditable memory** instead of a growing text blob.

- **Event-sourced**: Every fact, constraint, and decision is an immutable event
- **Deterministic**: Replay events → get same state every time
- **Self-improving**: Agent learns constraints from mistakes, enforced automatically

### The Demo (2 minutes)
Watch a travel agent that:
1. Learns user requirements (budget, destination, accessibility)
2. Makes a booking mistake (misses accessibility requirement)
3. Gets corrected → adds a "learned constraint"
4. Future bookings are **automatically blocked** if they skip verification
5. "Fork the Future" shows what would have happened with earlier constraint

### Key Moments to Watch

| Moment | What Happens | Why It Matters |
|--------|--------------|----------------|
| BLOCKED decision | Policy rejects booking | Constraints enforced in real-time |
| Learned constraint | Agent adds rule from mistake | Self-improvement loop |
| Timeline B | Counterfactual simulation | Proves determinism |
| Provenance trace | Shows reasoning chain | Full auditability |
| Drift alert | Fact changed mid-conversation | Catches contradictions |

### Try It Yourself

```bash
# Install
pip install deterministic-memory-layer

# Configure Claude Code
dml install

# Start the MCP server
dml serve --init

# In another terminal, use Claude Code with DML
claude
```

### Architecture (10 seconds)

```
Agent ←→ MCP Tools ←→ EventStore (SQLite)
              ↓
         PolicyEngine (blocks violations)
              ↓
         ReplayEngine (deterministic state)
```

### The 8 Tools

| Tool | Purpose |
|------|---------|
| `add_fact` | Record learned information |
| `add_constraint` | Add requirements/rules |
| `record_decision` | Make decisions (auto-checked) |
| `query_memory` | Search and verify |
| `get_memory_context` | Full state snapshot |
| `trace_provenance` | Explain reasoning |
| `time_travel` | View historical state |
| `simulate_timeline` | What-if analysis |

### Technical Highlights

- **75+ tests** covering core functionality
- **SQLite + WAL** for concurrent access
- **Monotonic timestamps** for deterministic replay
- **Strict regex** for constraint matching
- **Event-driven verification** tracking

### Links
- [Full Demo Design](DEMO_DESIGN.md)
- [MCP Server Plan](MCP_SERVER_PLAN.md)
- [README](../README.md)

### Self-Improving Loop

```
Agent makes decision → Decision has bad outcome
                              ↓
                    DML records what happened
                              ↓
                    Agent reviews history (time travel)
                              ↓
                    Agent adds constraint: "Don't do X"
                              ↓
                    Next time: Policy blocks X before it happens
```

**You can't improve if you can't remember what you did wrong.** DML makes that memory structured and queryable.
