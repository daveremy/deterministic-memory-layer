"""Live memory monitor - watches DML database and displays state in real-time."""

import time
from pathlib import Path

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.box import ROUNDED, DOUBLE
from rich.table import Table

from dml.events import EventStore
from dml.replay import ReplayEngine


class DMLMonitor:
    """Live monitor for DML memory state."""

    def __init__(self, db_path: str | None = None):
        self.console = Console()

        # Use default path if not specified
        if db_path is None:
            db_path = str(Path.home() / ".dml" / "memory.db")

        self.db_path = db_path
        self.last_seq = -1
        self.flash_until = 0  # Timestamp when flash should end
        self.flash_panel = None  # Which panel to flash

    def _get_state(self):
        """Get current state from database."""
        try:
            store = EventStore(self.db_path)
            engine = ReplayEngine(store)
            state = engine.replay_to()
            events = store.get_events()
            store.close()
            return state, events
        except Exception as e:
            return None, []

    def _should_flash(self, panel_name: str) -> bool:
        """Check if panel should be flashing."""
        return time.time() < self.flash_until and self.flash_panel == panel_name

    def _make_facts_panel(self, state) -> Panel:
        """Create facts panel."""
        content = Text()

        if state is None or not state.facts:
            content.append("(waiting for facts...)", style="dim")
        else:
            for key, fact in state.facts.items():
                content.append(f"{key}: ", style="cyan bold")
                content.append(f"{fact.value}\n", style="white")
                if fact.previous_value is not None:
                    content.append(f"  └─ was: {fact.previous_value}\n", style="yellow dim")

        border = "bright_yellow" if self._should_flash("facts") else "blue"
        return Panel(content, title="[bold]Facts[/]", border_style=border)

    def _make_constraints_panel(self, state) -> Panel:
        """Create constraints panel."""
        content = Text()

        if state is None:
            content.append("(waiting...)", style="dim")
        else:
            active = [c for c in state.constraints.values() if c.active]
            if not active:
                content.append("(none)", style="dim")
            else:
                for c in active:
                    if c.priority == "learned":
                        content.append("★ ", style="yellow bold")
                        content.append(f"{c.text}\n", style="yellow")
                    elif c.priority == "required":
                        content.append("● ", style="red bold")
                        content.append(f"{c.text}\n", style="white")
                    else:
                        content.append("○ ", style="green")
                        content.append(f"{c.text}\n", style="dim")

        border = "bright_yellow" if self._should_flash("constraints") else "green"
        return Panel(content, title="[bold]Constraints[/]", border_style=border)

    def _make_decisions_panel(self, state) -> Panel:
        """Create decisions panel."""
        content = Text()

        if state is None:
            content.append("(waiting...)", style="dim")
        else:
            if not state.decisions:
                content.append("(none)", style="dim")
            else:
                for d in state.decisions[-6:]:
                    if d.status == "blocked":
                        content.append("✗ ", style="red bold")
                        content.append(f"{d.text}\n", style="red")
                    else:
                        content.append("✓ ", style="green bold")
                        if d.topic:
                            content.append(f"[{d.topic}] ", style="cyan dim")
                        content.append(f"{d.text}\n", style="white")

        border = "bright_yellow" if self._should_flash("decisions") else "magenta"
        return Panel(content, title="[bold]Decisions[/]", border_style=border)

    def _make_events_panel(self, state, events) -> Panel:
        """Create events panel."""
        content = Text()

        if not events:
            content.append("(waiting for events...)", style="dim")
        else:
            for e in events[-10:]:
                seq = e.global_seq
                etype = e.type.value
                short = etype.replace("Added", "+").replace("Made", "").replace("Memory", "")

                # Highlight based on event type
                if "Decision" in etype:
                    status = e.payload.get("status", "")
                    if status == "blocked":
                        content.append(f"{seq:3} ", style="dim")
                        content.append(f"{short} ", style="red")
                        content.append("BLOCKED\n", style="red bold")
                    else:
                        content.append(f"{seq:3} ", style="dim")
                        content.append(f"{short} ", style="green")
                        content.append("OK\n", style="green")
                elif "Constraint" in etype:
                    priority = e.payload.get("priority", "")
                    if priority == "learned":
                        content.append(f"{seq:3} ", style="dim")
                        content.append(f"{short} ", style="yellow")
                        content.append("LEARNED ★\n", style="yellow bold")
                    elif priority == "required":
                        content.append(f"{seq:3} ", style="dim")
                        content.append(f"{short} ", style="red")
                        content.append("REQUIRED ●\n", style="red")
                    else:
                        content.append(f"{seq:3} {short}\n", style="dim")
                elif "Fact" in etype:
                    key = e.payload.get("key", "?")
                    content.append(f"{seq:3} ", style="dim")
                    content.append(f"Fact+ ", style="cyan")
                    content.append(f"{key}\n", style="white")
                elif "Query" in etype:
                    content.append(f"{seq:3} ", style="dim")
                    content.append("Query 🔍\n", style="bright_blue")
                else:
                    content.append(f"{seq:3} {short}\n", style="dim")

        seq_display = state.last_seq if state else 0
        border = "bright_yellow" if self._should_flash("events") else "dim"
        return Panel(content, title=f"[bold]Events[/] [dim]#{seq_display}[/]", border_style=border)

    def _make_header(self, state) -> Panel:
        """Create header panel."""
        seq = state.last_seq if state else 0
        content = Text()
        content.append("Deterministic Memory Layer", style="bold bright_cyan")
        content.append(f"  •  seq: {seq}", style="dim")
        content.append(f"  •  db: {Path(self.db_path).name}", style="dim")

        return Panel(content, border_style="bright_blue", box=ROUNDED)

    def _make_layout(self, state, events) -> Layout:
        """Create the full layout."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="events", size=14),
        )

        layout["main"].split_row(
            Layout(name="facts"),
            Layout(name="constraints"),
            Layout(name="decisions"),
        )

        layout["header"].update(self._make_header(state))
        layout["facts"].update(self._make_facts_panel(state))
        layout["constraints"].update(self._make_constraints_panel(state))
        layout["decisions"].update(self._make_decisions_panel(state))
        layout["events"].update(self._make_events_panel(state, events))

        return layout

    def _trigger_flash(self, panel: str, duration: float = 0.5):
        """Trigger a flash on a panel."""
        self.flash_panel = panel
        self.flash_until = time.time() + duration

    def _detect_changes(self, old_events, new_events):
        """Detect what changed and trigger appropriate flashes."""
        if not new_events:
            return

        old_seqs = {e.global_seq for e in old_events} if old_events else set()

        for e in new_events:
            if e.global_seq not in old_seqs:
                # New event - determine which panel to flash
                etype = e.type.value
                if "Fact" in etype:
                    self._trigger_flash("facts")
                elif "Constraint" in etype:
                    self._trigger_flash("constraints")
                elif "Decision" in etype:
                    self._trigger_flash("decisions")
                self._trigger_flash("events", 0.3)

    def run(self):
        """Run the live monitor."""
        self.console.clear()

        # Show startup message
        startup = Panel(
            Text.from_markup(
                "[bold bright_cyan]DML Monitor[/]\n\n"
                f"[dim]Watching: {self.db_path}[/]\n\n"
                "[white]Waiting for events...[/]\n"
                "[dim]Chat with Claude in another terminal.[/]"
            ),
            border_style="bright_blue",
            box=DOUBLE,
        )
        self.console.print(startup)

        # Wait for database to exist
        while not Path(self.db_path).exists():
            time.sleep(0.5)

        old_events = []

        with Live(self._make_layout(None, []), refresh_per_second=4, console=self.console) as live:
            while True:
                try:
                    state, events = self._get_state()

                    # Detect changes and trigger flashes
                    self._detect_changes(old_events, events)
                    old_events = events

                    # Update display
                    live.update(self._make_layout(state, events))

                    time.sleep(0.25)

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    # Database might be locked, just retry
                    time.sleep(0.5)


def main(db_path: str | None = None):
    """Run the monitor."""
    monitor = DMLMonitor(db_path)
    monitor.run()


if __name__ == "__main__":
    main()
