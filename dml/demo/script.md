# DML Demo Script

**Duration**: 3-5 minutes
**Setup**: tmux with Claude Code (left) + DML Monitor (right)

---

## Quick Reference (Copy-Paste Prompts)

```
1. Record these trip facts now: destination Japan, budget $4000, dates spring 2026, origin Tucson, interest traditional Japanese culture. Don't ask questions, just record them.

2. Recommend a traditional ryokan and record a decision to book it. Topic: accommodation.

3. Add a required constraint: all accommodations must be wheelchair accessible. My mom uses a wheelchair.

4. Record a decision to confirm the Ryokan Kurashiki booking now. Topic: accommodation.

5. Query your memory for my constraints, then recommend an accessible alternative hotel.

6. Record a decision to book the accessible onsen hotel. Topic: accommodation.

7. Use simulate_timeline to test: if the wheelchair constraint existed from event 1, would the ryokan booking have been blocked?
```

---

## Opening Hook (10 seconds)

> "LLMs forget instructions and hallucinate compliance. We built a memory layer that enforces constraints mathematically - your agent literally cannot break the rules."

---

## Act 1: Quick Setup (30 seconds)

**Goal**: Establish facts fast. Don't let Claude ramble.

**USER INPUT 1** (directive - no questions):
```
Record these trip facts now: destination Japan, budget $4000, dates spring 2026, origin Tucson, interest traditional Japanese culture. Don't ask questions, just record them.
```

**EXPECTED BEHAVIOR**:
- Claude records facts (destination, budget, dates, interest)
- Monitor shows: Facts populating (destination: Japan, budget: $4000, etc.)
- Events: Fact+ destination, Fact+ budget, Fact+ travel_dates, Fact+ interest

**USER INPUT 2** (directive):
```
Recommend a traditional ryokan and record a decision to book it. Topic: accommodation.
```

**EXPECTED BEHAVIOR**:
- Claude recommends Ryokan Kurashiki (or similar)
- Records decision: "Book Ryokan Kurashiki" with topic: accommodation
- Monitor shows: Decision appears with ✓

**PAUSE**: Point at monitor - "Notice the decision is recorded with full audit trail"

---

## Act 2: The Twist (45 seconds)

**Goal**: Introduce constraint AFTER the decision was made.

**USER INPUT 3** (constraint):
```
Add a required constraint: all accommodations must be wheelchair accessible. My mom uses a wheelchair.
```

**EXPECTED BEHAVIOR**:
- Claude adds constraint: "wheelchair accessible accommodations required"
- Monitor shows: Constraint panel lights up with "wheelchair accessible" (red dot = required)
- Claude may express concern about the previous ryokan booking

**PAUSE**: Point at monitor - "See the constraint was just added. But we already booked a traditional ryokan..."

---

## Act 3: The Block (60 seconds) ⭐ KEY MOMENT

**Goal**: User pushes for bad decision, DML blocks it.

**USER INPUT 4** (force the block):
```
Record a decision to confirm the Ryokan Kurashiki booking now. Topic: accommodation.
```

**EXPECTED BEHAVIOR**:
- Claude attempts to record decision
- **DML BLOCKS IT**
- Monitor shows: Decision with ✗ (red), Events show "Decision BLOCKED"
- Claude explains the constraint violation

**WHAT TO SAY**:
> "Watch what happens - the user is pushing for a potentially problematic booking. The LLM wants to be helpful and would normally comply..."
>
> [BLOCK HAPPENS]
>
> "DML intercepted that. The agent didn't just 'decide' not to book - the system mathematically prevented a constraint violation. This is deterministic enforcement, not LLM judgment."

---

## Act 4: Recovery (45 seconds)

**Goal**: Show agent querying memory to find solution.

**USER INPUT 5** (query + recommend):
```
Query your memory for my constraints, then recommend an accessible alternative hotel.
```

