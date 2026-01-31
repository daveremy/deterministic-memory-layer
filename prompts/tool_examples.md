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

## Pattern 5: Drift Detection

```python
# User updates their budget
add_fact(key="budget", value="2500")
# → {seq: 10, key: "budget", value: "2500", previous_value: "3000", drift_alert: true}

# The drift_alert tells you to review decisions based on old value
```

## Anti-Patterns (Don't Do This)

```python
# ❌ Deciding without querying first
record_decision(text="booking Hotel Sakura", rationale="looks good")
# Will be BLOCKED if "verify X before booking" constraint exists

# ❌ Not including references
query_memory("accessibility")  # query_seq: 5
record_decision(text="booking Hotel", rationale="accessible", references=[])
# Missing reference - loses verification chain

# ❌ Retrying blocked decision unchanged
result = record_decision(...)  # BLOCKED
record_decision(...)  # Same thing again - still BLOCKED!
```
