# DML Workflow Patterns

## 1. Verify-Decide Workflow
The core pattern for any booking/selection decision.

```
User request → add_fact (capture requirements)
            → query_memory (verify constraints)
            → record_decision (with references)
            → Success OR learn from block
```

### Example Flow
1. User: "I need a hotel in Kyoto with wheelchair access"
2. Agent: `add_fact(key="destination", value="Kyoto")`
3. Agent: `add_constraint(text="wheelchair accessible rooms required")`
4. Agent: `query_memory(question="accessibility")` → seq: 5
5. Agent: `record_decision(text="booking Hotel Granvia", references=[5])`

## 2. Learn-Constrain Workflow
How the agent improves from mistakes.

```
Decision BLOCKED → Read reason
                → Identify missing step
                → add_constraint(priority="learned", triggered_by=...)
                → Future decisions auto-checked
```

### Example Flow
1. Agent tries to book without checking accessibility
2. Gets BLOCKED: "verify accessibility before booking"
3. Agent: `add_constraint(text="verify accessibility before booking", priority="learned", triggered_by=3)`
4. Next time: Agent must query before booking or gets blocked

## 3. Explain-Trace Workflow
For transparency and debugging.

```
User asks "why did you pick X?" → trace_provenance(seq)
                                → Show causal chain
                                → Each step has source event
```

### Example Flow
1. User: "Why did you pick Hotel Granvia?"
2. Agent: `trace_provenance(seq=6)` (the decision event)
3. Shows: Decision → based on query → which found accessibility fact → from user requirement

## 4. What-If Workflow
For demonstrating counterfactuals.

```
After mistake → simulate_timeline(inject early, test decision)
             → Show: "If we knew this earlier, we'd have caught it"
             → Proves determinism
```

### Example Flow
1. Agent made mistake booking non-accessible hotel
2. Agent: `simulate_timeline(inject_constraint="wheelchair required", at_seq=1, then_decide="booking Hotel Sakura")`
3. Result: BLOCKED - proves constraint would have prevented the mistake

## 5. Drift-Detection Workflow
When facts change mid-conversation.

```
add_fact("budget", "4000") → seq: 3
... later ...
add_fact("budget", "3000") → {drift_alert: true, previous_value: "4000"}
                          → Agent notified of change
                          → Can review decisions based on old value
```

### Example Flow
1. User: "My budget is $4000"
2. Agent books expensive hotel
3. User: "Actually my budget is $3000"
4. Agent: `add_fact(key="budget", value="3000")` → drift_alert: true
5. Agent should review if booked hotel fits new budget

## 6. Context Refresh Workflow
When starting a new turn or resuming conversation.

```
get_memory_context() → Full state snapshot
                    → All facts, constraints, decisions
                    → Current pending verifications
```

### Example Flow
1. New conversation turn starts
2. Agent: `get_memory_context()`
3. Gets: {facts: {...}, constraints: [...], decisions: [...]}
4. Agent now has full context without relying on internal memory
