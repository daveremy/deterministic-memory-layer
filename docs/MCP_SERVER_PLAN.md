# MCP Server Implementation Plan

## Overview

Expose DML as an MCP server that Claude Code can use via tools.

## Dependencies

```toml
# Add to pyproject.toml
"mcp>=1.0.0",
```

## File Structure

```
dml/server.py          # MCP server (inside package)
├── Tools (8 total)
│   ├── add_fact
│   ├── add_constraint
│   ├── record_decision    # ENFORCED
│   ├── query_memory
│   ├── get_memory_context
│   ├── trace_provenance
│   ├── time_travel
│   └── simulate_timeline
└── Server setup
    ├── Initialize EventStore
    ├── Initialize ReplayEngine
    ├── Initialize PolicyEngine
    └── Weave tracing wrapper
```

---

## External Review Feedback (Gemini + Codex)

### Critical Fixes Applied:
1. **[High]** `record_decision` mutable default fixed (`list[int] = []` → `None`)
2. **[High]** Verification tracking is now event-driven via `MemoryQueried` events (not volatile state)
3. **[Medium]** "verify X before Y" parsing uses strict regex
4. **[Medium]** Return IDs standardized to `seq` everywhere
5. **[Medium]** `query_memory` now has `scope` parameter
6. **[Medium]** Added `rationale` field to `record_decision`
7. **[Low]** `trace_provenance` accepts explicit `seq` or `fact_key`
8. **[Low]** `simulate_timeline` supports `priority` for injected constraints

---

## Tool Specifications

### 1. `add_fact`

```python
@mcp.tool()
def add_fact(key: str, value: str, confidence: float = 1.0) -> dict:
    """
    Record a learned fact about the user or context.

    Call this when you learn something new from the conversation.

    Args:
        key: Fact identifier (e.g., "budget", "destination", "dietary_restriction")
        value: The fact value (e.g., "3000", "Japan", "vegetarian")
        confidence: How confident you are (0.0-1.0, default 1.0)

    Returns:
        {seq, key, value, previous_value?, drift_alert?}
    """
```

**Implementation notes:**
- Check if key already exists → return `previous_value` for drift detection
- If value changed, include `drift_alert: true`
- Emit `FactAdded` event

---

### 2. `add_constraint`

```python
@mcp.tool()
def add_constraint(
    text: str,
    priority: str = "required",
    triggered_by: int | None = None
) -> dict:
    """
    Record a constraint or requirement.

    Call this when:
    - User states a requirement ("I need wheelchair access")
    - You learn a rule from a mistake (use priority="learned")

    Args:
        text: The constraint text (e.g., "wheelchair accessible rooms required")
        priority: "required" | "preferred" | "learned"
        triggered_by: If learned, the seq of the event that triggered learning

    Returns:
        {seq, constraint, priority, triggered_by?}
    """
```

**Implementation notes:**
- Store priority in event payload
- If `priority="learned"`, require `triggered_by`
- Tag learned constraints visually in UI

---

### 3. `record_decision` ⚠️ ENFORCED

```python
@mcp.tool()
def record_decision(
    text: str,
    rationale: str,
    references: list[int] | None = None
) -> dict:
    """
    Record a decision you're making. AUTO-CHECKS ALL CONSTRAINTS.

    This will be BLOCKED if the decision violates any constraint,
    including learned constraints about procedure.

    Args:
        text: What you're deciding (e.g., "Book Hotel Granvia Kyoto")
        rationale: Why this decision satisfies constraints
        references: Event seqs this decision is based on (default: [])

    Returns:
        If ALLOWED: {status: "COMMITTED", seq, decision, rationale}
        If BLOCKED: {status: "BLOCKED", violated_constraint_seq, reason, suggestion}
    """
```

**Implementation notes:**
- ALWAYS run policy check before committing
- `references` defaults to `[]` internally (not in signature - avoids mutable default)
- Return detailed explanation on block, including constraint `seq` for traceability
- `rationale` improves provenance chain and debugging
- This is the key enforcement point

---

### 4. `query_memory`

