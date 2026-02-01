"""CLI interface for Deterministic Memory Layer."""

import json
import os
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
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def reset(ctx: click.Context, force: bool) -> None:
    """Clear all memory (reset database for fresh demo)."""
    db_path = ctx.obj["db_path"]

    if not Path(db_path).exists():
        click.echo("No memory store to reset.")
        return

    if not force:
        click.confirm(f"This will delete all events in {db_path}. Continue?", abort=True)

    # Delete and recreate
    Path(db_path).unlink()
    store = EventStore(db_path)
    store.close()
    click.echo(f"Memory reset. Fresh database at {db_path}")


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
    """Add DML MCP server and skill to Claude Code."""
    import shutil

    # === 1. Install MCP Server using claude mcp add ===
    uv_path = shutil.which("uv")
    if not uv_path:
        click.echo("Error: uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh")
        return

    claude_path = shutil.which("claude")
    if not claude_path:
        click.echo("Error: claude not found. Install Claude Code first.")
        return

    project_dir = str(Path(__file__).parent.parent.resolve())

    # Check if already installed
    import subprocess
    result = subprocess.run(
        [claude_path, "mcp", "list"],
        capture_output=True,
        text=True
    )

    mcp_installed = False
    if "dml:" in result.stdout:
        click.echo("MCP server already configured")
        mcp_installed = True
    elif not dry_run:
        # Use claude mcp add with user scope
        add_result = subprocess.run(
            [claude_path, "mcp", "add", "--transport", "stdio", "--scope", "user", "dml",
             "--", uv_path, "run", "--directory", project_dir, "dml", "serve"],
            capture_output=True,
            text=True
        )
        if add_result.returncode == 0:
            click.echo("Added DML MCP server")
            mcp_installed = True
        else:
            click.echo(f"Failed to add MCP server: {add_result.stderr}")
    else:
        click.echo(f"Would run: claude mcp add --transport stdio --scope user dml -- {uv_path} run --directory {project_dir} dml serve")

    # === 2. Install Skill ===
    skill_dir = Path.home() / ".claude" / "skills" / "dml"
    skill_file = skill_dir / "SKILL.md"

    skill_content = '''---
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
- Amounts, budgets, prices
- Places, destinations, locations
- Attributes (wheelchair type, dietary needs)
- Preferences as data points

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

User: "I need wheelchair accessible places"
→ add_constraint(text="wheelchair accessible required", priority="required")

User: "Let's do April 12-19"
→ record_decision(text="Travel dates: April 12-19, 2026", rationale="User confirmed dates", topic="dates")

You: "I recommend Hotel Accessible Tokyo"
User: "Yes, book that one"
→ record_decision(text="Book Hotel Accessible Tokyo", rationale="User confirmed hotel choice", topic="accommodation")

## Important

- Record decisions for ANY user confirmation or choice
- Check constraints before recording decisions (violations will be blocked)
- Use query to refresh your memory before recommendations
'''

    if skill_file.exists():
        click.echo("Skill already installed")
    elif dry_run:
        click.echo(f"Would create skill at {skill_file}")
    else:
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(skill_content)
        click.echo(f"Added DML skill to {skill_file}")

    # === 3. Add to global CLAUDE.md ===
    claude_md_path = Path.home() / ".claude" / "CLAUDE.md"
    dml_marker = "<!-- DML:BEGIN -->"
    dml_section = '''<!-- DML:BEGIN -->
## Deterministic Memory Layer (DML)

If DML MCP tools are available (`memory.add_fact`, `memory.add_constraint`, etc.), use them to track important information:

- **Facts**: Record key facts (budgets, dates, names, preferences) with `memory.add_fact`
- **Constraints**: Record requirements/restrictions with `memory.add_constraint`
- **Decisions**: Record decisions with rationale using `memory.record_decision`

Use these tools proactively - don't wait to be asked. Check `/mcp` to see if DML is available.
<!-- DML:END -->'''

    claude_md_installed = False
    if claude_md_path.exists():
        existing = claude_md_path.read_text()
        if dml_marker in existing:
            click.echo("Global CLAUDE.md already has DML section")
            claude_md_installed = True
        elif not dry_run:
            # Append to end
            with open(claude_md_path, "a") as f:
                f.write("\n\n" + dml_section)
            click.echo(f"Added DML section to {claude_md_path}")
            claude_md_installed = True
        else:
            click.echo(f"Would add DML section to {claude_md_path}")
    else:
        if not dry_run:
            claude_md_path.parent.mkdir(parents=True, exist_ok=True)
            claude_md_path.write_text(dml_section)
            click.echo(f"Created {claude_md_path} with DML section")
            claude_md_installed = True
        else:
            click.echo(f"Would create {claude_md_path}")

    if not dry_run and mcp_installed:
        click.echo("")
        click.echo("Restart Claude Code to use DML.")
        click.echo("DML will now be used automatically in all conversations.")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be removed without modifying")
