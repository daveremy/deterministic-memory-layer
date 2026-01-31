# DML Development Plan

**Last Updated:** January 31, 2026

---

## Current State Assessment

### What's Built (Phase 0 - Complete)

| Component | Status | Notes |
|-----------|--------|-------|
| **Event Store** | Done | SQLite + WAL, append-only, monotonic timestamps |
| **Projections** | Done | Facts, constraints, decisions with supersession tracking |
| **Replay Engine** | Done | Time travel, counterfactual exclusion |
| **Policy Engine** | Done | Prohibition patterns, procedural "verify before" patterns |
| **Memory API** | Done | search, propose/commit, trace, diff, drift, add_fact, get_fact_history |
| **MCP Server** | Done | 8 tools, proper supersession tracking |
| **Weave Integration** | Done | Optional tracing on all operations |
| **Tests** | Done | 99 tests passing |

### What's Missing for Demo

From `DEMO_DESIGN.md` and `MCP_SERVER_PLAN.md`:

| Gap | Priority | Notes |
|-----|----------|-------|
| Rich terminal UI | High | Main view, flashback mode, timeline split |
| End-to-end Claude test | High | Verify MCP tools work with real agent |
| `dml install` command | Medium | Auto-configure .claude/mcp.json |
| `dml demo` command | Medium | Scripted demo runner |
| Demo video recording | High | Required for submission |

---

## Phase 1: Hackathon Demo (Jan 31 - Feb 1)

**Goal:** Working demo that showcases self-improvement loop + "Fork the Future"

### Saturday Morning: Verification & Polish (3 hours)

| Task | Owner | Time | Notes |
|------|-------|------|-------|
| End-to-end test with Claude | - | 1h | Verify all 8 MCP tools work |
| Fix any blocking issues | - | 1h | Based on E2E test results |
| Create `dml install` command | - | 30m | Auto-configure mcp.json |
| Test full flow: install → use | - | 30m | Fresh environment test |

### Saturday Afternoon: Demo UI (4 hours)

| Task | Owner | Time | Notes |
|------|-------|------|-------|
| Create `visualization.py` | - | 2h | Rich terminal panels |
| Implement main view | - | 30m | Facts/constraints/decisions columns |
| Implement flashback mode | - | 30m | Sepia border, historical state |
| Implement timeline split | - | 1h | Side-by-side A vs B comparison |

**Main View Wireframe:**
```
┌─────────────────────────────────────────────────────────────────┐
│ DML: Self-Improving Travel Agent                        seq: 52 │
├───────────────────┬───────────────────┬─────────────────────────┤
│ FACTS             │ CONSTRAINTS       │ DECISIONS               │
├───────────────────┼───────────────────┼─────────────────────────┤
│ destination: JP   │ ✓ wheelchair req  │ ✗ Ryokan (BLOCKED)     │
│ budget: $3000     │ ★ LEARNED: verify │ ✓ Granvia (VERIFIED)   │
│   ⚠️ was $4000    │   before booking  │                         │
└───────────────────┴───────────────────┴─────────────────────────┘
```

### Saturday Evening: Weave Dashboard (2 hours)

| Task | Owner | Time | Notes |
|------|-------|------|-------|
| Verify Weave traces appear | - | 30m | Check W&B dashboard |
| Add custom tags for Timeline B | - | 30m | Distinguish simulation traces |
| Create decision audit view | - | 1h | Table of seq/decision/status |

### Sunday Morning: Record & Submit (3 hours)

| Task | Owner | Time | Notes |
|------|-------|------|-------|
| Practice demo 3x | - | 1h | Timing, transitions |
| Record demo video | - | 1h | For social media prize |
| Final polish | - | 30m | README, screenshots |
| Submit | - | 30m | Before 1:30 PM deadline |

### Demo Script (6 minutes, 8 acts)

1. **Setup** (30s): User states requirements → facts added
2. **First Decision** (30s): Book ryokan → allowed
3. **The Drift** (30s): Budget changes → drift alert
4. **THE BLOCK** (1m): Wheelchair constraint → booking blocked
5. **THE LEARNING** (30s): Agent adds learned constraint
6. **THE DOUBLE-TAP** (1m): Correct hotel blocked (no verification) → verify → allowed
7. **FORK THE FUTURE** (1m): What if constraint came earlier? → Timeline B
8. **Weave Dashboard** (30s): Show audit trail, drift graph

---

## Phase 2: Post-Hackathon Stabilization (Week 1-2)

**Goal:** Production-ready v1.0 release

### Code Quality

| Task | Priority | Notes |
|------|----------|-------|
| Increase test coverage to 95%+ | High | Edge cases, error paths |
| Add integration tests | High | Full MCP flow tests |
| Performance benchmarks | Medium | Document latency/memory |
| Code review & cleanup | Medium | Remove hackathon shortcuts |

### Documentation

| Task | Priority | Notes |
|------|----------|-------|
| Complete API documentation | High | All public methods |
| Add architecture diagrams | Medium | Visual system overview |
| Create tutorial/quickstart | High | 5-minute getting started |
| Record demo video (polished) | Medium | For GitHub README |

### Distribution

| Task | Priority | Notes |
|------|----------|-------|
| Publish to PyPI | High | `pip install deterministic-memory-layer` |
| Create GitHub releases | Medium | Versioned releases with changelog |
| Docker image | Low | For easy deployment |

---

## Phase 3: Feature Expansion (Month 1-2)

**Goal:** Address limitations identified in reviews and white paper