```python
@mcp.tool()
def query_memory(
    question: str,
    scope: str = "all"
) -> dict:
    """
    Search memory for facts, constraints, or decisions matching a question.

    Use this to verify information before making decisions.
    IMPORTANT: Calling this tool records a MemoryQueryIssued event for verification tracking.

    Args:
        question: What you want to know (e.g., "wheelchair accessible")
        scope: "facts" | "constraints" | "decisions" | "all" (default: "all")

    Returns:
        {
            query_seq: int,  # The seq of this query event (for references)
            facts: [{key, value, confidence, seq}, ...],
            constraints: [{text, priority, active, seq}, ...],  # if scope includes
            decisions: [{text, status, seq}, ...]  # if scope includes
        }
    """
```

**Implementation notes:**
- Simple text search on keys, values, and constraint text
- **Emit `MemoryQueryIssued` event** - this is critical for verification tracking
- Return `query_seq` so agent can include it in `record_decision.references`
- Scope allows focused queries for performance

---

### 5. `get_memory_context`

```python
@mcp.tool()
def get_memory_context() -> dict:
    """
    Get the full current memory state.

    Use this to refresh your understanding of all facts, constraints, and decisions.

    Returns:
        {
            current_seq: int,
            facts: {key: {value, confidence, seq}},
            constraints: [{text, priority, active, seq}],
            decisions: [{text, status, seq}],
            alerts: [{type, message, related_seqs}]
        }
    """
```

**Implementation notes:**
- Call `replay_engine.replay_to()` for current state
- Format for easy agent consumption
- Include any active drift alerts
- All IDs use `seq` for consistency

---

### 6. `trace_provenance`

```python
@mcp.tool()
def trace_provenance(
    seq: int | None = None,
    fact_key: str | None = None
) -> dict:
    """
    Trace how a fact or decision came to be.

    Use this to explain why you know something or made a decision.

    Args:
        seq: The event sequence number to trace (preferred)
        fact_key: Alternative: trace the fact with this key

    Returns:
        {chain: [{seq, type, payload, caused_by}, ...]}
    """
```

**Implementation notes:**
- Accept either `seq` (preferred) or `fact_key` for flexibility
- Follow `caused_by` links backwards
- Return full causal chain
- Mark stale facts in the chain

---

### 7. `time_travel`

```python
@mcp.tool()
def time_travel(to_seq: int) -> dict:
    """
    View memory state at a specific point in history.

    Use this to understand what you knew at a particular moment.

    Args:
        to_seq: The sequence number to travel to

    Returns:
        {
            mode: "FLASHBACK",
            viewing_seq: int,
            current_seq: int,
            historical_state: {facts, constraints, decisions},
            diff_from_current: {added, removed, changed}
        }
    """
```

**Implementation notes:**
- Call `replay_engine.replay_to(to_seq)`
- Also compute diff from current state
- UI will render this in "flashback mode"

---

### 8. `simulate_timeline`

```python
@mcp.tool()
def simulate_timeline(
    inject_constraint: str,
    at_seq: int,
    then_decide: str,
    priority: str = "required"
) -> dict:
    """
    Simulate an alternate timeline: "What if this constraint existed earlier?"

    Use this to show how earlier constraints would have changed outcomes.

    Args:
        inject_constraint: Constraint to inject (e.g., "wheelchair accessible")
        at_seq: Where to inject it in the timeline
        then_decide: Decision to test against the modified timeline
        priority: Priority of injected constraint (default: "required")

    Returns:
        {
            timeline: "B (simulated)",
            injected_constraint: str,
            injected_at_seq: int,
            injected_priority: str,
            tested_decision: str,
            result: "BLOCKED" | "ALLOWED",
            reason: str | None
        }
    """
```

**Implementation notes:**
- Get events up to `at_seq`
- Create synthetic constraint event with proper `priority`
- Rebuild state with injected constraint
- Test decision against alternate state
- DO NOT persist - this is read-only simulation

---

## Policy Engine Updates Required

The current policy engine only matches "never/do not/avoid" patterns. We need:

### 1. Use Existing Event Type: `MemoryQueryIssued`

The `events.py` already defines `MemoryQueryIssued` - use this instead of creating a new event type:

```python
# Already exists in events.py:
MemoryQueryIssued = "MemoryQueryIssued"  # PascalCase in actual code
```

### 2. Update Projection Schemas