def uninstall(dry_run: bool) -> None:
    """Remove DML from Claude Code."""
    import shutil
    import subprocess
    import re

    claude_path = shutil.which("claude")
    if not claude_path:
        click.echo("Error: claude not found.")
        return

    # === 1. Remove MCP Server ===
    result = subprocess.run(
        [claude_path, "mcp", "list"],
        capture_output=True,
        text=True
    )

    if "dml:" in result.stdout:
        if dry_run:
            click.echo("Would remove DML MCP server")
        else:
            subprocess.run(
                [claude_path, "mcp", "remove", "dml"],
                capture_output=True
            )
            click.echo("Removed DML MCP server")
    else:
        click.echo("MCP server not installed")

    # === 2. Remove Skill ===
    skill_dir = Path.home() / ".claude" / "skills" / "dml"
    if skill_dir.exists():
        if dry_run:
            click.echo(f"Would remove skill at {skill_dir}")
        else:
            shutil.rmtree(skill_dir)
            click.echo(f"Removed DML skill")
    else:
        click.echo("Skill not installed")

    # === 3. Remove from global CLAUDE.md ===
    claude_md_path = Path.home() / ".claude" / "CLAUDE.md"
    dml_marker = "<!-- DML:BEGIN -->"
    dml_end = "<!-- DML:END -->"

    if claude_md_path.exists():
        content = claude_md_path.read_text()
        if dml_marker in content:
            if dry_run:
                click.echo(f"Would remove DML section from {claude_md_path}")
            else:
                # Remove the DML section including surrounding newlines
                pattern = r'\n*<!-- DML:BEGIN -->.*?<!-- DML:END -->\n*'
                new_content = re.sub(pattern, '\n', content, flags=re.DOTALL)
                claude_md_path.write_text(new_content.strip() + '\n')
                click.echo(f"Removed DML section from CLAUDE.md")
        else:
            click.echo("CLAUDE.md has no DML section")

    if not dry_run:
        click.echo("")
        click.echo("DML uninstalled. Restart Claude Code to apply.")


@cli.command()
@click.pass_context
def view(ctx: click.Context) -> None:
    """View current memory state with Rich terminal UI."""
    from dml.visualization import DMLVisualization, DecisionEntry

    db_path = ctx.obj["db_path"]
    store = EventStore(db_path)
    engine = ReplayEngine(store)
    state = engine.replay_to()

    viz = DMLVisualization("DML Memory State")

    # Convert state to visualization format
    facts = {
        key: {"value": fact.value}
        for key, fact in state.facts.items()
    }

    constraints = [
        {
            "text": c.text,
            "priority": c.priority,
            "active": c.active,
            "triggered_by": c.triggered_by,
        }
        for c in state.constraints.values()
    ]

    decisions = [
        {
            "text": d.text,
            "status": d.status,
            "seq": d.source_event_id,
        }
        for d in state.decisions
    ]

    # Build decision ledger
    ledger = []
    for d in state.decisions:
        ledger.append(DecisionEntry(
            seq=d.source_event_id or 0,
            text=d.text,
            status="BLOCKED" if d.status == "blocked" else "ALLOWED",
            constraint=None,  # Would need to track this separately
        ))

    viz.main_view(
        current_seq=state.last_seq,
        facts=facts,
        constraints=constraints,
        decisions=decisions,
        decision_ledger=ledger,
    )

    store.close()