### Core Enhancements

| Feature | Priority | Complexity | Notes |
|---------|----------|------------|-------|
| **Semantic constraint matching** | High | High | Embeddings for "be respectful" → matches violations |
| **Fact key normalization** | High | Medium | Schema conventions, auto-normalization |
| **Snapshot checkpoints** | Medium | Medium | O(1) state reconstruction for long histories |
| **Constraint conflict detection** | Medium | Medium | Warn when constraints contradict |

### Storage Backends

| Feature | Priority | Complexity | Notes |
|---------|----------|------------|-------|
| **Redis Streams backend** | High | Medium | Production scalability |
| **PostgreSQL backend** | Medium | Medium | Enterprise deployments |
| **In-memory backend** | Low | Low | Testing, ephemeral use |

### Developer Experience

| Feature | Priority | Complexity | Notes |
|---------|----------|------------|-------|
| **Web dashboard** | Medium | High | Visual memory explorer |
| **VS Code extension** | Low | Medium | Inline memory visualization |
| **Jupyter integration** | Low | Low | Memory introspection in notebooks |

---

## Phase 4: Advanced Capabilities (Month 3-6)

**Goal:** Research directions from white paper

### Entity Modeling

| Feature | Description |
|---------|-------------|
| **Structured entities** | Group facts: `user.budget`, `user.preferences` → `user` entity |
| **Entity relationships** | `user` → `trip` → `bookings` graph |
| **Schema enforcement** | Optional typing for fact values |

### Multi-Agent Support

| Feature | Description |
|---------|-------------|
| **Shared memory spaces** | Multiple agents read/write same store |
| **Agent namespacing** | Per-agent fact isolation with shared constraints |
| **Conflict resolution** | Strategies for concurrent writes |

### Distributed Systems

| Feature | Description |
|---------|-------------|
| **Event streaming** | Kafka/Redis Streams for real-time sync |
| **Federation** | Share constraints across organizations |
| **Offline support** | Local-first with sync on reconnect |

### Privacy & Security

| Feature | Description |
|---------|-------------|
| **Crypto-shredding** | GDPR-compliant "forgetting" |
| **Differential privacy** | Aggregate analytics without exposure |
| **Audit log integrity** | Hash chains for tamper detection |

---

## Phase 5: Research Frontiers (6+ months)

These are speculative directions that may or may not be pursued:

| Direction | Description | Dependency |
|-----------|-------------|------------|
| **Formal verification** | Prove constraint systems can't deadlock | Academic collaboration |
| **Model training integration** | Use event logs as training signal | Research partnership |
| **Semantic fact matching** | Detect equivalent facts with different keys | Embedding infrastructure |
| **Branch and merge** | Git-like branching for agent reasoning | Significant R&D |
| **World model projection** | Synthesize coherent entities from partial facts | Entity modeling complete |

---

## Success Metrics

### Hackathon (Phase 1)

- [ ] Demo runs without crashes
- [ ] "Fork the Future" moment lands (audible reaction)
- [ ] Weave dashboard shows meaningful traces
- [ ] Judges understand value in <30 seconds

### v1.0 Release (Phase 2)

- [ ] 95%+ test coverage
- [ ] <100ms latency for all operations
- [ ] Zero critical bugs in 2 weeks of use
- [ ] 10+ GitHub stars

### Adoption (Phase 3-4)

- [ ] 100+ PyPI downloads/month
- [ ] 3+ production deployments
- [ ] 1+ academic citation
- [ ] Community contributions

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Demo fails live | Pre-record backup video |
| Claude doesn't use tools correctly | Extensive system prompt tuning |
| Weave integration breaks | Have screenshots as backup |
| Over-engineering | Timebox each task strictly |
| Scope creep | Explicit "cut if needed" list |

### Cut If Needed (Hackathon)

1. Multiple demo scenarios (one clean demo is enough)
2. Fancy Weave visualizations (audit table sufficient)
3. Complex constraint priorities
4. Polish UI animations

---

## Appendix: File Structure

```
deterministic-memory-layer/
├── dml/
│   ├── __init__.py
│   ├── __main__.py          # python -m dml
│   ├── cli.py               # CLI commands
│   ├── server.py            # MCP server
│   ├── events.py            # Event types + store
│   ├── projections.py       # Fact/constraint/decision projections
│   ├── replay.py            # Replay engine
│   ├── policy.py            # Constraint enforcement
│   ├── memory_api.py        # Agent-facing API
│   ├── tracing.py           # Weave integration
│   └── visualization.py     # Rich terminal UI (NEW)
├── prompts/
│   ├── travel_agent.md      # System prompt
│   ├── tool_examples.md     # Usage examples
│   └── workflows.md         # Common patterns
├── docs/
│   ├── DEV_PLAN.md          # This file
│   ├── WHITE_PAPER.md       # Technical paper
│   ├── DEMO_DESIGN.md       # Demo script
│   ├── MCP_SERVER_PLAN.md   # Server implementation
│   └── FAQ.md               # Q&A
├── tests/
│   └── (99 tests)
├── demo.py                  # Demo runner
└── pyproject.toml
```

---

## References

- [DEMO_DESIGN.md](DEMO_DESIGN.md) - Detailed demo script and visuals
- [MCP_SERVER_PLAN.md](MCP_SERVER_PLAN.md) - MCP tool specifications
- [WHITE_PAPER.md](WHITE_PAPER.md) - Technical architecture and future research
- [WeaveHacks 3](https://lu.ma/weavehacks3) - Hackathon details