```python
# In projections.py, update ConstraintProjection:
@dataclass
class ConstraintProjection:
    text: str
    source_event_id: int | None = None
    active: bool = True
    priority: str = "required"  # NEW: "required" | "preferred" | "learned"
    triggered_by: int | None = None  # NEW: seq that triggered learning

# In projections.py, update DecisionProjection:
@dataclass
class DecisionProjection:
    text: str
    references: list[int] = field(default_factory=list)
    source_event_id: int | None = None
    rationale: str | None = None  # NEW: why this decision
    status: str = "committed"  # NEW: "committed" | "blocked"
```

### 3. Update ProjectionState for Verification Tracking

```python
# In projections.py, add to ProjectionState:
@dataclass
class ProjectionState:
    facts: dict[str, FactProjection]
    constraints: dict[str, ConstraintProjection]  # keyed by text
    decisions: list[DecisionProjection]
    pending_verifications: set[str] = field(default_factory=set)  # NEW

# In ProjectionEngine._apply_event:
elif event.type == EventType.MemoryQueryIssued:
    # Extract keywords from query
    query = event.payload.get("question", "").lower()
    for keyword in self._extract_keywords(query):
        state.pending_verifications.add(keyword)

elif event.type == EventType.DecisionMade:
    # Clear verifications after each decision
    state.pending_verifications.clear()
```

**Why event-driven?** Both Gemini and Codex emphasized this: volatile state breaks determinism and replay. By deriving verifications from events, `replay_to(seq)` correctly reconstructs what had been verified at that point.

### 4. Implement `_extract_keywords` Helper

```python
# In projections.py, add to ProjectionEngine:
def _extract_keywords(self, query: str) -> list[str]:
    """Extract searchable keywords from a query string.

    For demo reliability, we use exact term matching.
    The system prompt instructs agents to use standardized terms.
    """
    # Standardized keywords from system prompt
    KNOWN_KEYWORDS = {
        "accessibility", "budget", "destination",
        "booking", "canceling", "selecting"
    }

    query_lower = query.lower()
    found = []
    for keyword in KNOWN_KEYWORDS:
        if keyword in query_lower:
            found.append(keyword)

    # Also add any word longer than 4 chars as potential keyword
    words = query_lower.split()
    for word in words:
        word = word.strip(".,!?\"'")
        if len(word) > 4 and word not in found:
            found.append(word)

    return found
```

### 5. Define `record_decision` Enforcement Path

```python
# In dml/server.py, record_decision routes through PolicyEngine:

def record_decision(text: str, rationale: str, references: list[int] | None = None) -> dict:
    refs = references or []

    # Build current state via replay
    state = replay_engine.replay_to()

    # Create decision item for policy check
    decision_item = {
        "text": text,
        "rationale": rationale,
        "references": refs,
        "type": "decision"
    }

    # Create proposal and check policy
    proposal = WriteProposal(items=[decision_item])
    result = policy_engine.check_write(proposal, state)

    if result.rejected:
        # Return BLOCKED with details
        violation = result.details.get("violations", [{}])[0]
        return {
            "status": "BLOCKED",
            "violated_constraint_seq": violation.get("constraint_source"),
            "reason": result.reason,
            "suggestion": f"Call query_memory to verify before deciding"
        }

    # Commit the decision
    event = Event(
        type=EventType.DecisionMade,
        payload={
            "text": text,
            "rationale": rationale,
            "references": refs,
            "status": "committed"
        }
    )
    seq = store.append(event)

    return {
        "status": "COMMITTED",
        "seq": seq,
        "decision": text,
        "rationale": rationale
    }
```

### 6. Learned Constraint Pattern: "verify X before Y"

```python
# In policy.py, add to _violates_constraint:
import re

# Strict pattern matching (not just "before" anywhere)
VERIFY_BEFORE_PATTERN = re.compile(
    r"^(verify|check)\s+(.+?)\s+before\s+(.+)$",
    re.IGNORECASE
)

def _violates_constraint(
    self, item: dict, constraint: ConstraintProjection, state: ProjectionState
) -> bool:
    constraint_text = constraint.text.lower()
    item_text = self._item_to_text(item).lower()

    # Existing patterns: never/do not/avoid
    # ... (existing code) ...

    # NEW: "verify X before Y" pattern
    match = VERIFY_BEFORE_PATTERN.match(constraint_text)
    if match:
        verification_topic = match.group(2).strip()  # e.g., "accessibility"
        action_type = match.group(3).strip()  # e.g., "booking"

        # Check if this decision matches the action type
        if self._matches_action(item_text, action_type):
            # Check if verification was done (via MemoryQueryIssued events)
            if verification_topic not in state.pending_verifications:
                return True  # VIOLATION: didn't verify before acting

    return False

def _matches_action(self, item_text: str, action_type: str) -> bool:
    """Word-boundary match for action type."""
    pattern = r'\b' + re.escape(action_type) + r'\b'
    return bool(re.search(pattern, item_text, re.IGNORECASE))
```

