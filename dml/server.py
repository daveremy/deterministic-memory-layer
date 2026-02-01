"""MCP server exposing DML tools for Claude Code integration."""

import json
import os
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from dml.events import Event, EventStore, EventType
from dml.memory_api import MemoryAPI
from dml.policy import PolicyEngine, WriteProposal
from dml.projections import ProjectionEngine
from dml.replay import ReplayEngine
from dml.tracing import init_tracing, TracedEventStore, TracedMemoryAPI, WEAVE_AVAILABLE


def _load_dotenv() -> None:
    """Load .env file from project directory for WANDB_API_KEY etc."""
    # Try multiple locations for .env
    candidates = [
        Path(__file__).parent.parent / ".env",  # Project root
        Path.home() / ".dml" / ".env",  # DML config directory
        Path.cwd() / ".env",  # Current working directory
    ]
    for env_path in candidates:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        os.environ.setdefault(key.strip(), value.strip())
            break  # Use first found .env


# Load .env before anything else
_load_dotenv()


def get_default_db_path() -> Path:
    """Get the default DML database path (~/.dml/memory.db)."""
    dml_dir = Path.home() / ".dml"
    dml_dir.mkdir(parents=True, exist_ok=True)
    return dml_dir / "memory.db"


# Global instances (initialized in run_server)
store: EventStore | None = None
replay_engine: ReplayEngine | None = None
policy_engine: PolicyEngine | None = None
memory_api: MemoryAPI | None = None


def get_current_state():
    """Get the current projection state."""
    return replay_engine.replay_to()


