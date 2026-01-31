"""Rich terminal UI for DML demo visualization."""

from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.style import Style
from rich.box import ROUNDED, DOUBLE


# Color scheme
BLOCKED_STYLE = Style(color="red", bold=True)
ALLOWED_STYLE = Style(color="green", bold=True)
LEARNED_STYLE = Style(color="yellow", bold=True)
DRIFT_STYLE = Style(color="yellow")
FLASHBACK_STYLE = Style(color="yellow", dim=True)
SEPIA_BORDER = Style(color="dark_orange")


@dataclass
class DecisionEntry:
    """Entry for the decision ledger."""
    seq: int
    text: str
    status: str  # "ALLOWED", "BLOCKED"
    constraint: str | None = None


class DMLVisualization:
    """Rich terminal visualization for DML demo."""

    def __init__(self, title: str = "DML: Self-Improving Agent"):
        self.console = Console()
        self.title = title
        self.decisions: list[DecisionEntry] = []

    def _make_facts_panel(self, facts: dict[str, Any], drift_alerts: dict[str, str] | None = None) -> Panel:
        """Create facts panel with optional drift alerts."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        drift_alerts = drift_alerts or {}

        for key, fact in facts.items():
            value = str(fact.get("value", fact)) if isinstance(fact, dict) else str(fact)
            if key in drift_alerts:
                value_text = Text(value)
                value_text.append(f"\n  was {drift_alerts[key]}", style=DRIFT_STYLE)
                table.add_row(key + ":", value_text)
            else:
                table.add_row(key + ":", value)

        return Panel(table, title="FACTS", border_style="blue")

    def _make_constraints_panel(self, constraints: list[dict[str, Any]]) -> Panel:
        """Create constraints panel with learned constraints highlighted."""
        lines = []

        for c in constraints:
            text = c.get("text", str(c))
            priority = c.get("priority", "required")
            active = c.get("active", True)

            if not active:
                continue

            if priority == "learned":
                line = Text(" LEARNED: ", style=LEARNED_STYLE)
                line.append(text)
                if c.get("triggered_by"):
                    line.append(f"\n   [from: seq {c['triggered_by']}]", style="dim")
            else:
                line = Text(" ", style=ALLOWED_STYLE)
                line.append(text)

            lines.append(line)

        content = Text("\n").join(lines) if lines else Text("(none)", style="dim")
        return Panel(content, title="CONSTRAINTS", border_style="green")

    def _make_decisions_panel(self, decisions: list[dict[str, Any]]) -> Panel:
        """Create decisions panel with status indicators."""
        lines = []

        for d in decisions:
            text = d.get("text", str(d))
            status = d.get("status", "committed")
            seq = d.get("seq", "?")

            if status == "blocked" or status == "BLOCKED":
                line = Text(" ", style=BLOCKED_STYLE)
                line.append(f"{text}\n   BLOCKED (seq {seq})", style=BLOCKED_STYLE)
            else:
                line = Text(" ", style=ALLOWED_STYLE)
                line.append(f"{text}\n   (seq {seq})")

            lines.append(line)

        content = Text("\n").join(lines) if lines else Text("(none)", style="dim")
        return Panel(content, title="DECISIONS", border_style="magenta")

    def _make_decision_ledger(self, entries: list[DecisionEntry]) -> Table:
        """Create the decision audit ledger table."""
        table = Table(title="DECISION LEDGER", box=ROUNDED)
        table.add_column("seq", style="cyan", justify="right")
        table.add_column("decision", style="white")
        table.add_column("status", justify="center")
        table.add_column("constraint", style="dim")

        for entry in entries:
            if entry.status == "BLOCKED":
                status_text = Text("", style=BLOCKED_STYLE)
            else:
                status_text = Text("", style=ALLOWED_STYLE)

            table.add_row(
                str(entry.seq),
                entry.text[:40] + "..." if len(entry.text) > 40 else entry.text,
                status_text,
                entry.constraint or "-"
            )

        return table

    def main_view(
        self,
        current_seq: int,
        facts: dict[str, Any],
        constraints: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        drift_alerts: dict[str, str] | None = None,
        decision_ledger: list[DecisionEntry] | None = None,
    ) -> None:
        """Display the main three-column view with decision ledger."""
        self.console.clear()

        # Header
        header = Panel(
            Text(f"{self.title}", justify="center"),
            subtitle=f"seq: {current_seq}",
            border_style="bright_blue",
        )

        # Three columns
        layout = Layout()
        layout.split_column(
            Layout(header, name="header", size=3),
            Layout(name="columns", size=12),
            Layout(name="ledger"),
        )

        layout["columns"].split_row(
            Layout(self._make_facts_panel(facts, drift_alerts)),
            Layout(self._make_constraints_panel(constraints)),
            Layout(self._make_decisions_panel(decisions)),
        )

        # Decision ledger
        entries = decision_ledger or self.decisions
        if entries:
            layout["ledger"].update(self._make_decision_ledger(entries))
        else:
            layout["ledger"].update(Panel("No decisions yet", title="DECISION LEDGER"))

        self.console.print(layout)

    def flashback_mode(
        self,
        viewing_seq: int,
        current_seq: int,
        facts: dict[str, Any],
        constraints: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
    ) -> None:
        """Display flashback mode with sepia styling."""
        self.console.clear()

        # Sepia header
        header = Panel(
            Text(f" FLASHBACK MODE", style=FLASHBACK_STYLE, justify="center"),
            subtitle=f"viewing seq: {viewing_seq} (current: {current_seq})",
            border_style=SEPIA_BORDER,
            box=DOUBLE,
        )

        # Columns with sepia border
        facts_panel = Panel(
            self._make_facts_content(facts),
            title=f"FACTS (seq {viewing_seq})",
            border_style=SEPIA_BORDER,
        )
        constraints_panel = Panel(
            self._make_constraints_content(constraints),
            title=f"CONSTRAINTS (seq {viewing_seq})",
            border_style=SEPIA_BORDER,
        )
        decisions_panel = Panel(
            self._make_decisions_content(decisions),
            title=f"DECISIONS (seq {viewing_seq})",
            border_style=SEPIA_BORDER,
        )

        layout = Layout()
        layout.split_column(
            Layout(header, name="header", size=4),
            Layout(name="columns"),
            Layout(
                Panel(
                    Text(" Press ENTER to return to present", style=FLASHBACK_STYLE, justify="center"),
                    border_style=SEPIA_BORDER,
                ),
                name="footer",
                size=3,
            ),
        )

        layout["columns"].split_row(
            Layout(facts_panel),
            Layout(constraints_panel),
            Layout(decisions_panel),
        )

        self.console.print(layout)

    def _make_facts_content(self, facts: dict[str, Any]) -> Text:
        """Helper to create facts content."""
        if not facts:
            return Text("(none)", style="dim")
        lines = []
        for key, fact in facts.items():
            value = fact.get("value", fact) if isinstance(fact, dict) else fact
            lines.append(f"{key}: {value}")
        return Text("\n".join(lines))

    def _make_constraints_content(self, constraints: list[dict[str, Any]]) -> Text:
        """Helper to create constraints content."""
        if not constraints:
            return Text("(none)", style="dim")
        lines = []
        for c in constraints:
            text = c.get("text", str(c))
            if c.get("active", True):
                lines.append(f" {text}")
        return Text("\n".join(lines)) if lines else Text("(none)", style="dim")

    def _make_decisions_content(self, decisions: list[dict[str, Any]]) -> Text:
        """Helper to create decisions content."""
        if not decisions:
            return Text("(none)", style="dim")
        lines = []
        for d in decisions:
            text = d.get("text", str(d))
            status = d.get("status", "committed")
            icon = "" if status in ("blocked", "BLOCKED") else ""
            lines.append(f"{icon} {text}")
        return Text("\n".join(lines))

    def timeline_split(
        self,
        timeline_a: dict[str, Any],
        timeline_b: dict[str, Any],
        injected_constraint: str,
        injected_at_seq: int,
    ) -> None:
        """Display side-by-side timeline comparison (Fork the Future)."""
        self.console.clear()

        # Header
        header = Panel(
            Text("FORK THE FUTURE: Timeline Comparison", style="bold bright_white", justify="center"),
            border_style="bright_magenta",
            box=DOUBLE,
        )

        # Timeline A
        a_content = Text()
        a_content.append(f"Constraint added: seq {timeline_a.get('constraint_seq', '?')}\n", style="dim")
        a_content.append("(added AFTER hotel decision)\n\n", style="dim")

        for d in timeline_a.get("decisions", []):
            seq = d.get("seq", "?")
            text = d.get("text", "?")
            status = d.get("status", "?")
            if status in ("blocked", "BLOCKED"):
                a_content.append(f"seq {seq}: {text}\n", style=BLOCKED_STYLE)
                a_content.append("         BLOCKED\n", style=BLOCKED_STYLE)
            else:
                a_content.append(f"seq {seq}: {text}\n", style=ALLOWED_STYLE)
                a_content.append("         ALLOWED\n", style=ALLOWED_STYLE)

        a_panel = Panel(a_content, title="TIMELINE A (actual)", border_style="blue")

        # Timeline B
        b_content = Text()
        b_content.append(f"Constraint added: seq {injected_at_seq}\n", style="dim")
        b_content.append("(added BEFORE hotel decision)\n\n", style="dim")

        for d in timeline_b.get("decisions", []):
            seq = d.get("seq", "?")
            text = d.get("text", "?")
            status = d.get("status", "?")
            if status in ("blocked", "BLOCKED"):
                b_content.append(f"seq {seq}: {text}\n", style=BLOCKED_STYLE)
                b_content.append("         BLOCKED\n", style=BLOCKED_STYLE)
            else:
                b_content.append(f"seq {seq}: {text}\n", style=ALLOWED_STYLE)
                b_content.append("         ALLOWED\n", style=ALLOWED_STYLE)

        b_panel = Panel(b_content, title="TIMELINE B (what-if)", border_style="magenta")

        # Summary
        summary_a = timeline_a.get("summary", "Pain discovered LATE")
        summary_b = timeline_b.get("summary", "Pain PREVENTED")

        summary = Panel(
            Text(
                f'"Same inputs. Earlier constraint. Different reality."\n\n'
                f'Timeline A: {summary_a}\n'
                f'Timeline B: {summary_b}',
                justify="center",
            ),
            border_style="bright_yellow",
        )

        layout = Layout()
        layout.split_column(
            Layout(header, name="header", size=3),
            Layout(name="timelines"),
            Layout(summary, name="summary", size=6),
        )

        layout["timelines"].split_row(
            Layout(a_panel),
            Layout(b_panel),
        )

        self.console.print(layout)

    def show_blocked(
        self,
        decision: str,
        constraint: str,
        constraint_seq: int,
        reason: str,
    ) -> None:
        """Display a blocked decision alert."""
        content = Text()
        content.append("Decision: ", style="bold")
        content.append(f'"{decision}"\n\n')
        content.append("Violated: ", style="bold")
        content.append(f'"{constraint}" (seq {constraint_seq})\n\n')
        content.append("Reason: ", style="bold")
        content.append(reason)

        panel = Panel(
            content,
            title=" DECISION BLOCKED",
            title_align="left",
            border_style=BLOCKED_STYLE,
            box=DOUBLE,
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

    def show_learned(
        self,
        constraint: str,
        triggered_by: int,
    ) -> None:
        """Display a learned constraint notification."""
        content = Text()
        content.append(f'"{constraint}"\n\n', style="bold")
        content.append("Triggered by: ", style="dim")
        content.append(f"conflict at seq {triggered_by}\n")
        content.append("Type: ", style="dim")
        content.append("learned (self-improvement)")

        panel = Panel(
            content,
            title=" CONSTRAINT LEARNED",
            title_align="left",
            border_style=LEARNED_STYLE,
            box=DOUBLE,
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

    def show_drift_alert(
        self,
        key: str,
        old_value: Any,
        new_value: Any,
        affected_decisions: list[str] | None = None,
    ) -> None:
        """Display a drift alert."""
        content = Text()
        content.append(f"{key}: ", style="bold")
        content.append(f"{old_value}", style="dim strike")
        content.append(f"  {new_value}\n\n", style="bold")

        if affected_decisions:
            content.append("Decisions made before this change:\n", style="dim")
            for d in affected_decisions:
                content.append(f"  - {d}\n")

        panel = Panel(
            content,
            title=" DRIFT ALERT",
            title_align="left",
            border_style=DRIFT_STYLE,
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

    def add_decision(self, seq: int, text: str, status: str, constraint: str | None = None) -> None:
        """Add a decision to the ledger."""
        self.decisions.append(DecisionEntry(
            seq=seq,
            text=text,
            status=status,
            constraint=constraint,
        ))


def demo():
    """Quick demo of visualization components."""
    viz = DMLVisualization("DML: Self-Improving Travel Agent")

    # Sample data
    facts = {
        "destination": {"value": "Japan"},
        "duration": {"value": "10 days"},
        "budget": {"value": "$3000"},
    }

    constraints = [
        {"text": "traditional ryokan accommodations", "priority": "preferred", "active": True},
        {"text": "wheelchair accessible rooms required", "priority": "required", "active": True},
        {"text": "verify accessibility BEFORE recommending", "priority": "learned", "active": True, "triggered_by": 47},
    ]

    decisions = [
        {"text": "Book Ryokan Kurashiki", "status": "blocked", "seq": 47},
        {"text": "Hotel Granvia (unverified)", "status": "blocked", "seq": 50},
        {"text": "Hotel Granvia (verified)", "status": "committed", "seq": 52},
    ]

    # Decision ledger
    ledger = [
        DecisionEntry(23, "Ryokan Kurashiki", "ALLOWED", None),
        DecisionEntry(47, "Keep Ryokan", "BLOCKED", "wheelchair"),
        DecisionEntry(50, "Hotel Granvia", "BLOCKED", "learned:verify"),
        DecisionEntry(52, "Hotel Granvia (verified)", "ALLOWED", None),
    ]

    # Show main view
    viz.main_view(
        current_seq=52,
        facts=facts,
        constraints=constraints,
        decisions=decisions,
        drift_alerts={"budget": "$4000"},
        decision_ledger=ledger,
    )

    input("\nPress Enter for flashback mode...")

    # Show flashback
    viz.flashback_mode(
        viewing_seq=5,
        current_seq=52,
        facts={"destination": {"value": "Japan"}, "budget": {"value": "$4000"}},
        constraints=[],
        decisions=[],
    )

    input()  # Wait for enter

    # Show timeline split
    viz.timeline_split(
        timeline_a={
            "constraint_seq": 45,
            "decisions": [
                {"seq": 23, "text": "Ryokan Kurashiki", "status": "ALLOWED"},
                {"seq": 47, "text": "Keep Ryokan", "status": "BLOCKED"},
            ],
            "summary": "Pain discovered LATE - user had to complain",
        },
        timeline_b={
            "decisions": [
                {"seq": 23, "text": "Ryokan Kurashiki", "status": "BLOCKED"},
            ],
            "summary": "Pain PREVENTED - constraint caught it early",
        },
        injected_constraint="wheelchair accessible",
        injected_at_seq=6,
    )


if __name__ == "__main__":
    demo()