---

## System Prompt for Agent

Create `prompts/travel_agent.md`:

```markdown
# DML Travel Agent System Prompt

You are a travel planning assistant with access to a Deterministic Memory Layer (DML).

## Critical Rules

1. **You CANNOT rely on internal context.** All facts, constraints, and decisions
   must be recorded in DML using the provided tools.

2. **Before making ANY booking decision**, you MUST:
   - Call `query_memory` to verify relevant requirements
   - Include the `query_seq` in your `record_decision.references`

3. **When `record_decision` returns BLOCKED**:
   - Do NOT retry the same decision
   - Read the `reason` and `suggestion`
   - Take corrective action (query more info, inform user, etc.)

4. **When you learn from a mistake**:
   - Call `add_constraint` with `priority="learned"`
   - Include `triggered_by` pointing to the problematic event

## Keyword Standardization

For the demo, use these EXACT terms in queries and constraints:
- "accessibility" (not "wheelchair", "disabled access", etc.)
- "budget" (not "price", "cost", "spending")
- "destination" (not "location", "place", "city")

For decisions, use these action keywords (word-boundary matching):
- "booking" (say "booking hotel", not "book hotel")
- "canceling" (say "canceling reservation", not "cancel reservation")
- "selecting" (say "selecting flight", not "select flight")

This ensures reliable constraint matching.
```

---

## Documentation Plan

### 1. `prompts/travel_agent.md` (System Prompt)
Already defined above - the core instructions for the agent.

### 2. `prompts/tool_examples.md` (Concrete Examples)

```markdown
# DML Tool Examples

## Pattern 1: Verify Before Deciding

```python
# Step 1: Query memory (records MemoryQueryIssued event)
result = query_memory("accessibility")
# → {query_seq: 5, facts: [...], constraints: [...]}

# Step 2: Use query_seq in references
record_decision(
    text="booking Hotel Granvia Kyoto",
    rationale="verified accessibility requirement met - hotel has wheelchair ramps",
    references=[5]
)
# → {status: "COMMITTED", seq: 6, decision: "booking Hotel Granvia Kyoto"}
```

## Pattern 2: Learning from Mistakes

```python
# Decision gets blocked
result = record_decision(
    text="booking Hotel Sakura",
    rationale="good reviews"
)
# → {status: "BLOCKED", violated_constraint_seq: 3, reason: "..."}

# Learn from this - add procedural constraint
add_constraint(
    text="verify accessibility before booking",
    priority="learned",
    triggered_by=result["violated_constraint_seq"]
)
# → {seq: 7, constraint: "verify accessibility before booking", priority: "learned"}
```

## Pattern 3: Tracing Provenance

```python
# Why do I know the budget is $3000?
trace_provenance(fact_key="budget")
# → {chain: [
#     {seq: 2, type: "FactAdded", payload: {key: "budget", value: "3000"}, caused_by: 1},
#     {seq: 1, type: "UserMessageReceived", payload: {text: "My budget is $3000"}}
#   ]}
```

## Pattern 4: What-If Simulation

```python
# What if we had the accessibility constraint from the start?
simulate_timeline(
    inject_constraint="verify accessibility before booking",
    at_seq=1,  # Beginning of conversation
    then_decide="booking Hotel Sakura"
)
# → {timeline: "B (simulated)", result: "BLOCKED", reason: "..."}
```

## Anti-Patterns (Don't Do This)

```python
# ❌ Deciding without querying first
record_decision(text="booking Hotel Sakura", rationale="looks good")
# Will be BLOCKED if "verify X before booking" constraint exists

# ❌ Not including references
query_memory("accessibility")  # query_seq: 5
record_decision(text="booking Hotel", rationale="accessible", references=[])
# Missing reference - policy can't verify you actually checked