# Create MCP server
server = Server("dml")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available DML tools."""
    return [
        Tool(
            name="add_fact",
            description="Record a learned fact about the user or context. IMPORTANT: Call this IMMEDIATELY when the user mentions ANY factual information - names, dates, numbers, locations, preferences, budgets, counts, attributes. Do not wait to be asked. Examples: 'planning a trip to Japan' -> add_fact(destination, Japan); 'budget is $4000' -> add_fact(budget, 4000); '6 guests' -> add_fact(guest_count, 6).",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Fact identifier (e.g., 'budget', 'destination', 'dietary_restriction')"
                    },
                    "value": {
                        "type": "string",
                        "description": "The fact value (e.g., '3000', 'Japan', 'vegetarian')"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "How confident you are (0.0-1.0, default 1.0)",
                        "default": 1.0
                    }
                },
                "required": ["key", "value"]
            }
        ),
        Tool(
            name="add_constraint",
            description="Record a constraint or requirement. IMPORTANT: Call this when user states ANY requirement, restriction, or rule - 'must have', 'need', 'require', 'can't', 'won't', 'never', 'avoid', 'allergic to', 'prefer'. Examples: 'wheelchair accessible' -> add_constraint; 'gluten-free' -> add_constraint; 'no more than $500' -> add_constraint.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The constraint text (e.g., 'wheelchair accessible rooms required')"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["required", "preferred", "learned"],
                        "description": "Constraint priority",
                        "default": "required"
                    },
                    "triggered_by": {
                        "type": "integer",
                        "description": "If learned, the seq of the event that triggered learning"
                    }
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="record_decision",
            description="Record a decision or user confirmation. IMPORTANT: Call this when user confirms, chooses, or commits to something - 'yes', 'sounds good', 'let's do it', 'book it', 'go with that', 'I'll take option X'. AUTO-CHECKS ALL CONSTRAINTS and will be BLOCKED if decision violates any active constraint.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "What's being decided (e.g., 'Book Hotel Granvia Kyoto')"
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Why this decision was made"
                    },
                    "topic": {
                        "type": "string",
                        "description": "Category: dates, accommodation, transportation, itinerary, budget, etc."
                    },
                    "references": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Event seqs this decision is based on"
                    }
                },
                "required": ["text", "rationale"]
            }
        ),
        Tool(
            name="query_memory",
            description="Search memory for facts, constraints, or decisions. Call this BEFORE making recommendations or decisions to check for relevant constraints. Also use when user asks 'what did I say about X' or 'remind me of Y'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "What you want to know (e.g., 'wheelchair accessible')"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["facts", "constraints", "decisions", "all"],
                        "description": "What to search",
                        "default": "all"
                    }
                },
                "required": ["question"]
            }
        ),
        Tool(
            name="get_memory_context",
            description="Get the full current memory state. Use to refresh understanding of all facts, constraints, and decisions.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="trace_provenance",
            description="Trace how a fact or decision came to be. Use to explain why you know something.",
            inputSchema={
                "type": "object",
                "properties": {
                    "seq": {
                        "type": "integer",
                        "description": "The event sequence number to trace"
                    },
                    "fact_key": {
                        "type": "string",
                        "description": "Alternative: trace the fact with this key"
                    }
                }
            }
        ),
        Tool(
            name="time_travel",
            description="View memory state at a specific point in history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to_seq": {
                        "type": "integer",
                        "description": "The sequence number to travel to"
                    }
                },
                "required": ["to_seq"]
            }
        ),
        Tool(
            name="simulate_timeline",
            description="Simulate an alternate timeline: 'What if this constraint existed earlier?'",
            inputSchema={
                "type": "object",
                "properties": {
                    "inject_constraint": {
                        "type": "string",
                        "description": "Constraint to inject"
                    },
                    "at_seq": {
                        "type": "integer",
                        "description": "Where to inject it in the timeline"
                    },
                    "then_decide": {
                        "type": "string",
                        "description": "Decision to test against the modified timeline"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["required", "preferred", "learned"],
                        "default": "required"
                    }
                },
                "required": ["inject_constraint", "at_seq", "then_decide"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "add_fact":
            result = handle_add_fact(arguments)
        elif name == "add_constraint":
            result = handle_add_constraint(arguments)
        elif name == "record_decision":
            result = handle_record_decision(arguments)
        elif name == "query_memory":
            result = handle_query_memory(arguments)
        elif name == "get_memory_context":
            result = handle_get_memory_context(arguments)
        elif name == "trace_provenance":
            result = handle_trace_provenance(arguments)
        elif name == "time_travel":
            result = handle_time_travel(arguments)
        elif name == "simulate_timeline":
            result = handle_simulate_timeline(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


def handle_add_fact(args: dict[str, Any]) -> dict[str, Any]:
    """Handle add_fact tool."""
    key = args["key"]
    value = args["value"]
    confidence = args.get("confidence", 1.0)

    # Check for existing fact (drift detection)
    state = get_current_state()
    previous_value = None
    drift_alert = False
    if key in state.facts:
        previous_value = state.facts[key].value
        if previous_value != value:
            drift_alert = True

    # Use MemoryAPI.add_fact for proper supersession tracking
    seq = memory_api.add_fact(key, value, confidence)

    result = {
        "seq": seq,
        "key": key,
        "value": value,
    }
    if previous_value is not None:
        result["previous_value"] = previous_value
    if drift_alert:
        result["drift_alert"] = True

    return result


def handle_add_constraint(args: dict[str, Any]) -> dict[str, Any]:
    """Handle add_constraint tool."""
    text = args["text"]
    priority = args.get("priority", "required")
    triggered_by = args.get("triggered_by")

    # Validate: learned constraints require triggered_by
    if priority == "learned" and triggered_by is None:
        return {"error": "Learned constraints require 'triggered_by' parameter"}

    event = Event(
        type=EventType.ConstraintAdded,
        payload={
            "text": text,
            "priority": priority,
            "triggered_by": triggered_by,
        }
    )
    seq = store.append(event)

    result = {
        "seq": seq,
        "constraint": text,
        "priority": priority,
    }
    if triggered_by is not None:
        result["triggered_by"] = triggered_by

    return result


def handle_record_decision(args: dict[str, Any]) -> dict[str, Any]:
    """Handle record_decision tool with policy enforcement."""
    text = args["text"]
    rationale = args["rationale"]
    topic = args.get("topic")
    references = args.get("references", [])

    # Get current state for policy check
    state = get_current_state()

    # Create decision item for policy check
    decision_item = {
        "text": text,
        "rationale": rationale,
        "topic": topic,
        "references": references,
        "type": "decision"
    }

    # Check policy
    proposal = WriteProposal(items=[decision_item])
    result = policy_engine.check_write(proposal, state)

    if result.rejected:
        # Return BLOCKED with details
        violation = result.details.get("violations", [{}])[0]
        return {
            "status": "BLOCKED",
            "violated_constraint_seq": violation.get("constraint_source"),
            "constraint": violation.get("constraint"),
            "reason": result.reason,
            "suggestion": "Call query_memory to verify requirements before deciding"
        }

    # Commit the decision
    payload = {
        "text": text,
        "rationale": rationale,
        "references": references,
        "status": "committed"
    }
    if topic:
        payload["topic"] = topic

    event = Event(
        type=EventType.DecisionMade,
        payload=payload
    )
    seq = store.append(event)

    return {
        "status": "COMMITTED",
        "seq": seq,
        "decision": text,
        "topic": topic,
        "rationale": rationale
    }


def handle_query_memory(args: dict[str, Any]) -> dict[str, Any]:
    """Handle query_memory tool - emits MemoryQueryIssued for verification tracking."""
    question = args["question"]
    scope = args.get("scope", "all")

    # Emit MemoryQueryIssued event for verification tracking
    query_event = Event(
        type=EventType.MemoryQueryIssued,
        payload={"question": question, "scope": scope}
    )
    query_seq = store.append(query_event)

    # Get current state and search
    state = get_current_state()
    question_lower = question.lower()

    result: dict[str, Any] = {"query_seq": query_seq}

    # Search facts
    if scope in ("facts", "all"):
        matching_facts = []
        for key, fact in state.facts.items():
            if question_lower in key.lower() or question_lower in str(fact.value).lower():
                matching_facts.append({
                    "key": fact.key,
                    "value": fact.value,
                    "confidence": fact.confidence,
                    "seq": fact.source_event_id,
                })
        result["facts"] = matching_facts

    # Search constraints
    if scope in ("constraints", "all"):
        matching_constraints = []
        for text, constraint in state.constraints.items():
            if question_lower in text.lower():
                matching_constraints.append({
                    "text": constraint.text,
                    "priority": constraint.priority,
                    "active": constraint.active,
                    "seq": constraint.source_event_id,
                })
        result["constraints"] = matching_constraints

    # Search decisions
    if scope in ("decisions", "all"):
        matching_decisions = []
        for decision in state.decisions:
            if question_lower in decision.text.lower():
                matching_decisions.append({
                    "text": decision.text,
                    "status": decision.status,
                    "seq": decision.source_event_id,
                })
        result["decisions"] = matching_decisions

    return result


def handle_get_memory_context(args: dict[str, Any]) -> dict[str, Any]:
    """Handle get_memory_context tool."""
    state = get_current_state()

    return {
        "current_seq": state.last_seq,
        "facts": {
            key: {
                "value": fact.value,
                "confidence": fact.confidence,
                "seq": fact.source_event_id,
            }
            for key, fact in state.facts.items()
        },
        "constraints": [
            {
                "text": c.text,
                "priority": c.priority,
                "active": c.active,
                "seq": c.source_event_id,
            }
            for c in state.constraints.values()
        ],
        "decisions": [
            {
                "text": d.text,
                "status": d.status,
                "seq": d.source_event_id,
            }
            for d in state.decisions
        ],
        "pending_verifications": list(state.pending_verifications),
    }


def handle_trace_provenance(args: dict[str, Any]) -> dict[str, Any]:
    """Handle trace_provenance tool."""
    seq = args.get("seq")
    fact_key = args.get("fact_key")

    if seq is None and fact_key is None:
        return {"error": "Provide either 'seq' or 'fact_key'"}

    # If fact_key provided, find its source event
    if fact_key and seq is None:
        state = get_current_state()
        if fact_key not in state.facts:
            return {"error": f"No fact found with key: {fact_key}"}
        seq = state.facts[fact_key].source_event_id

    # Build provenance chain by following caused_by links
    chain = []
    current_seq = seq
    visited = set()

    while current_seq is not None and current_seq not in visited:
        visited.add(current_seq)
        event = store.get_event(current_seq)
        if event is None:
            break
        chain.append({
            "seq": event.global_seq,
            "type": event.type.value,
            "payload": event.payload,
            "caused_by": event.caused_by,
        })
        current_seq = event.caused_by

    return {"chain": chain}


def handle_time_travel(args: dict[str, Any]) -> dict[str, Any]:
    """Handle time_travel tool."""
    to_seq = args["to_seq"]

    # Get historical state
    historical_state = replay_engine.replay_to(to_seq)
    current_state = get_current_state()

    # Compute diff
    added = []
    removed = []
    changed = []

    # Compare facts
    for key in set(current_state.facts.keys()) | set(historical_state.facts.keys()):
        in_current = key in current_state.facts
        in_historical = key in historical_state.facts
        if in_current and not in_historical:
            added.append({"type": "fact", "key": key})
        elif in_historical and not in_current:
            removed.append({"type": "fact", "key": key})
        elif in_current and in_historical:
            if current_state.facts[key].value != historical_state.facts[key].value:
                changed.append({
                    "type": "fact",
                    "key": key,
                    "was": historical_state.facts[key].value,
                    "now": current_state.facts[key].value,
                })

    return {
        "mode": "FLASHBACK",
        "viewing_seq": to_seq,
        "current_seq": current_state.last_seq,
        "historical_state": historical_state.to_dict(),
        "diff_from_current": {
            "added": added,
            "removed": removed,
            "changed": changed,
        }
    }


def handle_simulate_timeline(args: dict[str, Any]) -> dict[str, Any]:
    """Handle simulate_timeline tool - counterfactual simulation."""
    inject_constraint = args["inject_constraint"]
    at_seq = args["at_seq"]
    then_decide = args["then_decide"]
    priority = args.get("priority", "required")

    # Get events up to at_seq
    events = store.get_events(to_seq=at_seq)

    # Create synthetic constraint event
    synthetic_constraint = Event(
        type=EventType.ConstraintAdded,
        payload={
            "text": inject_constraint,
            "priority": priority,
        }
    )

    # Rebuild state with injected constraint
    engine = ProjectionEngine()
    for event in events:
        engine.apply_event(event)
    engine.apply_event(synthetic_constraint)
    alternate_state = engine.state

    # Test decision against alternate state
    decision_item = {"text": then_decide, "type": "decision"}
    proposal = WriteProposal(items=[decision_item])
    result = policy_engine.check_write(proposal, alternate_state)

    return {
        "timeline": "B (simulated)",
        "injected_constraint": inject_constraint,
        "injected_at_seq": at_seq,
        "injected_priority": priority,
        "tested_decision": then_decide,
        "result": "BLOCKED" if result.rejected else "ALLOWED",
        "reason": result.reason if result.rejected else None,
    }


def run_server(db_path: str | None = None) -> None:
    """Run the MCP server."""
    global store, replay_engine, policy_engine, memory_api

    # Initialize database
    if db_path is None:
        db_path = os.environ.get("DML_DB_PATH", str(get_default_db_path()))

    # Check if Weave tracing should be enabled
    weave_enabled = False
    if WEAVE_AVAILABLE and (os.environ.get("WANDB_API_KEY") or os.environ.get("WEAVE_PROJECT")):
        weave_enabled = init_tracing("dml-mcp-server")

    # Use traced wrappers when Weave is enabled
    base_store = EventStore(db_path)
    if weave_enabled:
        store = TracedEventStore(base_store)
        memory_api = TracedMemoryAPI(MemoryAPI(store))
    else:
        store = base_store
        memory_api = MemoryAPI(base_store)

    replay_engine = ReplayEngine(base_store)  # Replay uses base store
    policy_engine = PolicyEngine()

    # Run server
    import asyncio

    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(main())
