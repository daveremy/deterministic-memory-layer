# Deterministic Memory Layer: Reliable AI Agents Through Event-Driven Memory

**Version 1.0 | January 2026**

---

## Abstract

Large language model (LLM) agents increasingly operate autonomously, making decisions that affect users, systems, and organizations. Yet current agent memory architectures suffer from fundamental limitations: state drift over time, contradictory memories, non-reproducible behavior, and lack of accountability for decisions. We present the **Deterministic Memory Layer (DML)**, a framework for building reliable, self-improving AI agents. DML achieves its goals through **event-driven memory**—a mechanism where agent memory is stored as an immutable stream of events from which state is deterministically reconstructed. This approach, adapted from proven distributed systems patterns, enables agents that are auditable, debuggable, and reliably self-improving. DML extends event-driven memory with integrated policy enforcement, self-improvement through learned constraints, and counterfactual analysis. Our implementation demonstrates constraint enforcement with negligible overhead and provides MCP tools for seamless integration with Claude Code and other AI systems.

**Key Terms**: *DML (Deterministic Memory Layer)* is the framework for reliable agent memory. *Event-driven memory* is the underlying mechanism—storing memory as an immutable event stream rather than mutable state. *Projections* are derived views of current state reconstructed from events. *Constraints* are rules (required, preferred, or learned) that govern agent behavior.

---

## 1. Introduction

### 1.1 The Agent Memory Problem

AI agents powered by large language models are transitioning from experimental tools to production systems. Organizations deploy agents for customer service, code generation, research assistance, and autonomous task execution. These agents must maintain context across sessions, remember user preferences, and make decisions consistent with established constraints.

However, current agent memory approaches face critical limitations:

**Memory Drift**: Agent performance gradually declines as data evolves, models change, and user patterns shift. Without explicit tracking, agents accumulate contradictory information and diverge from intended behavior.

**Hallucination and Contradiction**: LLMs generate responses that can contradict previously established facts. When Air Canada's chatbot provided incorrect refund information, the company faced legal consequences. Such failures stem from memory systems that cannot enforce consistency.

**Non-Reproducibility**: Debugging agent behavior requires reproducing the exact state that led to a decision. Yet studies report that a majority of AI researchers struggle to reproduce results, even within the same subfield [9]. Traditional debugging assumes deterministic execution—an assumption that fails for most AI systems.

**Accountability Gap**: When agents make autonomous decisions, organizations need clear audit trails. Industry surveys report that most security leaders struggle to audit AI-driven decisions. Without provenance tracking, explaining *why* an agent made a particular choice becomes impossible.

### 1.2 Current Approaches and Their Limitations

Existing agent memory architectures focus primarily on *retrieval*—how to efficiently find relevant memories—rather than *reliability*—how to ensure memories are consistent, auditable, and enforceable.

**MemGPT** (now Letta) pioneered the "operating system" metaphor for agent memory, with hierarchical storage mimicking RAM and disk. While innovative for managing context limits, it maintains mutable state without deterministic reconstruction.

**Mem0** achieves strong retrieval performance through incremental summarization and graph-based memory [4]. However, it focuses on efficiency rather than constraint enforcement or auditability.

**A-Mem** introduces "agentic memory" with dynamic self-organization inspired by the Zettelkasten method. Memories evolve and link autonomously. Yet this evolution is not deterministic—replaying the same inputs may produce different memory structures.

**LangChain Memory** provides semantic, procedural, and episodic memory types with vector-based retrieval. While developer-friendly, it offers no mechanism for policy enforcement or state reconstruction.

None of these systems provide:
- Append-only immutable event logs
- Deterministic state reconstruction from events
- Integrated policy enforcement on memory writes
- Self-improvement through learned constraints
- Counterfactual analysis capabilities

### 1.3 Our Contribution

We present the **Deterministic Memory Layer (DML)**, a framework for building reliable, accountable AI agents. DML addresses the core problems of drift, hallucination, non-reproducibility, and lack of accountability through a unified architecture.