# ❌ Retrying blocked decision unchanged
result = record_decision(...)  # BLOCKED
record_decision(...)  # Same thing again - still BLOCKED!
```
```

### 3. `prompts/workflows.md` (Common Patterns)

```markdown
# DML Workflow Patterns

## 1. Verify-Decide Workflow
The core pattern for any booking/selection decision.

```
User request → add_fact (capture requirements)
            → query_memory (verify constraints)
            → record_decision (with references)
            → Success OR learn from block
```

## 2. Learn-Constrain Workflow
How the agent improves from mistakes.

```
Decision BLOCKED → Read reason
                → Identify missing step
                → add_constraint(priority="learned", triggered_by=...)
                → Future decisions auto-checked
```

## 3. Explain-Trace Workflow
For transparency and debugging.

```
User asks "why did you pick X?" → trace_provenance(seq)
                                → Show causal chain
                                → Each step has source event
```

## 4. What-If Workflow
For demonstrating counterfactuals.

```
After mistake → simulate_timeline(inject early, test decision)
             → Show: "If we knew this earlier, we'd have caught it"
             → Proves determinism
```

## 5. Drift-Detection Workflow
When facts change mid-conversation.

```
add_fact("budget", "4000") → seq: 3
... later ...
add_fact("budget", "3000") → {drift_alert: true, previous_value: "4000"}
                          → Agent notified of change
                          → Can review decisions based on old value
```
```

### 4. `docs/JUDGE_GUIDE.md` (Hackathon Overview)

```markdown
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

### Weave Dashboard
- Each tool call is traced
- Compare Timeline A vs B
- See constraint violations in red
- Drill into any decision's provenance

### Try It Yourself
```bash
# Start the MCP server
python mcp_server.py

# In another terminal, use Claude Code with DML
claude --mcp-config .claude/mcp.json
```

### Architecture (10 seconds)
```
Agent ←→ MCP Tools ←→ EventStore (SQLite)
              ↓
         PolicyEngine (blocks violations)
              ↓
         ReplayEngine (deterministic state)
```

### Links
- [Full Demo Design](DEMO_DESIGN.md)
- [MCP Server Plan](MCP_SERVER_PLAN.md)
- Weave Dashboard: [link after deploy]
```

---

## Weave Integration

Wrap each tool with Weave tracing:

```python
from dml.tracing import trace_op

@mcp.tool()
@trace_op("dml.add_fact")
def add_fact(key: str, value: str, confidence: float = 1.0) -> dict:
    # ... implementation
```

For Timeline B simulations, add tags:

```python
@trace_op("dml.simulate_timeline", tags=["simulation", "timeline-b"])
def simulate_timeline(...):
```

---

## Server Setup

```python
# dml/server.py

import os
from pathlib import Path
from mcp import Server
from dml.events import EventStore, Event, EventType
from dml.replay import ReplayEngine
from dml.policy import PolicyEngine, WriteProposal
from dml.memory_api import MemoryAPI
from dml.tracing import trace_op, init_tracing

# DB Path: Use ~/.dml/memory.db for consistent location
# This ensures the same DB is used regardless of CWD
def get_db_path() -> Path:
    """Get the DML database path."""
    dml_dir = Path.home() / ".dml"
    dml_dir.mkdir(parents=True, exist_ok=True)
    return dml_dir / "memory.db"

# Initialize
db_path = os.environ.get("DML_DB_PATH", str(get_db_path()))
store = EventStore(db_path)
replay_engine = ReplayEngine(store)
policy_engine = PolicyEngine()
api = MemoryAPI(store)

# Optional Weave
init_tracing("dml-travel-agent")

# Create MCP server
server = Server("dml")

# Register tools
@server.tool()
def add_fact(...): ...

@server.tool()
def add_constraint(...): ...

# ... etc

# Run
if __name__ == "__main__":
    server.run()
```

---

## Distribution & Installation

### Package Structure (Refactored)

