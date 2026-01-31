"""CLI interface for Deterministic Memory Layer."""

import json
import sys
from pathlib import Path

import click

from dml.events import Event, EventStore, EventType
from dml.memory_api import MemoryAPI
from dml.replay import ReplayEngine


def get_default_db_path() -> Path:
    """Get the default DML database path (~/.dml/memory.db)."""
    dml_dir = Path.home() / ".dml"
    dml_dir.mkdir(parents=True, exist_ok=True)
    return dml_dir / "memory.db"


@click.group()
@click.option(
    "--db",
    default=None,
    help="Path to the memory database. Defaults to ~/.dml/memory.db",
    type=click.Path(),
)
@click.pass_context
def cli(ctx: click.Context, db: str | None) -> None:
    """Deterministic Memory Layer CLI."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db or str(get_default_db_path())


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize a new memory store."""
    db_path = ctx.obj["db_path"]
    if Path(db_path).exists():
        click.echo(f"Memory store already exists at {db_path}")
        return

    store = EventStore(db_path)
    store.close()
    click.echo(f"Initialized memory store at {db_path}")


@cli.command()
@click.argument("event_type")
@click.argument("payload")
@click.option("--turn-id", type=int, help="Turn ID for the event.")
@click.option("--caused-by", type=int, help="Sequence of causing event.")
@click.option("--correlation-id", help="Correlation ID for provenance.")
@click.pass_context
def append(
    ctx: click.Context,
    event_type: str,
    payload: str,
    turn_id: int | None,
    caused_by: int | None,
    correlation_id: str | None,
) -> None:
    """Append an event to the store."""
    db_path = ctx.obj["db_path"]

    # Validate event type
    try:
        etype = EventType(event_type)
    except ValueError:
        valid = [e.value for e in EventType]
        click.echo(f"Invalid event type: {event_type}")
        click.echo(f"Valid types: {', '.join(valid)}")
        return

    # Parse payload
    try:
        payload_dict = json.loads(payload)
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON payload: {e}")
        return

    store = EventStore(db_path)
    event = Event(
        type=etype,
        payload=payload_dict,
        turn_id=turn_id,
        caused_by=caused_by,
        correlation_id=correlation_id,
    )
    seq = store.append(event)
    store.close()

    click.echo(f"Appended event with seq={seq}")


@cli.command()
@click.option("--to", "to_seq", type=int, help="Replay up to this sequence.")
@click.option(
    "--exclude",
    help="Comma-separated event IDs to exclude (counterfactual).",
)
@click.pass_context
def replay(
    ctx: click.Context,
    to_seq: int | None,
    exclude: str | None,
) -> None:
    """Replay events and show state."""
    db_path = ctx.obj["db_path"]
    store = EventStore(db_path)
    engine = ReplayEngine(store)

    if exclude:
        try:
            exclude_ids = [int(x.strip()) for x in exclude.split(",")]
        except ValueError:
            click.echo("Error: --exclude must be comma-separated integers (e.g., '1,2,3')")
            store.close()
            return
        state = engine.replay_excluding(exclude_ids)
        click.echo(f"State (excluding events {exclude_ids}):")
    elif to_seq is not None:
        state = engine.replay_to(to_seq)
        click.echo(f"State at seq={to_seq}:")
    else:
        state = engine.replay_to()
        click.echo("Current state:")

    click.echo(json.dumps(state.to_dict(), indent=2))
    store.close()


@cli.command()
@click.argument("search_query")
@click.pass_context
def query(ctx: click.Context, search_query: str) -> None:
    """Search memory for facts."""
    db_path = ctx.obj["db_path"]
    store = EventStore(db_path)
    api = MemoryAPI(store)

    results = api.search(search_query)
    if not results:
        click.echo("No results found.")
    else:
        click.echo(f"Found {len(results)} result(s):")
        for fact in results:
            click.echo(json.dumps(fact.to_dict(), indent=2))

    store.close()


@cli.command()
@click.argument("key")
@click.pass_context
def trace(ctx: click.Context, key: str) -> None:
    """Trace provenance chain for a fact key."""
    db_path = ctx.obj["db_path"]
    store = EventStore(db_path)
    api = MemoryAPI(store)

    chain = api.trace_provenance(key)
    if not chain:
        click.echo(f"No provenance found for key: {key}")
    else:
        click.echo(f"Provenance chain for '{key}' ({len(chain)} events):")
        for event in chain:
            click.echo(f"  seq={event.global_seq}: {event.type.value}")
            click.echo(f"    payload: {json.dumps(event.payload)}")

    store.close()


@cli.command()
@click.argument("seq1", type=int)
@click.argument("seq2", type=int)
@click.pass_context
def diff(ctx: click.Context, seq1: int, seq2: int) -> None:
    """Compare states at two sequence points."""
    db_path = ctx.obj["db_path"]
    store = EventStore(db_path)
    api = MemoryAPI(store)

    state_diff = api.diff_state(seq1, seq2)
    click.echo(f"Diff between seq={seq1} and seq={seq2}:")
    click.echo(json.dumps(state_diff.to_dict(), indent=2))

    store.close()