DML achieves these goals through **event-driven memory**—a mechanism adapted from distributed systems where:

- The **event log is the source of truth**—current state is derived, not stored
- **Replay is deterministic**—same events always produce the same state
- **Nothing is lost**—every change is preserved for audit and analysis

DML extends event-driven memory with capabilities specific to AI agents:

1. **Deterministic State Reconstruction**: Append-only event log enables exact replay to any point in history
2. **Policy Enforcement**: Constraints are checked on every write; violations are blocked before they occur
3. **Self-Improvement**: Agents learn constraints from mistakes, preventing recurrence
4. **Counterfactual Analysis**: "What if" queries replay events with modifications to understand alternate outcomes
5. **MCP Integration**: Native tools for Claude Code and other MCP-compatible systems

The key insight is that **event-driven memory is the mechanism** that enables DML to deliver reliable, auditable, self-improving agents.

---

## 2. Background and Related Work

### 2.1 Event Sourcing in Distributed Systems

Event sourcing is an architectural pattern where application state is derived from a sequence of immutable events rather than stored directly. First popularized in domain-driven design and financial systems, event sourcing provides:

- **Complete Audit Trail**: Every change is recorded; nothing is lost
- **Temporal Queries**: Reconstruct state at any historical point
- **Debugging**: Replay events to reproduce bugs deterministically
- **Scalability**: Append-only writes are highly performant

The pattern separates the "command" (write) and "query" (read) sides of applications—known as CQRS (Command Query Responsibility Segregation). This separation enables independent scaling and allows the read model to be regenerated from the event log if corrupted.

Recent industry recognition confirms event sourcing's relevance to AI. As noted by Akka:

> "Event sourcing isn't just a data persistence pattern—it's a paradigm shift that aligns perfectly with the needs of agentic AI. By treating state as a series of immutable events, event sourcing enables AI agents to reason about past actions, learn from historical context, and rewind or replay decisions with full traceability."

### 2.2 Guardrails and Policy Enforcement

The AI safety community has developed "guardrails"—validation layers that constrain agent behavior. NVIDIA NeMo Guardrails uses a domain-specific language (Colang) to define dialogue flows and safety constraints. Guardrails AI provides structural and type guarantees on LLM outputs.

Recent research on "Policy-as-Prompt" demonstrates automatic conversion of governance documents into enforceable constraints [2]. The MCP Guardrail Framework integrates policy checks directly into tool calls with only 8-13ms overhead [10].

A critical insight from the security community:

> "Never let the LLM decide what actions are allowed. The server enforces the rules."

DML adopts this principle: constraints are enforced by the memory layer itself, not by the LLM's self-restraint.

### 2.3 Self-Improving Agents

The NeurIPS 2025 research cluster on self-improving agents identifies a key challenge: enabling agents to learn from mistakes while operating within safety bounds. The concept of "bounded learning" captures this:

> "Agents adapt and improve within established guardrails. Instead of allowing unlimited experimentation that could lead to unpredictable behaviors, agents learn to optimize their performance within proven flow structures."

Research on self-correction (STaSC) and self-challenging agents shows that LLMs can generate their own training data from failures. DML operationalizes this insight: when an agent violates a constraint, it can add a "learned constraint" that prevents recurrence.

### 2.4 Constraint Violations in Autonomous Agents

The ODCV-Bench benchmark reveals how agents violate constraints under optimization pressure. Three violation types were identified:

- **Metric Gaming**: Exploiting validation loopholes
- **Active Falsification**: Modifying ground-truth data
- **Systemic Fraud**: Rewriting validation scripts

Alarmingly, agents demonstrated "deliberative misalignment"—correctly identifying their own unethical actions during review while still executing them under KPI pressure.

The benchmark recommends "process-based supervision" over outcome-based evaluation. DML implements this through procedural constraints that enforce verification before action.

### 2.5 Counterfactual Reasoning

Counterfactual reasoning—analyzing "what if" scenarios—is increasingly recognized as essential for AI explainability and safety. Applications include:

- **Explainability**: Understanding why a model made a decision
- **Fairness Auditing**: Testing whether decisions would differ with changed attributes
- **Optimization**: Testing strategies without real-world risk

Gartner predicts causal AI will have "high impact" within 2-5 years, with nearly 70% of AI-driven organizations incorporating causal reasoning by 2026. DML provides counterfactual capabilities through its replay mechanism—events can be selectively excluded or modified to explore alternate timelines.

---

## 3. Architecture

DML is built on six core principles, implemented through event-driven memory as the underlying mechanism.

### 3.1 Design Principles

1. **Append-Only**: Events are never modified or deleted; corrections create new events
2. **Deterministic Replay**: Given the same event sequence, state reconstruction is identical
3. **Provenance Tracking**: Every fact traces to its originating event
4. **Explicit Constraints**: Rules are recorded as events, not embedded in code
5. **Policy on Write**: Every write is checked against active constraints
6. **Self-Improvement**: Agents can add constraints learned from mistakes

### 3.2 Event-Driven Memory (The Mechanism)

DML achieves its goals through event-driven memory—an adaptation of event sourcing from distributed systems. Instead of storing current state, DML stores a sequence of immutable events:

- **Events are the source of truth**: Current state is always derived by replaying events
- **Nothing is lost**: Every change is preserved, enabling full audit trails
- **Replay is deterministic**: Same events always produce the same state

### 3.3 Event Model

DML defines a set of event types that capture agent memory operations:

| Event Type | Description |
|------------|-------------|
| `FactAdded` | Agent learned a new fact (key-value with confidence) |
| `ConstraintAdded` | New constraint established (required/preferred/learned) |
| `ConstraintDeactivated` | Constraint no longer applies |
| `DecisionMade` | Agent made a decision (with rationale and references) |
| `MemoryQueryIssued` | Agent queried memory (for verification tracking) |
| `MemoryWriteProposed` | Agent proposed a memory write |
| `MemoryWriteCommitted` | Write passed policy and was committed |

Each event includes:
- **global_seq**: Monotonically increasing sequence number
- **timestamp**: Monotonic counter (not wall-clock, for determinism)
- **type**: Event type from the enumeration
- **payload**: Event-specific data
- **caused_by**: Sequence of the event that caused this one
- **correlation_id**: Groups related events for provenance

### 3.4 Projections

Current state is derived from events through "projections"—pure functions that fold events into state:

```
ProjectionState:
  - facts: Dict[key, FactProjection]
  - constraints: Dict[text, ConstraintProjection]
  - decisions: List[DecisionProjection]
  - pending_verifications: Set[topic]
```

The `pending_verifications` set tracks which topics have been verified via memory queries, enabling procedural constraint enforcement.

### 3.5 Policy Engine

The policy engine intercepts every memory write and checks it against active constraints:

**Prohibition Patterns**: Constraints containing "never", "do not", or "avoid" block writes containing the forbidden term. Word-boundary matching prevents false positives (e.g., "avoid cat" does not match "concatenate").

**Procedural Patterns**: Constraints matching "verify X before Y" require that topic X was queried before action Y can proceed. If the agent attempts to book a hotel without first querying accessibility requirements, the write is blocked.

**Constraint Priorities**:
- `required`: Always enforced
- `learned`: Enforced (added from past mistakes)
- `preferred`: Not enforced, advisory only

### 3.6 Self-Improvement Loop

When an agent encounters a problem—a user correction, an error, or unexpected behavior—it can add a "learned" constraint:

1. Agent makes mistake (e.g., books non-accessible room)
2. User provides feedback
3. Agent adds learned constraint: "Verify accessibility before booking"
4. Constraint is recorded as event with `triggered_by` linking to the mistake
5. Future decisions automatically checked against this constraint

This creates a closed loop where mistakes become prevention mechanisms.

### 3.7 Counterfactual Analysis

DML's replay engine supports counterfactual queries:

- **Time Travel**: `replay_to(seq)` reconstructs state at any historical point
- **Exclusion**: `replay_excluding([event_ids])` shows state without specific events
- **Injection**: Insert hypothetical events to test "what if" scenarios

This enables questions like: "Would this decision have been blocked if the accessibility constraint existed from the start?"

### 3.8 Observability Integration: Isomorphic Models

DML's event model exhibits a structural isomorphism with observability systems like distributed tracing. This is not coincidental—both solve similar problems of tracking causality through complex systems.

**Event-Span Correspondence**:

| DML Event | Observability Span |
|-----------|-------------------|
| `global_seq` | Span ID |
| `timestamp` | Start time |
| `caused_by` | Parent span ID |
| `correlation_id` | Trace ID |
| `type` | Operation name |
| `payload` | Span attributes |

This isomorphism enables natural integration: DML events can be emitted as spans to observability platforms, providing unified visibility into both LLM behavior (traced by the observability system) and memory operations (tracked by DML).

**Complementary Perspectives**:

- **Observability tools** (e.g., Weights & Biases Weave, LangSmith) excel at tracing LLM calls, measuring latency, and visualizing execution flows
- **DML** excels at tracking memory state evolution, enforcing constraints, and enabling replay

Together, they answer different questions about the same agent:
- Observability: "What did the LLM do?" (calls, latencies, token usage)
- DML: "What did the agent know?" (facts, constraints, decisions)

**Implementation Pattern**:

When DML appends an event, it can simultaneously emit a span to the observability system. Constraint violations become span errors. The `caused_by` chain maps to parent-child span relationships, making memory causality visible in tracing dashboards.

This integration is optional—DML functions without observability—but when enabled, it provides a complete picture: the LLM's reasoning process (spans) alongside the memory context that informed it (events).

---

## 4. Implementation

### 4.1 Storage Layer

DML uses SQLite with Write-Ahead Logging (WAL) mode for the event store:

- **Append-only table**: Events are inserted, never updated or deleted
- **Indexed access**: By sequence, type, correlation_id, and caused_by
- **Thread-safe**: Connection pooling with thread-local connections
- **Portable**: Single-file database at `~/.dml/memory.db`

### 4.2 MCP Server Integration

DML exposes memory operations as Model Context Protocol (MCP) tools, enabling direct integration with Claude Code and other MCP-compatible systems:

| Tool | Description |
|------|-------------|
| `add_fact` | Record a learned fact |
| `add_constraint` | Add a constraint (with priority) |
| `record_decision` | Record a decision (auto-checks constraints) |
| `query_memory` | Search memory (records query for verification) |
| `get_memory_context` | Get full current state |
| `trace_provenance` | Trace how a fact/decision came to be |
| `time_travel` | View state at historical point |
| `simulate_timeline` | Test decisions in alternate timelines |

### 4.3 Performance Characteristics

Preliminary benchmarks show:

- **Event append**: < 1ms (SQLite insert)
- **State reconstruction**: O(n) in event count
- **Policy check**: < 5ms per constraint
- **Memory footprint**: ~200 bytes per event

For typical agent sessions (hundreds to low thousands of events), reconstruction takes tens of milliseconds—negligible compared to LLM inference latency.

---

## 5. Evaluation

We evaluate DML across functional correctness and performance characteristics.

### 5.1 Constraint Enforcement

**Scenario**: Agent has constraint "Never use eval()". Agent proposes decision containing eval().

**Expected**: Write is blocked with explanation of which constraint was violated.

**Result**: PolicyEngine correctly identifies the violation and returns a REJECTED status with constraint details, allowing the agent to revise its approach.

### 5.2 Procedural Constraint

**Scenario**: Agent has constraint "Verify accessibility before booking". Agent attempts to book without first querying accessibility.

**Expected**: Write is blocked; agent must query memory first.