```
deterministic-memory-layer/
├── dml/
│   ├── __init__.py
│   ├── __main__.py       # NEW: python -m dml entry point
│   ├── cli.py            # MOVED from root
│   ├── server.py         # NEW: MCP server
│   ├── events.py
│   ├── projections.py
│   ├── replay.py
│   ├── policy.py
│   ├── memory_api.py
│   └── tracing.py
├── prompts/              # NEW
│   ├── travel_agent.md
│   ├── tool_examples.md
│   └── workflows.md
├── docs/
│   ├── MCP_SERVER_PLAN.md
│   ├── DEMO_DESIGN.md
│   └── JUDGE_GUIDE.md
├── tests/
├── pyproject.toml
└── README.md
```

### Packaging

```toml
# pyproject.toml
[project]
name = "deterministic-memory-layer"  # PyPI name (unique)
version = "0.1.0"
# ...

[project.scripts]
dml = "dml.cli:cli"  # CLI command stays short

[tool.hatch.build.targets.wheel]
packages = ["dml"]
```

**Note:** `dml` is likely taken on PyPI. Keep `deterministic-memory-layer` as package name, `dml` as CLI command.

### Installation Flow

```bash
# Install from PyPI (one line)
pip install deterministic-memory-layer

# Or with uv
uv add deterministic-memory-layer

# Quick start
dml install   # Auto-configures .claude/mcp.json
dml serve     # Starts MCP server (or use --init to create DB first)
```

### CLI Commands

```bash
# New commands
dml serve [--init]      # Start MCP server (--init creates DB first)
dml install [--dry-run] # Add to .claude/mcp.json
dml demo [--interactive] # Run demo (scripted by default)

# Existing commands (keep)
dml init                # Create memory.db
dml replay [--to SEQ]   # View state
dml trace <key>         # Show provenance
dml query <search>      # Search memory
dml diff <seq1> <seq2>  # Compare states
dml drift <seq1> <seq2> # Measure drift
```

### `dml install` Implementation

```python
# In dml/cli.py

import sys
import json
from pathlib import Path

@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be added")
def install(dry_run: bool):
    """Add DML to Claude Code's MCP configuration."""

    config_path = Path.home() / ".claude" / "mcp.json"

    # Use absolute paths (critical for Claude to find the server)
    dml_config = {
        "dml": {
            "command": sys.executable,  # Absolute path to Python
            "args": ["-m", "dml", "serve"],
            "env": {}
        }
    }

    # Load existing config or create new
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        # Backup before modifying
        backup_path = config_path.with_suffix(".json.backup")
        if not dry_run:
            config_path.rename(backup_path)
            click.echo(f"Backed up existing config to {backup_path}")
    else:
        config = {"mcpServers": {}}
        config_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if already installed (idempotent)
    if "dml" in config.get("mcpServers", {}):
        click.echo("DML already configured in .claude/mcp.json")
        return

    # Add DML
    config.setdefault("mcpServers", {}).update(dml_config)

    if dry_run:
        click.echo("Would add to .claude/mcp.json:")
        click.echo(json.dumps(dml_config, indent=2))
    else:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        click.echo(f"Added DML to {config_path}")
        click.echo("Restart Claude Code to use DML tools.")
```

### `dml/__main__.py`

```python
"""Entry point for python -m dml."""
from dml.cli import cli

if __name__ == "__main__":
    cli()
```

### Demo Flow (Before/After)

#### Act 1: The Problem (No DML)
```bash
# Show Claude making mistakes without structured memory
claude -p "Help me plan a trip to Japan. Budget \$3000. I need wheelchair access."

# ... conversation continues ...

claude -p "Book Hotel Sakura please"
# Claude books it - FORGETS the wheelchair requirement!
```

#### Act 2: Install DML (Live, 2 commands)
```bash
pip install deterministic-memory-layer
dml install

# Show what changed
cat ~/.claude/mcp.json
```

#### Act 3: The Solution (With DML)
```bash
# Restart Claude Code, then same conversation
claude -p "Help me plan a trip to Japan. Budget \$3000. I need wheelchair access."

# ... conversation continues ...

claude -p "Book Hotel Sakura please"
# → BLOCKED: "verify accessibility before booking"
# Claude must query_memory first!
```

### `dml demo` Command

