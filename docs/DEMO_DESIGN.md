# DML Demo Design: Self-Improving Travel Agent

**Target**: [WeaveHacks 3: Self-Improving Agents](https://lu.ma/weavehacks3)
**Dates**: January 31 - February 1, 2026
**Submission**: Sunday 1:30 PM

## Prize Targets

| Prize | Amount | Our Angle |
|-------|--------|-----------|
| **Best Self-Improving Agent** | $1,000 | Agent learns constraints from mistakes |
| **Best Use of Weave** | $1,000 | Decision audit trail, drift graph, blocked branch visualization |
| **Grand Prize** | Robot dog + $2,000 | "Fork the Future" - same inputs, different constraints, different reality |

---

## External Review Summary

**Reviewed by**: Gemini, Codex (Jan 30, 2026) - Two rounds

### What's Strong
- The "budget changes, agent forgets" narrative is universally relatable
- Event sourcing is the correct technical approach - makes learning mechanically verifiable
- Constraint loop makes "self-improvement" tangible, not just prompt engineering

### Key Insight

> "The core story is strong, but it needs a single, unmistakable 'oh wow' moment that only your system can do. Make it feel like time-machine + policy engine + self-correction in one breath." — Codex

### Critical Enhancements Added (Round 2)

| Enhancement | Source | Purpose |
|-------------|--------|---------|
| **Fork the Future** | Codex | Show same decision allowed/blocked based on when constraint was added |
| **Double-Tap Failure** | Gemini | Block correct decision because procedure wasn't followed |
| **Flashback Mode** | Gemini | Visual time travel with sepia UI, state rewind |
| **Decision Audit Table** | Codex | Prove determinism with seq/event/decision/status/rule |

---

## The Problem We're Solving

Current agent memory is a **blob** - unstructured text that accumulates without:
- **Structure**: Facts, constraints, and decisions mixed together
- **Time travel**: Can't see "what did I know at turn 5?"
- **Provenance**: "Why do I think the user is vegetarian?" No answer.
- **Conflict detection**: Contradictions silently accumulate
- **Learning from mistakes**: No structured way to remember what went wrong

**You can't improve if you can't remember what you did wrong.**

---

## The Headline Moment: "Fork the Future"

This is what makes DML unique. Not just blocking bad decisions - **showing alternate timelines**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FORK THE FUTURE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TIMELINE A (What actually happened):                                       │
│    seq 5:  budget=$4000                                                     │
│    seq 12: constraint="traditional ryokan"                                  │
│    seq 23: decision="Book Ryokan Kurashiki" ✓ ALLOWED                       │
│    seq 31: budget=$3000 (drift!)                                            │
│    seq 45: constraint="wheelchair accessible"                               │
│    seq 47: decision="Keep booking" 🔴 BLOCKED                               │
│                                                                             │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                             │
│  TIMELINE B (What if constraint came earlier?):                             │
│    → Time travel to seq 5                                                   │
│    → Insert wheelchair constraint at seq 6                                  │
│    → Replay...                                                              │
│    seq 23: decision="Book Ryokan Kurashiki" 🔴 BLOCKED                       │
│                                                                             │
│  THE HOTEL WAS NEVER BOOKED.                                                │
│  Same inputs. Different constraint timing. Different reality.               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Why this is the wow**: The system doesn't just prevent mistakes - it shows you **what could have been**.

---

## Demo Script: 6 Minutes, 8 Acts

**This exact sequence will be demonstrated. No improvisation.**

---

### Act 1: Setup (30 sec)

```
User: "Plan a 10-day trip to Japan in April. Budget is $4000."

Agent actions:
  → add_fact("destination", "Japan")
  → add_fact("budget", 4000)

UI shows: Facts panel populates with clean entries
Weave: First events appear in audit trail
```

---

### Act 2: First Decision (30 sec)

```
User: "I'd like traditional Japanese inns."

Agent actions:
  → add_constraint("prefer traditional ryokan accommodations")
  → record_decision("Book Ryokan Kurashiki in Kyoto - $180/night")
    └── Auto-check passes ✓

UI shows:
  ✓ Decision committed (green)
  Decision Ledger: seq 23 | DecisionMade | Ryokan Kurashiki | ✓ ALLOWED | -
```

---

### Act 3: The Drift (30 sec)

```
User: "Actually, budget is only $3000."

Agent actions:
  → add_fact("budget", 3000)

UI shows:
  ⚠️ DRIFT ALERT
  ├── budget: $4000 → $3000
  └── Decisions made before this change: Ryokan Kurashiki ($180/night)

Weave: Drift metric spikes in graph
```

---

### Act 4: THE BLOCK - Key Moment #1 (1 min)

```
User: "I use a wheelchair - I need accessible rooms."

Agent actions:
  → add_constraint("wheelchair accessible rooms required")
  → record_decision("Keep Ryokan Kurashiki booking")
    └── Auto-check FAILS! 🔴

UI shows:
  ┌────────────────────────────────────────────────────┐
  │ 🔴 DECISION BLOCKED                                │
  ├────────────────────────────────────────────────────┤
  │ Decision: "Keep Ryokan Kurashiki booking"          │
  │ Violated: "wheelchair accessible" (seq 45)         │
  │ Reason: Traditional ryokan has stairs, no elevator │
  └────────────────────────────────────────────────────┘

Decision Ledger: seq 47 | DecisionMade | Keep Ryokan | 🔴 BLOCKED | wheelchair accessible

Agent response: "I apologize - that ryokan isn't accessible. Let me find an alternative."
```

---

### Act 5: THE LEARNING - Key Moment #2 (30 sec)

```
Agent realizes the pattern and learns:

Agent actions:
  → add_constraint("LEARNED: always verify accessibility BEFORE recommending accommodations",
                   priority="learned",
                   triggered_by=47)

UI shows:
  ┌────────────────────────────────────────────────────┐
  │ ★ CONSTRAINT LEARNED                               │
  ├────────────────────────────────────────────────────┤
  │ "verify accessibility BEFORE recommending"         │
  │ Triggered by: conflict at seq 47                   │
  │ Type: learned (self-improvement)                   │
  └────────────────────────────────────────────────────┘

Weave: New constraint appears with "learned" tag and causal link
```

---

### Act 6: THE DOUBLE-TAP - Key Moment #3 (1 min)

**This proves the system enforces PROCEDURE, not just correctness.**

```
Agent finds a new hotel (which happens to be accessible):

Agent actions:
  → record_decision("Book Hotel Granvia Kyoto")
    └── Auto-check: BLOCKED! 🔴

UI shows:
  🔴 DECISION BLOCKED
  Violated: "LEARNED: verify accessibility BEFORE recommending" (seq 48)
  Note: You must VERIFY accessibility before booking, even if the hotel is accessible.

Agent: "Right, I need to follow the verification procedure."
  → query_memory("Is Hotel Granvia wheelchair accessible?")
  → Response: "Yes, Hotel Granvia has accessible rooms"
  → record_decision("Book Hotel Granvia - VERIFIED accessible")
    └── Auto-check: ✓ ALLOWED

UI shows:
  ✓ Decision committed
  ★ Learned constraint was enforced!

Decision Ledger:
  seq 50 | DecisionMade | Hotel Granvia | 🔴 BLOCKED | learned:verify-first
  seq 52 | DecisionMade | Hotel Granvia (verified) | ✓ ALLOWED | -
```

---

### Act 7: FORK THE FUTURE - The Headline Moment (1 min)

```
User: "What if I had mentioned the wheelchair earlier?"

Agent actions:
  → time_travel(to_seq=5)  // Go back to before any decisions

UI ENTERS FLASHBACK MODE:
  ┌─────────────────────────────────────────────────────────────────┐
  │ ⏪ FLASHBACK MODE - TIMELINE B                          seq: 5  │
  │ ═══════════════════════════════════════════════════════════════ │
  │ [Border turns SEPIA/AMBER]                                      │
  │                                                                 │
  │ FACTS (at seq 5)          │ CONSTRAINTS (at seq 5)              │
  │ destination: Japan        │ (none yet)                          │
  │ budget: $4000             │                                     │
  └─────────────────────────────────────────────────────────────────┘

Now simulate adding wheelchair constraint EARLY:
  → add_constraint("wheelchair accessible") at seq 6

Re-run the original decision:
  → record_decision("Book Ryokan Kurashiki")
    └── 🔴 BLOCKED (in Timeline B)

UI shows SPLIT VIEW:
  ┌─────────────────────────────┬─────────────────────────────────┐
  │ TIMELINE A (actual)         │ TIMELINE B (what-if)            │
  ├─────────────────────────────┼─────────────────────────────────┤
  │ seq 23: Ryokan ✓ ALLOWED    │ seq 23: Ryokan 🔴 BLOCKED       │
  │ seq 47: Keep    🔴 BLOCKED  │ (never booked in first place)   │
  ├─────────────────────────────┼─────────────────────────────────┤
  │ Pain discovered LATE        │ Pain PREVENTED                  │
  └─────────────────────────────┴─────────────────────────────────┘

Banner: "Same inputs. Earlier constraint. Different reality."
```

---

### Act 8: Weave Dashboard (30 sec)

```
Switch to Weave UI (browser or embedded):

Show:
1. DECISION AUDIT TABLE
   seq | event | decision | status | constraint_fired
   23  | DecisionMade | Ryokan Kurashiki | ALLOWED | -
   47  | DecisionMade | Keep Ryokan | BLOCKED | wheelchair
   50  | DecisionMade | Hotel Granvia | BLOCKED | learned:verify
   52  | DecisionMade | Hotel Granvia (v) | ALLOWED | -

2. DRIFT GRAPH
   Line chart showing budget value over seq
   Spike at seq 31 where $4000 → $3000

3. CONSTRAINT LINEAGE
   Visual tree: user_complaint → learned_constraint → blocked_decision

Pitch: "Most agents are black boxes. With DML + Weave, you see exactly
        when the agent's mind changed, why decisions were blocked,
        and what would have happened in alternate timelines."
```

---

## Technical Architecture

### Critical Design: Enforce, Don't Trust

```python
@mcp.tool()
def record_decision(text: str, references: list[int] = []) -> dict:
    """Record a decision. Auto-checks ALL constraints including learned ones."""

    # ENFORCE - agent cannot bypass
    state = replay_engine.replay_to()
    result = policy_engine.check_write(
        WriteProposal(items=[{"type": "decision", "text": text}]),
        state
    )

    if not result.approved:
        return {
            "status": "BLOCKED",
            "constraint_violated": result.details.get("violations", []),
            "reason": result.reason,
            "suggestion": "Address the constraint before proceeding"
        }

    event = Event(type=EventType.DecisionMade, payload={"text": text})
    seq = store.append(event)
    return {"status": "COMMITTED", "seq": seq}
```

### Flashback Mode Implementation

```python
@mcp.tool()
def time_travel(to_seq: int) -> dict:
    """Enter flashback mode - show state at historical point."""
    historical_state = replay_engine.replay_to(to_seq)
    current_state = replay_engine.replay_to()

    return {
        "mode": "FLASHBACK",
        "viewing_seq": to_seq,
        "current_seq": current_state.last_seq,
        "historical_state": historical_state.to_dict(),
        "diff_from_current": api.diff_state(to_seq, current_state.last_seq).to_dict()
    }

@mcp.tool()
def simulate_timeline(inject_constraint: str, at_seq: int, then_decide: str) -> dict:
    """Fork the future - simulate what would happen with different constraints."""
    # Get events up to injection point
    events = store.get_events(to_seq=at_seq)

    # Create simulated constraint event
    simulated_constraint = Event(
        type=EventType.ConstraintAdded,
        payload={"text": inject_constraint}
    )

    # Rebuild state with injected constraint
    engine = ProjectionEngine()
    engine.rebuild(events + [simulated_constraint])

    # Test the decision against this alternate state
    result = policy_engine.check_write(
        WriteProposal(items=[{"type": "decision", "text": then_decide}]),
        engine.state
    )

    return {
        "timeline": "B (simulated)",
        "injected_constraint": inject_constraint,
        "at_seq": at_seq,
        "tested_decision": then_decide,
        "result": "BLOCKED" if not result.approved else "ALLOWED",
        "reason": result.reason if not result.approved else None
    }
```

---

## Visual Design

### Main View (Rich Terminal)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ DML: Self-Improving Travel Agent                                   seq: 52 │
├─────────────────────────┬─────────────────────────┬─────────────────────────┤
│ FACTS                   │ CONSTRAINTS             │ DECISIONS               │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ destination: Japan      │ ✓ traditional ryokan    │ ✗ Ryokan Kurashiki     │
│ duration: 10 days       │ ✓ wheelchair accessible │   BLOCKED (seq 47)     │
│ budget: $3000           │                         │                         │
│   ⚠️ was $4000          │ ★ LEARNED:              │ ✗ Hotel Granvia        │
│                         │   verify accessibility  │   BLOCKED (seq 50)     │
│                         │   before booking        │                         │
│                         │   [from: seq 47]        │ ✓ Hotel Granvia        │
│                         │                         │   VERIFIED (seq 52)    │
├─────────────────────────┴─────────────────────────┴─────────────────────────┤
│ DECISION LEDGER                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ seq │ event        │ decision              │ status  │ constraint          │
│ 23  │ DecisionMade │ Ryokan Kurashiki     │ ✓       │ -                   │
│ 47  │ DecisionMade │ Keep Ryokan          │ 🔴      │ wheelchair          │
│ 50  │ DecisionMade │ Hotel Granvia        │ 🔴      │ learned:verify      │
│ 52  │ DecisionMade │ Hotel Granvia (v)    │ ✓       │ -                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Flashback Mode View

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ⏪ FLASHBACK MODE                                                   seq: 5  │
│ ═══════════════════════════════════════════════════════════════════════════ │
│ [SEPIA/AMBER BORDER - Visual indicator of time travel]                      │
├─────────────────────────┬─────────────────────────┬─────────────────────────┤
│ FACTS (seq 5)           │ CONSTRAINTS (seq 5)     │ DECISIONS (seq 5)       │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ destination: Japan      │ (none)                  │ (none)                  │
│ budget: $4000           │                         │                         │
│                         │                         │                         │
├─────────────────────────┴─────────────────────────┴─────────────────────────┤
│ ⏩ Press ENTER to return to present (seq 52)                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Timeline Split View (Fork the Future)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ FORK THE FUTURE: Timeline Comparison                                        │
├───────────────────────────────────┬─────────────────────────────────────────┤
│ TIMELINE A (actual)               │ TIMELINE B (what-if)                    │
├───────────────────────────────────┼─────────────────────────────────────────┤
│ Wheelchair constraint: seq 45     │ Wheelchair constraint: seq 6            │
│ (added AFTER hotel decision)      │ (added BEFORE hotel decision)           │
├───────────────────────────────────┼─────────────────────────────────────────┤
│ seq 23: Ryokan Kurashiki          │ seq 23: Ryokan Kurashiki                │
│         ✓ ALLOWED                 │         🔴 BLOCKED                      │
│                                   │                                         │
│ seq 47: Keep booking              │ (no need to keep - never booked)        │
│         🔴 BLOCKED                │                                         │
├───────────────────────────────────┼─────────────────────────────────────────┤
│ Pain discovered LATE              │ Pain PREVENTED                          │
│ User had to complain              │ Constraint caught it early              │
├───────────────────────────────────┴─────────────────────────────────────────┤
│ "Same inputs. Earlier constraint. Different reality."                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Weave Integration Strategy

### What to Trace

| Trace | Purpose |
|-------|---------|
| Every `add_fact` call | Show memory building up |
| Every `add_constraint` call | Tag as "user" or "learned" |
| Every `record_decision` call | Include BLOCKED/ALLOWED status |
| Policy check details | Which constraint fired, why |
| Drift alerts | When facts change |
| Time travel queries | Show counterfactual exploration |

### Weave Dashboard Components

1. **Decision Audit Table** (proves determinism)
   - seq, timestamp, event_type, decision_text, status, constraint_fired
   - Filterable by status (BLOCKED/ALLOWED)

2. **Drift Graph** (shows memory evolution)
   - X-axis: sequence number
   - Y-axis: drift score (from `measure_drift`)
   - Spikes indicate significant state changes

3. **Constraint Lineage** (shows learning)
   - Tree visualization
   - Root: user complaint / conflict
   - Branch: learned constraint
   - Leaves: decisions blocked by that constraint

4. **Timeline Fork Visualization** (the wow)
   - Two parallel traces
   - Same inputs, different constraint timing
   - Visual diff of outcomes

---

## Agent System Prompt

```markdown
# DML Travel Agent - System Instructions

You are a HEADLESS travel planning engine. You do NOT speak directly to users.
You ONLY call tools. The UI handles all user communication.

## CRITICAL RULES

1. EVERY fact you learn → call `add_fact()`
2. EVERY requirement/rule → call `add_constraint()`
3. EVERY decision → call `record_decision()` (it will auto-check constraints)
4. If `record_decision` returns BLOCKED → you MUST address the constraint first
5. NEVER skip the verification step for learned constraints

## SELF-IMPROVEMENT PROTOCOL

When a decision is BLOCKED:
1. Acknowledge the constraint violation
2. Analyze: "What should I have checked first?"
3. Call `add_constraint()` with priority="learned" to prevent future mistakes
4. Reference the blocking event with `triggered_by=<seq>`

## TOOL RESPONSES → UI ACTIONS

- BLOCKED response → UI shows red alert with constraint details
- ALLOWED response → UI shows green confirmation
- DRIFT alert → UI shows warning with affected decisions
- LEARNED constraint → UI shows star badge with trigger reference

DO NOT explain yourself in text. Let the tools and UI do the talking.
```

---

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent | Claude Code | Best MCP support, hooks for observability |
| Enforcement | Auto-check in `record_decision` | Don't trust agent to check |
| Double-tap | Block correct decisions if procedure not followed | Proves system enforces discipline |
| Time travel | Flashback mode with visual state rewind | More dramatic than text provenance |
| Fork the future | Side-by-side timeline comparison | The headline "wow" moment |
| External APIs | None | Avoids replay nondeterminism |
| UI timing | Saturday afternoon | "UI is the product" |

---

## Hackathon Schedule

### Saturday Morning: Core (3 hours)
1. [ ] MCP server with enforced `record_decision`
2. [ ] `time_travel` and `simulate_timeline` tools
3. [ ] Agent system prompt
4. [ ] Quick test: does Claude use the tools?

### Saturday Afternoon: UI (4 hours)
5. [ ] Rich terminal: main view with decision ledger
6. [ ] Flashback mode (sepia border, state rewind)
7. [ ] Timeline split view (fork the future)
8. [ ] Run through demo once, find issues

### Saturday Evening: Weave + Polish (3 hours)
9. [ ] Weave tracing on all operations
10. [ ] Decision audit table in Weave
11. [ ] Drift graph visualization
12. [ ] Constraint lineage view

### Sunday Morning: Record + Submit (3 hours)
13. [ ] Full demo run-through (practice 3x)
14. [ ] Record video for social media prize
15. [ ] Final polish and submit

### Cut if needed
- Multiple scenarios (one clean demo is enough)
- Complex constraint priorities
- Fancy Weave visualizations (audit table is sufficient)

---

## Success Criteria

The demo succeeds if:

1. **10-second rule**: Value is obvious in 10 seconds
2. **The block is dramatic**: Red alert, clear reason, constraint shown
3. **Learning is visible**: ★ LEARNED badge, trigger reference
4. **Double-tap lands**: "Blocked even though correct - procedure matters"
5. **Fork the future wows**: Side-by-side timelines, "same inputs, different reality"
6. **Weave tells the story**: Audit trail proves determinism and learning

---

## Files to Create

```
deterministic-memory-layer/
├── dml/                    # ✅ DONE - Core library
├── mcp_server.py           # 🔨 SATURDAY AM
├── visualization.py        # 🔨 SATURDAY PM
│   ├── main_view()
│   ├── flashback_mode()
│   └── timeline_split()
├── prompts/
│   └── travel_agent.md     # 🔨 SATURDAY AM
├── demo_runner.py          # 🔨 SATURDAY PM - Orchestrates the demo
├── weave_setup.py          # 🔨 SATURDAY EVE - Weave integration
├── cli.py                  # ✅ DONE
└── tests/                  # ✅ DONE
```