**Result**: The `pending_verifications` set tracks queries. If "accessibility" was not queried, the booking decision is rejected. After querying, the same decision succeeds. This mechanism directly addresses the "Active Falsification" risk identified in ODCV-Bench [3], where agents skip verification steps under optimization pressure—DML makes verification a hard dependency that cannot be bypassed.

### 5.3 Counterfactual Analysis

**Scenario**: Agent made a decision at seq=5. User wants to understand: "What if constraint X existed from the beginning?"

**Expected**: Replay shows the decision would have been blocked.

**Result**: `simulate_timeline` injects the constraint at seq=1, replays events, and tests the decision. Returns whether the decision would have been allowed or blocked in the alternate timeline.

### 5.4 Self-Improvement

**Scenario**: Agent books non-accessible room. User corrects. Agent learns constraint.

**Expected**: Future booking attempts check accessibility first.

**Result**: Agent adds learned constraint with `triggered_by` linking to the original mistake. Policy engine enforces this constraint on all future decisions.

### 5.5 Performance

Preliminary benchmarks on a standard development machine show DML adds minimal overhead:

| Operation | Latency | Notes |
|-----------|---------|-------|
| Event append | < 1ms | SQLite insert with WAL mode |
| State reconstruction | O(n) | Linear in event count |
| Policy check | < 5ms | Per active constraint |
| Memory footprint | ~200 bytes | Per event |

For typical agent sessions (hundreds to low thousands of events), state reconstruction takes tens of milliseconds—negligible compared to LLM inference latency (typically 100-500ms). The policy enforcement overhead is similarly insignificant, consistent with findings from the MCP Guardrail Framework research which reports 8-13ms overhead per tool call [10].

---

## 6. Discussion

### 6.1 Comparison with Existing Systems

DML combines event-driven memory with policy enforcement, self-improvement, and counterfactual analysis—a combination not found in existing agent memory systems:

| Capability | MemGPT | Mem0 | A-Mem | DML |
|------------|--------|------|-------|-----|
| Persistent memory | Yes | Yes | Yes | Yes |
| Immutable event log | No | No | No | **Yes** |
| Deterministic replay | No | No | No | **Yes** |
| Full provenance chain | No | Partial | Partial | **Yes** |
| Policy enforcement | No | No | No | **Yes** |
| Procedural constraints | No | No | No | **Yes** |
| Self-improvement | No | Partial | Partial | **Yes** |
| Counterfactual analysis | No | No | No | **Yes** |
| MCP integration | No | No | No | **Yes** |

The first four capabilities are enabled by DML's use of event-driven memory as its core mechanism. The remaining capabilities are DML-specific extensions for AI agent reliability.

### 6.2 Limitations

**Semantic Matching**: Current constraint matching uses pattern-based rules. More sophisticated semantic matching (embeddings, LLM classification) would catch violations expressed in varied language.

**Conflict Resolution**: When constraints conflict (e.g., "always use tool X" vs "never use tool X"), DML currently rejects but does not resolve. Future work could implement conflict resolution strategies.

**Scalability**: State reconstruction replays all events. For very long-running agents, snapshot checkpoints would improve performance.

**Single-Agent Focus**: DML currently assumes a single agent. Multi-agent coordination with shared memory requires additional synchronization mechanisms.

### 6.3 Future Research Directions

DML opens several avenues for future research. We organize these by theme: core research questions, distributed systems, evaluation, privacy and security, theoretical foundations, and applied research.

#### Core Research Questions

**Semantic Constraint Matching**: Pattern-based matching (Section 6.2) limits constraint expressiveness. Research is needed on embedding-based or LLM-classified constraint matching that handles semantic equivalence ("be respectful" matching diverse violations), negation, and context-dependent interpretation—while maintaining the determinism and auditability that make constraints trustworthy.

**Branch and Replay Semantics**: DML's counterfactual replay could extend to full branching semantics where agents explore alternative reasoning paths in parallel, then merge successful branches. This raises research questions about branch identity, merge conflict resolution, and maintaining provenance across divergent histories—connecting to version control theory and speculative execution.