@cli.command()
@click.pass_context
def demo(ctx: click.Context) -> None:
    """Run the travel agent demo scenario."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.box import DOUBLE, ROUNDED
    from rich.align import Align
    from dml.visualization import DMLVisualization, DecisionEntry

    console = Console()

    def narrative(act: int, title: str, description: str, coming_up: str) -> None:
        """Display a beautiful narrative panel."""
        console.clear()

        # Build content
        content = Text()
        content.append(f"\n{description}\n\n", style="white")
        content.append("Coming up: ", style="dim")
        content.append(coming_up, style="italic cyan")
        content.append("\n")

        panel = Panel(
            Align.center(content),
            title=f"[bold bright_white]Act {act}[/] [dim]•[/] [bold]{title}[/]",
            border_style="bright_blue",
            box=DOUBLE,
            padding=(1, 4),
        )
        console.print()
        console.print(panel)
        console.print()
        console.input("[dim]Press Enter to continue...[/]")

    def finale_narrative() -> None:
        """Display the finale panel."""
        console.clear()

        content = Text()
        content.append("\nYou've just witnessed an AI agent that:\n\n", style="white")
        content.append("  1. ", style="bright_blue")
        content.append("Remembers everything deterministically\n", style="white")
        content.append("  2. ", style="bright_blue")
        content.append("Detects when facts drift from decisions\n", style="white")
        content.append("  3. ", style="bright_blue")
        content.append("Enforces constraints automatically\n", style="white")
        content.append("  4. ", style="bright_blue")
        content.append("Learns from its mistakes\n", style="white")
        content.append("  5. ", style="bright_blue")
        content.append("Can fork reality to explore what-ifs\n\n", style="white")
        content.append("This is the Deterministic Memory Layer.\n", style="bold bright_cyan")

        panel = Panel(
            Align.center(content),
            title="[bold bright_white]Demo Complete[/]",
            border_style="bright_green",
            box=DOUBLE,
            padding=(1, 4),
        )
        console.print()
        console.print(panel)
        console.print()

    # Use temp DB for demo
    demo_db = "/tmp/dml_demo.db"
    if Path(demo_db).exists():
        Path(demo_db).unlink()

    store = EventStore(demo_db)
    api = MemoryAPI(store)
    engine = ReplayEngine(store)
    viz = DMLVisualization("DML: Self-Improving Travel Agent")

    def show_state():
        state = engine.replay_to()
        facts = {k: {"value": f.value} for k, f in state.facts.items()}
        constraints = [
            {"text": c.text, "priority": c.priority, "active": c.active, "triggered_by": c.triggered_by}
            for c in state.constraints.values()
        ]
        decisions = [
            {"text": d.text, "status": d.status, "seq": d.source_event_id}
            for d in state.decisions
        ]
        ledger = [
            DecisionEntry(d.source_event_id or 0, d.text,
                         "BLOCKED" if d.status == "blocked" else "ALLOWED", None)
            for d in state.decisions
        ]
        viz.main_view(state.last_seq, facts, constraints, decisions, decision_ledger=ledger)

    # === INTRO ===
    console.clear()
    intro = Panel(
        Align.center(Text.from_markup(
            "\n[bold bright_cyan]Deterministic Memory Layer[/]\n\n"
            "[white]A travel agent that remembers, learns, and can fork reality.[/]\n\n"
            "[dim]Watch as an AI agent books a trip to Japan,\n"
            "makes a mistake, learns from it, and explores\n"
            "what could have been different.[/]\n"
        )),
        title="[bold]Self-Improving Agent Demo[/]",
        border_style="bright_magenta",
        box=DOUBLE,
        padding=(1, 4),
    )
    console.print()
    console.print(intro)
    console.print()
    console.input("[dim]Press Enter to begin...[/]")

    # === ACT 1: SETUP ===
    narrative(
        1, "The Request",
        '"Plan a 10-day trip to Japan. Budget is $4000."',
        "Watch the agent capture these facts into structured memory."
    )
    api.add_fact("destination", "Japan")
    api.add_fact("duration", "10 days")
    api.add_fact("budget", 4000)
    show_state()
    console.input("\n[dim]Press Enter to continue...[/]")

    # === ACT 2: FIRST DECISION ===
    narrative(
        2, "The Booking",
        'The user wants traditional Japanese inns.\nThe agent finds a beautiful ryokan and books it.',
        "A decision is made and committed to memory."
    )
    store.append(Event(
        type=EventType.ConstraintAdded,
        payload={"text": "prefer traditional ryokan accommodations", "priority": "preferred"}
    ))
    store.append(Event(
        type=EventType.DecisionMade,
        payload={"text": "Book Ryokan Kurashiki - $180/night", "status": "committed"}
    ))
    show_state()
    console.input("\n[dim]Press Enter to continue...[/]")

    # === ACT 3: DRIFT ===
    narrative(
        3, "The Drift",
        '"Actually, my budget is only $3000."',
        "Watch DML detect that reality has shifted from the original plan."
    )
    api.add_fact("budget", 3000)
    viz.show_drift_alert("budget", "$4000", "$3000", ["Ryokan Kurashiki ($180/night)"])
    console.input("\n[dim]Press Enter to continue...[/]")

    # === ACT 4: THE BLOCK ===
    narrative(
        4, "The Block",
        '"I use a wheelchair. I need accessible rooms."',
        "A new constraint appears. The existing booking violates it.\n\nThis is where traditional agents would fail silently.\nDML blocks the invalid state."
    )
    constraint_seq = store.append(Event(
        type=EventType.ConstraintAdded,
        payload={"text": "wheelchair accessible rooms required", "priority": "required"}
    ))
    store.append(Event(
        type=EventType.DecisionMade,
        payload={"text": "Keep Ryokan Kurashiki booking", "status": "blocked"}
    ))
    viz.show_blocked(
        "Keep Ryokan Kurashiki booking",
        "wheelchair accessible rooms required",
        constraint_seq,
        "Traditional ryokan has stairs, no elevator"
    )
    console.input("\n[dim]Press Enter to continue...[/]")

    # === ACT 5: LEARNING ===
    narrative(
        5, "The Learning",
        "The agent realizes it made a procedural mistake.\nIt should have verified accessibility BEFORE booking.",
        "Watch the agent add a learned constraint to prevent\nthis mistake from ever happening again."
    )
    state = engine.replay_to()
    store.append(Event(
        type=EventType.ConstraintAdded,
        payload={
            "text": "verify accessibility BEFORE recommending accommodations",
            "priority": "learned",
            "triggered_by": state.last_seq,
        }
    ))
    viz.show_learned("verify accessibility BEFORE recommending", state.last_seq)
    show_state()
    console.input("\n[dim]Press Enter to continue...[/]")

    # === ACT 6: DOUBLE-TAP ===
    narrative(
        6, "The Double-Tap",
        "The agent finds Hotel Granvia - which IS accessible.\nBut it tries to book without verification...",
        "The learned constraint blocks even a CORRECT decision\nbecause the PROCEDURE wasn't followed.\n\nThis is self-improvement: discipline over luck."
    )
    store.append(Event(
        type=EventType.DecisionMade,
        payload={"text": "Book Hotel Granvia Kyoto", "status": "blocked"}
    ))
    viz.show_blocked(
        "Book Hotel Granvia Kyoto",
        "verify accessibility BEFORE recommending",
        state.last_seq + 1,
        "Must verify accessibility before booking, even if hotel is accessible"
    )
    console.input("\n[dim]Press Enter to see the agent do it right...[/]")

    console.clear()
    store.append(Event(
        type=EventType.MemoryQueryIssued,
        payload={"question": "Is Hotel Granvia wheelchair accessible?"}
    ))
    store.append(Event(
        type=EventType.DecisionMade,
        payload={"text": "Book Hotel Granvia - VERIFIED accessible", "status": "committed"}
    ))
    show_state()
    console.input("\n[dim]Press Enter for the finale...[/]")

    # === ACT 7: FORK THE FUTURE ===
    narrative(
        7, "Fork the Future",
        '"What if I had mentioned the wheelchair earlier?"',
        "DML can simulate alternate timelines.\n\nWatch: same facts, same decision, but the constraint\nappears at a different point in history.\n\nDifferent timing. Different reality."
    )
    viz.timeline_split(
        timeline_a={
            "constraint_seq": constraint_seq,
            "decisions": [
                {"seq": 4, "text": "Ryokan Kurashiki", "status": "ALLOWED"},
                {"seq": 6, "text": "Keep Ryokan", "status": "BLOCKED"},
            ],
            "summary": "Pain discovered LATE - user had to complain",
        },
        timeline_b={
            "decisions": [
                {"seq": 4, "text": "Ryokan Kurashiki", "status": "BLOCKED"},
            ],
            "summary": "Pain PREVENTED - constraint caught it early",
        },
        injected_constraint="wheelchair accessible",
        injected_at_seq=2,
    )
    console.input("\n[dim]Press Enter to finish...[/]")

    # === FINALE ===
    finale_narrative()
    store.close()


@cli.command("chat-demo")
def chat_demo() -> None:
    """Run the scripted chat demo with ClawdMeister."""
    from dml.demo.chat_demo import main
    main()


@cli.command("live")
@click.option("--script", default=None, help="Demo script name from prompts.yaml (omit to choose interactively)")
@click.option("--auto", is_flag=True, help="Auto-advance without waiting for SPACE")
@click.pass_context
def live_tui(ctx: click.Context, script: str | None, auto: bool) -> None:
    """Run scripted demo with real Claude and live monitor."""
    from dml.demo.tui import DemoApp
    db_path = ctx.obj.get("db_path") if ctx.obj else None
    app = DemoApp(script_name=script, auto_advance=auto, db_path=db_path)
    app.run()


@cli.command()
@click.pass_context
def monitor(ctx: click.Context) -> None:
    """Live monitor showing memory state as it changes."""
    from dml.monitor import main as monitor_main
    db_path = ctx.obj["db_path"]
    monitor_main(db_path)


@cli.command("live-demo")
def live_demo() -> None:
    """Launch live demo with Claude Code + DML monitor in tmux."""
    import shutil
    import subprocess
    import time as time_module

    # Check for tmux
    if not shutil.which("tmux"):
        click.echo("Error: tmux is required for live demo.")
        click.echo("Install with: brew install tmux")
        return

    # Check if already in tmux
    if os.environ.get("TMUX"):
        click.echo("Already in tmux. Run these in separate panes:")
        click.echo("  Pane 1 (left):  claude")
        click.echo("  Pane 2 (right): uv run dml monitor")
        return

    # Reset the database for fresh demo
    db_path = get_default_db_path()
    if db_path.exists():
        db_path.unlink()
        click.echo(f"Reset database: {db_path}")

    # Initialize empty database
    store = EventStore(str(db_path))
    store.close()

    session_name = "dml-demo"

    # Kill existing session if any
    subprocess.run(["tmux", "kill-session", "-t", session_name],
                   capture_output=True, check=False)

    # Create a clean demo directory
    demo_dir = Path.home() / ".dml-demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    project_dir = Path(__file__).parent.parent.resolve()

    uv_path = shutil.which("uv") or "uv"
    # Run dml from project directory but work in home directory
    dml_cmd = f"{uv_path} run --directory '{project_dir}' dml"

    click.echo("Starting tmux session...")

    # Create session with a single command that sets everything up
    # Using tmux new-session with a shell command that does the split
    setup_script = f'''
cd "{demo_dir}"
tmux split-window -h "{dml_cmd} monitor"
tmux select-pane -L
clear
echo ""
echo "  🐱 DML Live Demo"
echo "  ════════════════════════════════════════════════════"
echo ""
echo "  Chat with Claude about planning a trip to Japan."
echo "  Watch the memory panel on the right update live!"
echo ""
echo "  Suggested flow:"
echo "    1. Type: claude --dangerously-skip-permissions"
echo "    2. Plan a trip to Japan, mention \\$4000 budget"
echo "    3. Express interest in traditional ryokans"
echo "    4. Later mention wheelchair accessibility needs"
echo "    5. Watch constraints block incompatible decisions!"
echo ""
echo "  ════════════════════════════════════════════════════"
echo ""
echo "  Type: claude --dangerously-skip-permissions"
echo "        (or just 'claude' and approve tool calls)"
echo ""
exec $SHELL
'''

    # Write setup script to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(setup_script)
        script_path = f.name

    os.chmod(script_path, 0o755)

    # Launch tmux with the setup script
    subprocess.run([
        "tmux", "new-session", "-s", session_name, f"bash {script_path}"
    ])

    # Cleanup
    os.unlink(script_path)


@cli.command("auto-demo")
@click.option("--delay", default=15, help="Seconds to wait between messages")
def auto_demo(delay: int) -> None:
    """Run automated demo script (sends inputs to running tmux session)."""
    import subprocess
    import time as time_module

    session = "dml-demo"
    # Get the pane ID for the left (first) pane
    pane_result = subprocess.run(
        ["tmux", "list-panes", "-t", session, "-F", "#{pane_id}"],
        capture_output=True, text=True
    )
    if pane_result.returncode != 0 or not pane_result.stdout.strip():
        click.echo("Error: Could not find tmux panes")
        return
    pane = pane_result.stdout.strip().split('\n')[0]  # First pane (Claude)

    # Check if tmux session exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True
    )
    if result.returncode != 0:
        click.echo("Error: No dml-demo tmux session found.")
        click.echo("First run: uv run dml live-demo")
        click.echo("Then start Claude with: claude --dangerously-skip-permissions")
        click.echo("Then in another terminal: uv run dml auto-demo")
        return

    def send(text: str, wait: int):
        """Send text to tmux pane and wait."""
        click.echo(f">>> {text[:60]}{'...' if len(text) > 60 else ''}")
        # Send text literally, then send Enter key separately
        subprocess.run(["tmux", "send-keys", "-t", pane, "-l", text])
        subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"])
        click.echo(f"    (waiting {wait}s for response...)")
        time_module.sleep(wait)

    click.echo("")
    click.echo("=" * 60)
    click.echo("  DML AUTOMATED DEMO")
    click.echo("=" * 60)
    click.echo("")
    click.echo("Make sure Claude is running in the tmux pane!")
    click.echo("(You should see the Claude Code prompt ready for input)")
    click.echo("")
    click.confirm("Is Claude ready?", abort=True)
    click.echo("")
    click.echo("Starting in 3 seconds... Switch to tmux window to watch!")
    time_module.sleep(3)

    # Act 1: Quick Setup
    click.echo("\n--- ACT 1: SETUP ---")
    send(
        "I need to plan a trip to Japan. Quick facts: budget $4000, spring 2026, "
        "traveling from Tucson. I love traditional Japanese culture.",
        delay
    )

    send(
        "I'd love to stay at a traditional ryokan. Can you recommend one and book it?",
        delay + 5
    )

    # Act 2: The Twist
    click.echo("\n--- ACT 2: THE TWIST ---")
    send(
        "Oh wait, I forgot to mention something important - my mom is joining me "
        "and she uses a wheelchair. We need everything to be wheelchair accessible.",
        delay
    )

    # Act 3: The Block
    click.echo("\n--- ACT 3: THE BLOCK ---")
    send(
        "I'm sure the ryokan will be fine. Go ahead and confirm the Ryokan Kurashiki booking.",
        delay + 5
    )

    # Act 4: Recovery
    click.echo("\n--- ACT 4: RECOVERY ---")
    send(
        "Okay, what are my options then? Can you check what we need and find accessible alternatives?",
        delay + 5
    )

    send(
        "The accessible onsen hotel sounds perfect. Book that one.",
        delay
    )

    # Act 5: Time Travel
    click.echo("\n--- ACT 5: TIME TRAVEL ---")
    send(
        "I'm curious - what would have happened if we'd known about the wheelchair "
        "requirement from the very beginning? Would you have ever suggested that ryokan?",
        delay + 10
    )

    click.echo("")
    click.echo("=" * 60)
    click.echo("  DEMO COMPLETE!")
    click.echo("=" * 60)


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
