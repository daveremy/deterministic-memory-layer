# Deterministic Memory Layer (DML)

**Event-driven memory for reliable, self-improving AI agents.**

Built for [WeaveHacks 3](https://lu.ma/weavehacks3) (Jan 31 - Feb 1, 2026)

## The Idea

LLMs are inherently stochastic—you can't make their outputs deterministic. But **memory is a different substrate**. The facts an agent knows, the constraints it operates under, the relationships it tracks—these don't need to be a blob appended to context. They can be structured, versioned, and deterministic.

Current approaches treat agent memory as unstructured text for retrieval. DML explores whether treating memory as a **first-class system**—with its own guarantees—improves reliability:

- **Reproducibility**: Replay to the exact memory state when a decision was made
- **Accountability**: Trace why the agent believed a specific fact
- **Consistency**: Detect contradictions before they cause problems
- **Learning**: Turn mistakes into constraints that prevent recurrence

## The Approach

DML uses **event-driven memory**—adapting event sourcing from distributed systems. Facts, constraints, and decisions are recorded as immutable events. Current state is always derived by replaying events.

**Core capabilities:**

1. **Deterministic Replay**: Same events → same state (always)
2. **Policy Enforcement**: Check constraints on every write
3. **Self-Improvement**: Learn constraints from mistakes
4. **Counterfactual Analysis**: "What if this constraint existed earlier?"
5. **Provenance Tracking**: Trace any fact to its origin

## Self-Improvement Loop

DML enables a closed loop from mistake to prevention:

```text
Agent makes decision → Decision has bad outcome
                              ↓
                    DML records what happened
                              ↓
                    Agent reviews history (replay)
                              ↓
                    Agent adds constraint: "Verify X before Y"
                              ↓
                    Next time: Policy blocks Y without X
```

Structured memory makes this possible—you can't improve if you can't remember what went wrong.

## Quick Start

```bash
# Install
uv sync

# Initialize memory store
python cli.py init

# Add a constraint
python cli.py append ConstraintAdded '{"text": "Never use eval()"}'

# View current state
python cli.py replay

# Run the demo
python demo.py

# Run tests (80 tests)
pytest tests/
```

## Architecture

```text
┌─────────────────┐     MCP Tools      ┌─────────────────┐
│                 │ ◄────────────────► │                 │
│  Claude/Agent   │  memory.add_fact   │   DML Server    │
│                 │  memory.constrain  │                 │
│                 │  memory.decide     │  Event Store    │
└─────────────────┘  memory.query      └────────┬────────┘
                                                │
                                         Events │ (append-only)
                                                ▼
┌─────────────────┐                    ┌─────────────────┐
│  Observability  │ ◄───── spans ───── │   Projections   │
│  (Weave, etc.)  │                    ├─────────────────┤
│                 │                    │ • Facts         │
│  Events ≅ Spans │                    │ • Constraints   │
└─────────────────┘                    │ • Decisions     │
                                       └─────────────────┘
```

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Event** | Immutable record of something that happened (fact learned, constraint added, decision made) |
| **Projection** | Current state derived from replaying events |
| **Policy** | Rules that gate commits (reject decisions violating constraints) |
| **Provenance** | Chain of `caused_by` links tracing state to origin |
| **Constraint** | Required, preferred, or learned rule governing behavior |

## Observability Integration

DML events are **isomorphic to distributed tracing spans**:

| DML Event | Observability Span |
|-----------|-------------------|
| `global_seq` | Span ID |
| `caused_by` | Parent span ID |
| `correlation_id` | Trace ID |
| `type` | Operation name |
| `payload` | Span attributes |

This enables unified visibility: observability tools trace LLM behavior, DML tracks memory state—together, full visibility into both what the agent did and what it knew.

## Project Structure

```
deterministic-memory-layer/
├── dml/
│   ├── events.py        # Event types + SQLite EventStore
│   ├── stores.py        # Store backends (SQLite, Redis stub)
│   ├── projections.py   # Fact/Constraint/Decision projections
│   ├── replay.py        # Deterministic replay engine
│   ├── policy.py        # Constraint enforcement
│   ├── memory_api.py    # Agent-facing API
│   ├── tracing.py       # Observability integration
│   └── server.py        # MCP server
├── cli.py               # CLI interface
├── demo.py              # Demo scenario
├── docs/                # Documentation
└── tests/               # 80 tests
```

## CLI Commands

```
dml init                    Create new memory store
dml append <type> <json>    Add event
dml replay [--to N]         Show state at point in time
dml replay --exclude 3,5    Counterfactual: state without events 3 and 5
dml query <search>          Search facts
dml trace <key>             Show provenance chain
dml diff <seq1> <seq2>      Compare states
dml drift <seq1> <seq2>     Measure drift metrics
dml eval                    Run evaluation workflow
```

## Documentation

### Core Documents
- **[White Paper](docs/WHITE_PAPER.md)** - Full technical paper on DML architecture, implementation, and future research directions
- **[FAQ](docs/FAQ.md)** - Tough questions and honest answers about DML's claims, limitations, and trade-offs

### Supporting Materials
- **[Research Notes](docs/RESEARCH_NOTES.md)** - Literature review and references supporting the white paper
- **[Demo Design](docs/DEMO_DESIGN.md)** - Demo scenario design and walkthrough
- **[CLAUDE.md](CLAUDE.md)** - Project instructions for Claude Code
- **[agents.md](agents.md)** - Headless AI assistant integration guide

## Key Features

- **Event Sourcing**: All mutations captured as immutable events
- **Deterministic Replay**: Rebuild state from any point in history
- **Policy Enforcement**: Block constraint violations before commit
- **Procedural Constraints**: "Verify X before Y" enforcement
- **Counterfactual Analysis**: "What if this constraint existed?"
- **Provenance Tracking**: Trace any fact to its origin
- **Drift Measurement**: Quantify state changes over time
- **Observability**: Event-span isomorphism for unified tracing
- **Pluggable Backends**: SQLite (default), Redis (planned)

## Acknowledgments

Built during WeaveHacks 3, sponsored by:
- [Weights & Biases](https://wandb.ai/) (Weave)
- [Redis](https://redis.io/)
- [Daily](https://www.daily.co/) (Pipecat)
- [Browserbase](https://browserbase.com/)

## License

MIT