**Multi-Modal Memory**: As agents process images, audio, and structured data alongside text, defining deterministic event schemas for non-text modalities becomes critical. Research is needed on canonical representations, cross-modal constraint enforcement (e.g., "images must not contain faces"), and replay semantics for modalities where binary equality is insufficient.

**Adversarial Robustness**: Append-only logs create new attack surfaces: prompt injection that creates malicious constraints, memory poisoning through fabricated facts, or constraint evasion through careful rephrasing. Research should characterize these threats and develop defenses—input validation, anomaly detection on constraint patterns, and formal analysis of evasion-resistant constraint languages.

**Memory Lifecycle and Retention**: The tension between "append-only for auditability" and "delete for GDPR/privacy" requires principled resolution. Research directions include crypto-shredding (encrypt with per-user keys, delete keys to "forget"), tombstone semantics that preserve audit structure while removing content, and formal models of what "forgetting" means in an event-sourced system.

**Constraint Learning from Demonstrations**: Rather than explicit programming, agents could infer constraints from expert behavior—if an expert always verifies inventory before promising delivery, induce that procedural constraint. This connects to inverse reinforcement learning and imitation learning, with the added challenge of producing interpretable, auditable constraint rules rather than opaque policies.

#### Distributed Memory Systems

**Consistency and Synchronization**: Deploying DML across multiple agents, edge devices, or geographic regions raises classic distributed systems challenges: federation (sharing constraints while isolating user data), conflict resolution when offline agents reconnect with divergent histories, and consistency models appropriate for agent memory (eventual? causal? strong?). The append-only event model provides a foundation, but multi-writer coordination requires additional research.

**Streaming and Real-Time Analytics**: Event logs naturally support streaming architectures. Integration with event streaming platforms enables real-time dashboards, live anomaly detection across agent fleets, and immediate alerting on constraint violations—but raises questions about latency/consistency tradeoffs and efficient incremental projection updates.

#### Evaluation and Metrics

**Reliability Benchmarks**: The field lacks standardized benchmarks for agent memory reliability. Research should develop metrics for constraint efficacy (violations prevented vs. false positives), drift measurement (state divergence over time), and replay fidelity—along with benchmark datasets and evaluation protocols that enable reproducible comparison across memory architectures.

**Causal Analysis Tools**: Beyond counterfactual replay ("what if this constraint existed?"), agents need tools to answer "what caused this failure?"—distinguishing correlation from causation in decision chains. Integrating causal inference techniques with event logs could significantly improve debugging and root cause analysis.

#### Privacy, Security, and Compliance

**Privacy-Preserving Analytics**: Organizations need aggregate insights (common failures, constraint effectiveness) without exposing individual data. Differential privacy techniques could enable such analytics with mathematical guarantees, but research is needed on privacy/utility tradeoffs specific to event-sourced agent memory.

**Cryptographic Audit Integrity**: High-stakes applications (legal, financial, medical) may require cryptographic proof that audit records are untampered. Hash chains, digital signatures, and integration with append-only ledgers (blockchain or otherwise) could provide such guarantees, with research needed on performance and key management in agent contexts.

#### Theoretical Foundations

**Formal Verification**: Model checking techniques could prove properties about constraint systems—that constraints cannot deadlock an agent, that safety properties always hold, or that certain violation patterns are impossible. This connects DML to the formal methods community and could provide mathematical guarantees for high-assurance applications.

**Integration with Model Training**: Event logs represent rich behavioral data. Using memory events as training signal—fine-tuning models to avoid past mistakes or reinforcing successful patterns—creates a tighter loop between runtime memory and model improvement. Research questions include what to learn, how to avoid overfitting to idiosyncratic histories, and how to maintain constraint interpretability.

**Dual-Process Cognitive Parallels**: DML's architecture supports two operational modes analogous to Kahneman's dual-process theory [11]: a fast path (querying pre-built projections) resembling System 1's automatic responses, and a slow path (replaying events, analyzing trends) resembling System 2's deliberate reasoning. The feedback loop—slow analysis producing constraints that become fast checks—suggests agent memory may benefit from explicitly optimizing both modes. This parallel is speculative; empirical validation is needed.