@cli.command()
@click.argument("seq1", type=int)
@click.argument("seq2", type=int)
@click.pass_context
def drift(ctx: click.Context, seq1: int, seq2: int) -> None:
    """Measure drift between two sequence points."""
    db_path = ctx.obj["db_path"]
    store = EventStore(db_path)
    api = MemoryAPI(store)

    metrics = api.measure_drift(seq1, seq2)
    click.echo(f"Drift metrics between seq={seq1} and seq={seq2}:")
    click.echo(json.dumps(metrics.to_dict(), indent=2))

    store.close()


@cli.command("eval")
@click.pass_context
def run_eval(ctx: click.Context) -> None:
    """Run evaluation workflow (baseline vs policy)."""
    click.echo("Running evaluation workflow...")
    click.echo("=" * 50)

    # Create a fresh store for eval
    eval_db = "eval_memory.db"
    if Path(eval_db).exists():
        Path(eval_db).unlink()

    store = EventStore(eval_db)
    api = MemoryAPI(store)

    # Step 1: Add a constraint
    click.echo("\n1. Adding constraint: 'Never use eval()'")
    constraint_event = Event(
        type=EventType.ConstraintAdded,
        payload={"text": "Never use eval()"},
        turn_id=1,
    )
    seq1 = store.append(constraint_event)
    click.echo(f"   Constraint added at seq={seq1}")

    # Step 2: Try to propose a violating write
    click.echo("\n2. Proposing decision that uses eval()...")
    proposal_id, prop_seq = api.propose_writes(
        items=[{"type": "decision", "text": "Use eval() to parse user input"}],
        turn_id=2,
    )
    click.echo(f"   Proposal created: {proposal_id} at seq={prop_seq}")

    # Step 3: Try to commit - should be rejected
    click.echo("\n3. Attempting to commit (should be rejected)...")
    result = api.commit_writes(proposal_id, turn_id=2)
    if hasattr(result, "approved") and not result.approved:
        click.echo(f"   REJECTED: {result.reason}")
        click.echo(f"   Details: {json.dumps(result.details, indent=4)}")
    else:
        click.echo(f"   Committed at seq={result}")

    # Step 4: Counterfactual - replay without constraint
    click.echo("\n4. Counterfactual: What if constraint didn't exist?")
    engine = ReplayEngine(store)
    state_without_constraint = engine.replay_excluding([seq1])
    click.echo(f"   Active constraints: {len([c for c in state_without_constraint.constraints.values() if c.active])}")

    # Step 5: Now try to add a compliant decision
    click.echo("\n5. Adding compliant decision...")
    proposal_id2, _ = api.propose_writes(
        items=[{"type": "decision", "text": "Use json.loads() to parse user input"}],
        turn_id=3,
    )
    result2 = api.commit_writes(proposal_id2, turn_id=3)
    if isinstance(result2, int):
        click.echo(f"   APPROVED and committed at seq={result2}")
    else:
        click.echo(f"   Unexpected result: {result2}")

    # Step 6: Show drift
    click.echo("\n6. Measuring drift from start to end...")
    max_seq = store.get_max_seq()
    drift_metrics = api.measure_drift(0, max_seq)
    click.echo(f"   {json.dumps(drift_metrics.to_dict(), indent=4)}")

    store.close()
    click.echo("\n" + "=" * 50)
    click.echo("Evaluation complete!")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be added without modifying")
def install(dry_run: bool) -> None:
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
        try:
            with open(config_path) as f:
                config = json.load(f)
        except json.JSONDecodeError:
            click.echo(f"Error: {config_path} contains invalid JSON")
            return

        # Backup before modifying
        if not dry_run:
            backup_path = config_path.with_suffix(".json.backup")
            import shutil
            shutil.copy(config_path, backup_path)
            click.echo(f"Backed up existing config to {backup_path}")
    else:
        config = {"mcpServers": {}}
        if not dry_run:
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


@cli.command()
@click.option("--init", "do_init", is_flag=True, help="Initialize DB if it doesn't exist")
def serve(do_init: bool) -> None:
    """Start the DML MCP server."""
    # Import here to avoid circular imports and only load when needed
    try:
        from dml.server import run_server
    except ImportError:
        click.echo("Error: MCP server not yet implemented. Run after completing server.py")
        return

    db_path = get_default_db_path()

    if do_init and not db_path.exists():
        store = EventStore(str(db_path))
        store.close()
        click.echo(f"Initialized memory store at {db_path}", err=True)

    click.echo(f"Starting DML MCP server (db: {db_path})...", err=True)
    run_server(str(db_path))


if __name__ == "__main__":
    cli()
