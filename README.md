# Deterministic Memory Layer (DML)

**Event-driven memory for reliable, self-improving AI agents.**

---

## Table of Contents

- [Demo](#demo)
- [The Idea](#the-idea)
- [The Problem](#the-problem)
- [The Approach](#the-approach)
- [How It Works](#how-it-works)
  - [Event-Driven Memory](#event-driven-memory)
  - [Self-Improvement Loop](#self-improvement-loop)
  - [Policy Enforcement](#policy-enforcement)
- [Architecture](#architecture)
  - [Core Components](#core-components)
  - [Protocol Integration (MCP)](#protocol-integration-mcp)
  - [Observability Integration](#observability-integration)
- [Getting Started](#getting-started)
  - [Installation](#installation)
  - [Quick Example](#quick-example)
  - [CLI Commands](#cli-commands)
- [Documentation](#documentation)
- [Project Structure](#project-structure)
- [Acknowledgments](#acknowledgments)

---

## Demo

Watch DML in action with live Claude sessions:

### Quick Demo: Dinner Party Planning
[![asciicast](https://asciinema.org/a/poksmLtZA784MzjQ.svg)](https://asciinema.org/a/poksmLtZA784MzjQ)

Facts captured from natural conversation, fact updates with history preserved, constraints from casual mentions, and provenance queries showing change history.

### Japan Trip: Accessibility Constraints
[![asciicast](https://asciinema.org/a/bjXwcMZumtnlBw5J.svg)](https://asciinema.org/a/bjXwcMZumtnlBw5J)

Constraint-aware reasoning catches a conflict between a traditional ryokan booking and wheelchair accessibility requirements. Shows explainability and counterfactual analysis.

### Product Launch: Complex Planning (Advanced)
[![asciicast](https://asciinema.org/a/raqQkjB2bOSlrBqp.svg)](https://asciinema.org/a/raqQkjB2bOSlrBqp)

Multi-phase scenario with evolving budget, dates, and constraints. Shows drift analysis, provenance traces, and counterfactual "what if" analysis across 15 prompts.

### Clinical: High-Stakes Decision Support
[![asciicast](https://asciinema.org/a/C7MG4qOxXLdi4GZc.svg)](https://asciinema.org/a/C7MG4qOxXLdi4GZc)

Drug allergy constraint prevents dangerous prescription. Shows how structured memory catches conflicts that conversation context might miss.

---

## The Idea

LLMs are inherently stochastic—you can't make their outputs deterministic. But **memory is a different substrate**. The facts an agent knows, the constraints it operates under, the relationships it tracks—these don't need to be a blob appended to context. They can be structured, versioned, and deterministic.

Current approaches treat agent memory as unstructured text optimized for retrieval. DML explores whether treating memory as a **first-class system**—with its own guarantees—improves agent reliability.

---

## The Problem

AI agents are moving from experiments to production, but current memory architectures have fundamental limitations:

| Problem | Description |
|---------|-------------|
| **Memory Drift** | Agent state gradually diverges from intended behavior as contradictions accumulate undetected |
| **Non-Reproducibility** | Can't debug what you can't replay—reproducing the exact state that led to a decision is often impossible |
| **Accountability Gap** | When agents make autonomous decisions, organizations can't answer "why did it do that?" |
| **No Learning Loop** | Mistakes aren't captured as prevention mechanisms; agents repeat the same errors |

Existing memory systems (MemGPT/Letta, Mem0, A-Mem, LangChain Memory) focus on *retrieval*—how to find relevant memories. DML focuses on *reliability*—how to ensure memories are consistent, auditable, and enforceable.

---

## The Approach

DML uses **event-driven memory**—inspired by event sourcing patterns in distributed systems:

- **Events are the source of truth**: Current state is derived by replaying events, not stored directly
- **Append-only**: Events are never modified or deleted; corrections create new events
- **Deterministic replay**: Same events always produce the same state

This enables capabilities that mutable memory cannot provide:

| Capability | Description |
|------------|-------------|
| **Time Travel** | Replay to the exact memory state when any decision was made |
| **Provenance** | Trace any fact back through the chain of events that established it |
| **Counterfactuals** | "What if this constraint existed earlier?" - replay with modifications |
| **Audit Trail** | Complete history of every memory change, forever |

---

## How It Works

### Event-Driven Memory

Every memory operation is recorded as an immutable event:

```python
# Events capture what happened, not current state
Event(type=FactAdded, payload={"key": "user.budget", "value": 3000})
Event(type=ConstraintAdded, payload={"text": "Verify accessibility before booking hotels"})
Event(type=DecisionMade, payload={"action": "book_hotel", "rationale": "..."})
```

Current state is always derived by replaying events through projections:

```python
# Replay events to get current state
engine = ReplayEngine(event_store)
state = engine.replay_to(seq=50)  # State at event 50

# Or exclude events for counterfactual analysis
alt_state = engine.replay_excluding([42, 43])  # "What if events 42-43 never happened?"
```

### Self-Improvement Loop

DML enables a closed loop from mistake to prevention:

```text
Agent makes decision → Decision has bad outcome
                              ↓
                    DML records what happened (event)
                              ↓
                    Agent reviews history (replay)
                              ↓
                    Agent adds constraint: "Verify X before Y"
                              ↓
                    Next time: Policy blocks Y without X
```

Constraints are themselves events—the agent's learned rules become part of its auditable history.

### Policy Enforcement

The policy engine intercepts every memory write and checks it against active constraints:

```python
# Constraint: "Never recommend products containing nuts"
# Attempted write: "Recommend trail mix for the hiking trip"

result = policy_engine.check(proposed_write, active_constraints)
# result.allowed = False
# result.violated = ["Never recommend products containing nuts"]
```

**Constraint Types**:
- **Required**: Always enforced (e.g., "Never share personal data")
- **Preferred**: Advisory, not blocking (e.g., "Prefer morning meetings")
- **Learned**: Added from past mistakes, enforced going forward

**Pattern Detection**:
- Prohibition: "never X", "do not X", "avoid X" → blocks writes containing X
- Procedural: "verify X before Y" → requires X was queried before Y proceeds

---

## Architecture

### Core Components

```text
┌─────────────────────────────────────────────────────────────────┐
│                         Agent (Claude, etc.)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ MCP Tools
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         DML Server                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  MemoryAPI  │  │   Policy    │  │   Replay    │             │
│  │             │  │   Engine    │  │   Engine    │             │
│  │ • search    │  │             │  │             │             │
│  │ • propose   │  │ • check     │  │ • replay_to │             │
│  │ • commit    │  │ • enforce   │  │ • excluding │             │
│  │ • trace     │  │             │  │ • inject    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│         │                │                │                     │
│         └────────────────┴────────────────┘                     │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Event Store                           │   │
│  │            (SQLite + WAL / Redis Streams)                │   │
│  │                                                          │   │
│  │  [Event 1] → [Event 2] → [Event 3] → ... (append-only)  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Spans (isomorphic)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Observability (Weave, etc.)                    │
└─────────────────────────────────────────────────────────────────┘
```

| Component | Purpose |
|-----------|---------|
| **Event Store** | Append-only storage for immutable events (SQLite default, Redis planned) |
| **Projection Engine** | Derives current state (facts, constraints, decisions) from events |
| **Replay Engine** | Reconstructs state at any point; supports counterfactual analysis |
| **Policy Engine** | Enforces constraints on every write; blocks violations |
| **Memory API** | Agent-facing interface for search, propose, commit, trace, diff |

### Protocol Integration (MCP)

DML is designed as an **MCP server**—it provides tools that AI agents can call.

**What is MCP?** The [Model Context Protocol](https://modelcontextprotocol.io/) (Anthropic) is a standard for connecting AI agents to external tools and data sources. When an agent needs to access a database, API, or service, MCP provides the interface.

**DML MCP Tools**:

| Tool | Description |
|------|-------------|
| `memory.add_fact` | Record a fact with confidence score |
| `memory.add_constraint` | Add a behavioral constraint |
| `memory.decide` | Record a decision with rationale |
| `memory.query` | Search memory for relevant facts |
| `memory.replay` | Reconstruct state at a specific point |

**Future Protocol Support**: As agent ecosystems evolve, DML could integrate with agent-to-agent protocols like [A2A](https://github.com/google/a2a) (Google/Linux Foundation) for multi-agent memory sharing scenarios.

### Observability Integration

DML events are **structurally isomorphic to distributed tracing spans**:

| DML Event | Observability Span |
|-----------|-------------------|
| `global_seq` | Span ID |
| `caused_by` | Parent span ID |
| `correlation_id` | Trace ID |
| `type` | Operation name |
| `payload` | Span attributes |

This means DML integrates naturally with observability platforms like [Weights & Biases Weave](https://wandb.ai/site/weave). When enabled, every event append becomes a span, constraint violations become errors, and the full memory operation history is visible in your tracing dashboard.

**Together, they answer different questions**:
- Observability: "What did the LLM do?" (calls, latencies, token usage)
- DML: "What did the agent know?" (facts, constraints, decisions)

---

## Getting Started

### Installation

DML requires Python 3.11+ and uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Clone the repository
git clone https://github.com/daveremy/deterministic-memory-layer.git
cd deterministic-memory-layer

# Install dependencies
uv sync

# (Alternative: pip install)
pip install -e .
```

### Quick Example

```python
from dml import EventStore, Event, EventType, ReplayEngine, PolicyEngine, MemoryAPI

# Initialize
store = EventStore("agent_memory.db")
memory = MemoryAPI(store)

# Add a constraint (recorded as event)
memory.add_constraint("Never recommend products containing nuts", priority="required")

# Add facts
memory.add_fact("user.allergy", "tree nuts", confidence=1.0)
memory.add_fact("user.preference", "healthy snacks", confidence=0.8)

# Propose a write - policy engine checks constraints
proposal_id, violations = memory.propose_writes([
    {"type": "recommendation", "content": "Try our new trail mix!"}
])

if violations:
    print(f"Blocked: {violations}")  # ["Never recommend products containing nuts"]
else:
    memory.commit_writes(proposal_id)

# Time travel: what was the state at event 5?
replay = ReplayEngine(store)
past_state = replay.replay_to(seq=5)

# Provenance: why does the agent believe this?
chain = memory.trace_provenance("user.allergy")
# Returns: [Event that established the fact, Event that caused it, ...]
```

### CLI Commands

```bash
# Initialize a new memory store
python -m dml init

# Add events
python -m dml append FactAdded '{"key": "user.name", "value": "Alice"}'
python -m dml append ConstraintAdded '{"text": "Always greet by name"}'

# View current state
python -m dml replay

# Time travel to specific point
python -m dml replay --to 5

# Counterfactual: state without events 3 and 5
python -m dml replay --exclude 3,5

# Search memory
python -m dml query "user preferences"

# Trace provenance
python -m dml trace user.name

# Compare states
python -m dml diff 10 20

# Measure drift
python -m dml drift 1 100

# Run demo scenario
python demo.py

# Run tests
pytest tests/ -v
```

---

## Documentation

### Core Documents

| Document | Description |
|----------|-------------|
| **[Judge Guide](docs/JUDGE_GUIDE.md)** | Quick 2-minute overview for hackathon judges |
| **[White Paper](docs/WHITE_PAPER.md)** | Full technical paper: architecture, implementation, evaluation, future research |
| **[FAQ](docs/FAQ.md)** | Tough questions and honest answers about claims, limitations, trade-offs |

### Supporting Materials

| Document | Description |
|----------|-------------|
| **[Research Notes](docs/RESEARCH_NOTES.md)** | Literature review and references |
| **[Demo Design](docs/DEMO_DESIGN.md)** | Demo scenario walkthrough |
| **[CLAUDE.md](CLAUDE.md)** | Development instructions |

---

## Project Structure

```text
deterministic-memory-layer/
├── dml/
│   ├── events.py        # Event types + SQLite EventStore
│   ├── stores.py        # Store backend abstraction (SQLite, Redis stub)
│   ├── projections.py   # Fact/Constraint/Decision projections
│   ├── replay.py        # Deterministic replay engine
│   ├── policy.py        # Constraint enforcement
│   ├── memory_api.py    # Agent-facing API
│   ├── tracing.py       # Observability integration (Weave)
│   └── server.py        # MCP server
├── docs/
│   ├── WHITE_PAPER.md   # Technical paper
│   ├── FAQ.md           # Questions and answers
│   ├── RESEARCH_NOTES.md
│   └── DEMO_DESIGN.md
├── tests/               # 124 tests covering core functionality
├── demo.py              # Demo scenario
└── pyproject.toml
```

---

## Acknowledgments

Built during [WeaveHacks 3](https://lu.ma/weavehacks3) (Jan 31 - Feb 1, 2026), sponsored by:
- [Weights & Biases](https://wandb.ai/) (Weave) - Observability integration
- [Redis](https://redis.io/) - Event store backend design
- [Daily](https://www.daily.co/) (Pipecat)
- [Browserbase](https://browserbase.com/)

---

## License

MIT