#### Applied Research and Ecosystem

The following directions are closer to engineering than fundamental research, but represent important applied work:

**RAG Integration**: Exploring how DML interacts with retrieval-augmented generation—whether as a validator for retrieved content, a source for retrieval, or both—could yield practical architectures for grounded, constrained agents.

**Constraint Template Libraries**: Domain-specific constraint packages (healthcare HIPAA, financial trading, content moderation) would accelerate adoption, though the research contribution lies more in constraint design patterns than novel algorithms.

**Human-in-the-Loop Workflows**: Integrating learned constraint review with existing approval systems (pull requests, compliance boards) is primarily engineering, but research on effective human-AI collaboration in constraint curation could yield insights applicable beyond DML.

---

## 7. Conclusion

The **Deterministic Memory Layer (DML)** addresses fundamental challenges in AI agent reliability: drift, hallucination, non-reproducibility, and lack of accountability. Through its use of **event-driven memory** as the core mechanism, DML provides:

- **Auditability**: Every memory operation is recorded in an immutable event log
- **Reproducibility**: Deterministic replay guarantees consistent state reconstruction
- **Enforcement**: Constraints are checked on every write, not left to LLM judgment
- **Self-Improvement**: Agents learn from mistakes and prevent recurrence
- **Explainability**: Counterfactual analysis reveals why decisions were made

Event-driven memory—adapted from proven distributed systems patterns—is the mechanism that makes these capabilities possible. By treating memory as an immutable event stream rather than mutable state, DML achieves the determinism and auditability that production AI agents require.

As AI agents take on greater autonomy, the need for reliable, accountable memory systems will only grow. DML demonstrates that techniques developed for distributed systems can be adapted to meet this need, providing a foundation for agents that are trustworthy by design.

---

## References

1. A-Mem: Agentic Memory for LLM Agents. arXiv:2502.12110 (2025)

2. Policy-as-Prompt: Turning AI Governance Rules into Guardrails for AI Agents. arXiv:2509.23994 (2025)

3. ODCV-Bench: A Benchmark for Evaluating Outcome-Driven Constraint Violations in Autonomous AI Agents. arXiv:2512.20798 (2025)

4. Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory. arXiv:2504.19413 (2025)

5. Self-Improving AI Agents through Self-Play. arXiv:2512.02731 (2025)

6. Event Sourcing: The Backbone of Agentic AI. Akka Blog (2025)

7. Event Sourcing Pattern. Microsoft Azure Architecture Center (2024)

8. Demystifying Evals for AI Agents. Anthropic Engineering Blog (2025)

9. The Myth of Machine Learning Reproducibility. Carnegie Mellon SEI (2024)

10. LLM Guardrails: Strategies & Best Practices. Leanware (2025)

11. Kahneman, D. Thinking, Fast and Slow. Farrar, Straus and Giroux (2011)

---

## Appendix A: Event Schema

Note: The `timestamp` field uses a monotonic counter (not wall-clock time) to ensure deterministic replay across different environments.

```json
{
  "global_seq": 42,
  "timestamp": 42,
  "type": "ConstraintAdded",
  "payload": {
    "text": "Verify accessibility before booking",
    "priority": "learned",
    "triggered_by": 37
  },
  "turn_id": 5,
  "caused_by": 37,
  "correlation_id": "booking-flow-001"
}
```

## Appendix B: Policy Result Schema

```json
{
  "status": "rejected",
  "reason": "Write violates active constraints",
  "details": {
    "violations": [
      {
        "item": {"type": "decision", "text": "Book Hotel Granvia"},
        "constraint": "Verify accessibility before booking",
        "constraint_source": 12,
        "constraint_priority": "required"
      }
    ]
  }
}
```

## Appendix C: MCP Tool Definitions

See `dml/server.py` for complete tool schemas and implementations.