```python
@cli.command()
@click.option("--interactive", is_flag=True, help="Interactive mode (vs scripted)")
def demo(interactive: bool):
    """Run the DML demo scenario."""

    if interactive:
        # Human-in-the-loop: show prompts, wait for Enter
        steps = [
            ("Add user requirements", "I'm planning a trip to Japan..."),
            ("Forget to check constraint", "Book Hotel Sakura"),
            ("See BLOCKED result", None),
            ("Learn from mistake", "Add constraint: verify accessibility before booking"),
            ("Retry correctly", "Query accessibility, then book"),
        ]
        for title, prompt in steps:
            click.echo(f"\n{'='*50}")
            click.echo(f"Step: {title}")
            if prompt:
                click.echo(f"Prompt: {prompt}")
            click.echo("Press Enter to continue...")
            input()
    else:
        # Scripted: run the full scenario automatically
        from demo import main
        main()
```

---

## Configuration for Claude Code

The `dml install` command auto-generates this, but for reference:

```json
{
  "mcpServers": {
    "dml": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "dml", "serve"],
      "env": {}
    }
  }
}
```

**Important:** Uses absolute path to Python (`sys.executable`) so Claude finds the correct interpreter regardless of working directory.

---

## Testing Plan

1. **Unit tests** for each tool
2. **Integration test**: Full 8-act demo flow
3. **Policy test**: Learned constraint blocks correctly
4. **Simulation test**: Timeline B produces different result
5. **Verification tracking test**: Decision blocked if query_memory not called first
6. **False positive test**: "before" in unrelated text doesn't trigger

---

## Build Order

### Project Refactoring
1. [ ] Move `cli.py` → `dml/cli.py`
2. [ ] Create `dml/__main__.py`
3. [ ] Update `pyproject.toml` scripts entry
4. [ ] Create `prompts/` directory

### Schema Updates
5. [ ] Update `ConstraintProjection` with `priority`, `triggered_by` fields
6. [ ] Update `DecisionProjection` with `rationale`, `status` fields
7. [ ] Update `ProjectionEngine` to populate new fields from events

### Core Implementation
8. [x] Use existing `MemoryQueryIssued` event type (already in `events.py`)
9. [ ] Update `ProjectionState` with `pending_verifications`
10. [ ] Implement `_extract_keywords` helper in `ProjectionEngine`
11. [ ] Update `PolicyEngine` with strict "verify before" pattern
12. [ ] Create `dml/server.py` with MCP server skeleton + DB path handling
13. [ ] Implement `add_fact`, `add_constraint` tools
14. [ ] Implement `query_memory` with `MemoryQueryIssued` event emission
15. [ ] Implement `record_decision` with policy check and rationale
16. [ ] Implement `get_memory_context`
17. [ ] Implement `trace_provenance`
18. [ ] Implement `time_travel`
19. [ ] Implement `simulate_timeline`
20. [ ] Weave integration on all tools (add `tags` param to `trace_op`)

### CLI Commands
21. [ ] Add `dml serve` command (with DB path from `~/.dml/`)
22. [ ] Add `dml install` command (with --dry-run, backup)
23. [ ] Add `dml demo` command (scripted + --interactive)

### Documentation
24. [ ] Create `prompts/travel_agent.md` (system prompt)
25. [ ] Create `prompts/tool_examples.md` (concrete examples)
26. [ ] Create `prompts/workflows.md` (common patterns)
27. [ ] Create `docs/JUDGE_GUIDE.md` (hackathon overview)

### Testing & Demo
28. [ ] End-to-end test with Claude
29. [ ] Update demo script with travel scenario

---

## Resolved Questions

1. **Verification tracking**: YES - track via `MemoryQueryIssued` events in `ProjectionState.pending_verifications`. This maintains determinism during replay.

2. **Constraint matching**: Use strict regex with word boundaries. Hardcode keywords in system prompt for demo reliability.

3. **State persistence**: Yes - SQLite already handles this. MCP server is stateless; state comes from replaying events.

4. **Error handling**: Return structured error responses with clear messages. Never crash - always return JSON.

5. **DB path**: Use `~/.dml/memory.db` by default for consistent location. Override with `DML_DB_PATH` env var if needed.

6. **DecisionMade events**: Include `rationale`, `references`, and `status` in payload. Status is both stored in event and returned by tool.

7. **Preferred constraints**: `priority="preferred"` constraints are tracked but not enforced (no blocking). They appear in `get_memory_context` for agent awareness.

8. **Provenance tracing**: `trace_provenance` follows `caused_by` links. For decisions, the `references` field points to query events but doesn't form a `caused_by` chain.
