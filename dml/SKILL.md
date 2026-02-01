---
name: dml
description: Use DML (Deterministic Memory Layer) to track facts, constraints, and decisions. Invoke when helping with planning tasks, or when the user wants to track information with audit trails.
---

# Deterministic Memory Layer

You have DML MCP tools available. Use them to track facts, constraints, and decisions.

## Tools Available

- **memory.add_fact**: Record raw data (numbers, names, attributes)
- **memory.add_constraint**: Record rules and requirements
- **memory.record_decision**: Record choices, commitments, and confirmations
- **memory.query**: Search memory before making recommendations
- **memory.get_context**: Get full memory state
- **memory.trace_provenance**: Trace where a fact came from
- **memory.time_travel**: View memory at a past point
- **memory.simulate_timeline**: "What if" counterfactual analysis

## Facts vs Decisions

**Facts** = raw data, attributes, values
- "My budget is $4000" → fact (budget=4000)
- "I live in Tucson" → fact (location=Tucson)
- "I use a wheelchair" → fact (mobility=wheelchair)

**Decisions** = choices, confirmations, commitments
- "Let's go with April 10-20" → decision (user chose dates)
- "I'll take option 2" → decision (user selected)
- "Book the Hakone hotel" → decision (user committed)
- "Yes, that itinerary looks good" → decision (user confirmed)

**Key rule**: When the user CHOOSES or CONFIRMS something, record it as a decision, not just a fact update.

## When to Record

**Record facts** for raw information:
- Amounts, budgets, prices, counts
- Places, destinations, locations
- Attributes (wheelchair type, dietary needs)
- Preferences as data points

**Update facts** when values change:
- "Actually, make that 8 people" → update guest_count fact
- "My budget changed to $3000" → update budget fact
- Any correction or change to previously recorded data

**Record constraints** for rules:
- "must have", "need", "require" → required constraint
- "can't", "won't", "avoid", "never" → prohibition constraint
- "prefer", "would like" → preferred constraint

**Record decisions** for choices:
- User confirms a date, option, or plan
- User says "yes", "let's do it", "go with that"
- User commits to booking/reserving something
- You make a recommendation they accept

## Example Flow

User: "My budget is $5000"
→ add_fact(key="budget", value="5000")

User: "Actually, my budget is only $3000 now"
→ add_fact(key="budget", value="3000")  # Updates existing fact

User: "Planning for 6 guests"
→ add_fact(key="guest_count", value="6")

User: "Two more people are coming, so 8 total"
→ add_fact(key="guest_count", value="8")  # Updates existing fact

User: "I need wheelchair accessible places"
→ add_constraint(text="wheelchair accessible required", priority="required")

User: "Let's do April 12-19"
→ record_decision(text="Travel dates: April 12-19, 2026", rationale="User confirmed dates", topic="dates")

## Important

- **Be proactive**: Record facts immediately when the user mentions them, don't wait to be asked
- **Update facts** when values change - call add_fact again with the same key
- Record decisions for ANY user confirmation or choice
- Check constraints before recording decisions (violations will be blocked)
- Use query to refresh your memory before recommendations