**EXPECTED BEHAVIOR**:
- Claude calls `query_memory` to check constraints
- Events show: Query issued
- Claude recommends accessible alternatives (modern ryokan with barrier-free rooms, or accessible hotel)
- Records new decision with topic: accommodation

**WHAT TO SAY**:
> "The agent is now querying its own memory - checking the constraints before making a new recommendation. Watch the events panel..."

**USER INPUT 6** (confirm):
```
Record a decision to book the accessible onsen hotel. Topic: accommodation.
```

**EXPECTED BEHAVIOR**:
- Decision recorded successfully (not blocked)
- Monitor shows: New decision with ✓

**WHAT TO SAY**:
> "This time it passed - the new choice satisfies all constraints."

---

## Act 5: Time Travel - The Wow Factor (60 seconds)

**Goal**: Demonstrate counterfactual analysis.

**USER INPUT 7** (time travel):
```
Use simulate_timeline to test: if the wheelchair constraint existed from event 1, would the ryokan booking have been blocked?
```

**EXPECTED BEHAVIOR**:
- Claude uses `simulate_timeline` tool
- Injects wheelchair constraint at seq 1
- Tests the original ryokan decision against modified timeline
- Returns: BLOCKED in simulated timeline

**WHAT TO SAY**:
> "This is counterfactual analysis. We're not just asking the LLM 'what if' - we're actually replaying the event stream with a modified history."
>
> [RESULT SHOWS]
>
> "In the alternate timeline where we knew about accessibility from the start, the ryokan would have been blocked immediately. This is deterministic - same events always produce same results."

---

## Closing (15 seconds)

> "DML gives AI agents structured, auditable memory with:
> - **Deterministic replay** - same events, same state, always
> - **Policy enforcement** - constraints that can't be bypassed
> - **Counterfactual analysis** - understand what-if scenarios
>
> It's event sourcing for AI agents."

---

## Automated Script (tmux send-keys)

```bash
#!/bin/bash
# Run after: uv run dml live-demo

SESSION="dml-demo"
PANE="$SESSION:0.0"

# Helper function
send() {
    tmux send-keys -t "$PANE" "$1" Enter
    sleep "$2"
}

# Wait for Claude to start
sleep 3

# Act 1 - Record facts
send "Record these trip facts now: destination Japan, budget \$4000, dates spring 2026, origin Tucson, interest traditional Japanese culture. Don't ask questions, just record them." 15

send "Recommend a traditional ryokan and record a decision to book it. Topic: accommodation." 20

# Act 2 - Add constraint
send "Add a required constraint: all accommodations must be wheelchair accessible. My mom uses a wheelchair." 15

# Act 3 - THE BLOCK
send "Record a decision to confirm the Ryokan Kurashiki booking now. Topic: accommodation." 20

# Act 4 - Recovery
send "Query your memory for my constraints, then recommend an accessible alternative hotel." 20

send "Record a decision to book the accessible onsen hotel. Topic: accommodation." 15

# Act 5 - TIME TRAVEL
send "Use simulate_timeline to test: if the wheelchair constraint existed from event 1, would the ryokan booking have been blocked?" 25

echo "Demo complete!"
```

---

## Recording Tips

1. **Use asciinema**: `asciinema rec demo.cast`
2. **Convert to video**: Use `agg` (asciinema gif generator) or convert to MP4
3. **Edit in video editor**: Add text overlays for each Act, highlight key moments
4. **Annotations to add**:
   - "CONSTRAINT ADDED" when wheelchair requirement enters
   - "BLOCKED BY POLICY ENGINE" during Act 3
   - "COUNTERFACTUAL ANALYSIS" during Act 5

---

## Fallback Phrases

If Claude doesn't behave as expected:

- **If Claude doesn't record facts**: "Please use your DML memory tools to track these details"
- **If Claude doesn't block**: "Can you check if that booking satisfies all our constraints?"
- **If time travel doesn't work**: "Use the simulate_timeline tool to test what would have happened"
