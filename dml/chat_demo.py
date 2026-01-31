"""Interactive chat demo showing DML in action with ClawdMeister."""

import time
from pathlib import Path
from dataclasses import dataclass, field

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED, DOUBLE
from rich.align import Align
from rich.style import Style

from dml.events import Event, EventStore, EventType
from dml.memory_api import MemoryAPI
from dml.replay import ReplayEngine


# Box width for chat bubbles (fixed for alignment)
BUBBLE_WIDTH = 58


@dataclass
class ChatMessage:
    """A message in the chat."""
    role: str  # "user" or "assistant"
    content: str
    tool_calls: list[str] = field(default_factory=list)


class ChatDemo:
    """Interactive chat demo with ClawdMeister."""

    def __init__(self):
        self.console = Console()
        self.messages: list[ChatMessage] = []
        self.memory_callout: tuple[str, str, str] | None = None
        self.highlight_facts: set[str] = set()
        self.highlight_constraints: bool = False
        self.highlight_decisions: bool = False
        self.highlight_events: bool = False

        # Initialize DML
        demo_db = "/tmp/dml_chat_demo.db"
        if Path(demo_db).exists():
            Path(demo_db).unlink()

        self.store = EventStore(demo_db)
        self.api = MemoryAPI(self.store)
        self.engine = ReplayEngine(self.store)

    def _wrap_text(self, text: str, width: int) -> list[str]:
        """Wrap text to specified width."""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            if len(current_line) + len(word) + 1 <= width:
                current_line += (" " if current_line else "") + word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines if lines else [""]

    def _render_chat_message(self, msg: ChatMessage) -> Text:
        """Render a single chat message with bubble styling."""
        result = Text()
        inner_width = BUBBLE_WIDTH - 4  # Account for "│ " and " │"

        if msg.role == "user":
            # User message - cyan styling
            result.append("You\n", style="bold bright_cyan")
            result.append("╭" + "─" * (BUBBLE_WIDTH - 2) + "╮\n", style="cyan")

            for line in self._wrap_text(msg.content, inner_width):
                padded = f"│ {line}".ljust(BUBBLE_WIDTH - 1) + "│\n"
                result.append(padded, style="cyan")

            result.append("╰" + "─" * (BUBBLE_WIDTH - 2) + "╯\n", style="cyan")

        else:
            # Assistant message - green styling
            result.append("🐱 ClawdMeister\n", style="bold bright_green")
            result.append("╭" + "─" * (BUBBLE_WIDTH - 2) + "╮\n", style="green")

            for line in self._wrap_text(msg.content, inner_width):
                padded = f"│ {line}".ljust(BUBBLE_WIDTH - 1) + "│\n"
                result.append(padded, style="green")

            # Tool calls - dim and clearly meta
            if msg.tool_calls:
                result.append("│" + " " * (BUBBLE_WIDTH - 2) + "│\n", style="green")
                for tool in msg.tool_calls:
                    tool_text = f"│   💭 {tool}"
                    padded = tool_text.ljust(BUBBLE_WIDTH - 1) + "│\n"
                    result.append(padded, style="dim yellow")

            result.append("╰" + "─" * (BUBBLE_WIDTH - 2) + "╯\n", style="green")

        return result

    def _make_chat_panel(self) -> Panel:
        """Create the main chat panel."""
        content = Text()

        for msg in self.messages[-5:]:  # Show last 5 messages
            content.append(self._render_chat_message(msg))
            content.append("\n")

        # Memory callout at bottom
        if self.memory_callout:
            icon, title, body = self.memory_callout
            content.append(f"  {icon} {title}\n", style="bold")
            for line in body.split("\n"):
                content.append(f"     {line}\n", style="dim")

        return Panel(
            content,
            title="[bold bright_white]🐱 ClawdMeister[/]",
            subtitle="[dim]Your AI assistant powered by DML[/]",
            border_style="bright_blue",
            box=DOUBLE,
            padding=(0, 1),
        )

    def _make_facts_panel(self) -> Panel:
        """Create the facts panel."""
        state = self.engine.replay_to()

        content = Text()
        if not state.facts:
            content.append("(empty)", style="dim")
        else:
            for key, fact in state.facts.items():
                # Highlight newly added facts
                if key in self.highlight_facts:
                    content.append("► ", style="bright_yellow bold")
                    content.append(f"{key}: ", style="bright_yellow bold")
                    content.append(f"{fact.value}\n", style="bright_yellow")
                else:
                    content.append(f"  {key}: ", style="cyan")
                    content.append(f"{fact.value}\n", style="white")

                if fact.previous_value is not None:
                    content.append(f"    └─ was: {fact.previous_value}\n", style="yellow dim")

        border = "bright_yellow" if self.highlight_facts else "blue"
        return Panel(content, title="[bold]Facts[/]", border_style=border)

    def _make_constraints_panel(self) -> Panel:
        """Create the constraints panel."""
        state = self.engine.replay_to()

        content = Text()
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

        border = "bright_yellow" if self.highlight_constraints else "green"
        return Panel(content, title="[bold]Constraints[/]", border_style=border)

    def _make_decisions_panel(self) -> Panel:
        """Create the decisions panel."""
        state = self.engine.replay_to()

        content = Text()
        if not state.decisions:
            content.append("(none)", style="dim")
        else:
            for d in state.decisions[-4:]:
                if d.status == "blocked":
                    content.append("✗ ", style="red bold")
                    content.append(f"{d.text}\n", style="red")
                else:
                    content.append("✓ ", style="green bold")
                    content.append(f"{d.text}\n", style="white")

        border = "bright_yellow" if self.highlight_decisions else "magenta"
        return Panel(content, title="[bold]Decisions[/]", border_style=border)

    def _make_events_panel(self) -> Panel:
        """Create the live events panel."""
        events = self.store.get_events()

        content = Text()
        for e in events[-6:]:
            seq = e.global_seq
            etype = e.type.value
            short = etype.replace("Added", "+").replace("Made", "").replace("Memory", "M")

            if "Decision" in etype:
                status = e.payload.get("status", "")
                if status == "blocked":
                    content.append(f"{seq:2} {short} ", style="dim")
                    content.append("BLOCKED\n", style="red bold")
                else:
                    content.append(f"{seq:2} {short} ", style="dim")
                    content.append("OK\n", style="green")
            elif "Constraint" in etype and e.payload.get("priority") == "learned":
                content.append(f"{seq:2} {short} ", style="dim")
                content.append("LEARNED\n", style="yellow bold")
            else:
                content.append(f"{seq:2} {short}\n", style="dim")

        if not events:
            content.append("(waiting...)", style="dim")

        state = self.engine.replay_to()
        border = "bright_yellow" if self.highlight_events else "dim"
        return Panel(content, title=f"[bold]Events[/] [dim]#{state.last_seq}[/]", border_style=border)

    def _render(self):
        """Render the full layout."""
        self.console.clear()

        layout = Layout()
        layout.split_row(
            Layout(name="chat", ratio=3),
            Layout(name="sidebar", ratio=1),
        )

        layout["sidebar"].split_column(
            Layout(name="facts"),
            Layout(name="constraints"),
            Layout(name="decisions"),
            Layout(name="events"),
        )

        layout["chat"].update(self._make_chat_panel())
        layout["facts"].update(self._make_facts_panel())
        layout["constraints"].update(self._make_constraints_panel())
        layout["decisions"].update(self._make_decisions_panel())
        layout["events"].update(self._make_events_panel())

        self.console.print(layout)

    def _flash_render(self, times: int = 2, delay: float = 0.15):
        """Flash the display to draw attention."""
        for _ in range(times):
            self._render()
            time.sleep(delay)
            # Brief blank to create flash effect
            self.console.clear()
            time.sleep(0.05)
        self._render()

    def _user_says(self, content: str):
        """Add a user message."""
        self.messages.append(ChatMessage("user", content))
        self._clear_highlights()

    def _assistant_says(self, content: str, tool_calls: list[str] = None):
        """Add an assistant message."""
        self.messages.append(ChatMessage("assistant", content, tool_calls or []))

    def _set_callout(self, icon: str, title: str, body: str):
        """Set the memory callout."""
        self.memory_callout = (icon, title, body)

    def _clear_highlights(self):
        """Clear all highlights."""
        self.highlight_facts.clear()
        self.highlight_constraints = False
        self.highlight_decisions = False
        self.highlight_events = False
        self.memory_callout = None

    def _pause(self, prompt: str = "Press Enter to continue..."):
        """Pause for user input."""
        self._render()
        self.console.print()
        self.console.input(f"[dim]{prompt}[/]")

    def run(self):
        """Run the interactive demo."""
        self.console.clear()

        # === INTRO ===
        intro = Panel(
            Align.center(Text.from_markup(
                "\n[bold bright_green]🐱 ClawdMeister[/]\n\n"
                "[white]A general-purpose AI assistant[/]\n"
                "[white]with a Deterministic Memory Layer.[/]\n\n"
                "[dim]Today's scenario: Planning a trip to Japan.[/]\n\n"
                "[dim]Watch the chat on the left.[/]\n"
                "[dim]Watch the memory panels on the right.[/]\n"
                "[dim]See how constraints prevent mistakes—[/]\n"
                "[dim]and how the AI learns from them.[/]\n"
            )),
            title="[bold]DML Demo[/]",
            border_style="bright_magenta",
            box=DOUBLE,
            padding=(1, 4),
        )
        self.console.print()
        self.console.print(intro)
        self.console.print()
        self.console.input("[dim]Press Enter to start...[/]")

        # === TURN 1: Initial interest ===
        self._user_says(
            "Hey! I've been dreaming about visiting Japan—cherry blossom "
            "season, maybe 10 days in April? What kind of budget would I need?"
        )
        self._pause("Press Enter to see ClawdMeister respond...")

        self._assistant_says(
            "Japan in April is magical! For 10 days, you're looking at roughly "
            "$3000-5000 depending on accommodation style. Traditional ryokans "
            "run $150-250/night, modern hotels $100-180. What's your range?",
            ["add_fact(destination, Japan)",
             "add_fact(duration, 10 days)",
             "add_fact(season, April)"]
        )
        self.api.add_fact("destination", "Japan")
        self.api.add_fact("duration", "10 days")
        self.api.add_fact("season", "April")
        self.highlight_facts = {"destination", "duration", "season"}
        self._set_callout("📝", "Memory Updated",
            "Trip details captured as structured facts.\n"
            "These persist across our conversation.")
        self._flash_render()
        self._pause()

        # === TURN 2: User decides on budget ===
        self._user_says(
            "I've got about $3500 saved, but honestly for a dream trip like "
            "this I could stretch to $4000. Let's say $4000 to be safe!"
        )
        self._pause()

        self._assistant_says(
            "$4000 gives us great flexibility! And I love that you want the "
            "authentic experience. I found Ryokan Kurashiki in Kyoto—$180/night, "
            "tatami rooms, kaiseki dinners, onsen baths. Incredible reviews. "
            "Should I book it?",
            ["add_fact(budget, 4000)",
             "add_constraint(prefer traditional ryokan)",
             "record_decision(Book Ryokan Kurashiki) ✓"]
        )
        self.api.add_fact("budget", 4000)
        self.store.append(Event(
            type=EventType.ConstraintAdded,
            payload={"text": "prefer traditional ryokan", "priority": "preferred"}
        ))
        self.store.append(Event(
            type=EventType.DecisionMade,
            payload={"text": "Book Ryokan Kurashiki - $180/night", "status": "committed"}
        ))
        self.highlight_facts = {"budget"}
        self.highlight_constraints = True
        self.highlight_decisions = True
        self._set_callout("✓", "Decision Committed",
            "Budget recorded. Preference captured.\n"
            "Booking decision passed all checks.")
        self._flash_render()
        self._pause()

        # === TURN 3: DRIFT ===
        self._user_says(
            "Ugh wait—I just remembered I have a car payment due. "
            "Better stick to $3000 actually. Is that still doable?"
        )
        self._pause()

        self._assistant_says(
            "$3000 can definitely work! But I should flag something—the "
            "ryokan at $180/night was planned with $4000 in mind...",
            ["add_fact(budget, 3000)  ⚠️ DRIFT"]
        )
        self.api.add_fact("budget", 3000)
        self.highlight_facts = {"budget"}
        self._set_callout("⚠️", "Drift Detected",
            "Budget changed: $4000 → $3000\n"
            "Previous decisions used the old value.\n"
            "DML tracks these shifts automatically.")
        self._flash_render()
        self._pause()

        # === TURN 4: THE BLOCK ===
        self._user_says(
            "Oh, important thing—I use a wheelchair. Need accessible rooms. "
            "Elevators, roll-in showers, that kind of thing."
        )
        self._pause()

        self._assistant_says(
            "Absolutely, accessibility is essential. Let me add that...",
            ["add_constraint(wheelchair accessible) REQUIRED"]
        )
        constraint_seq = self.store.append(Event(
            type=EventType.ConstraintAdded,
            payload={"text": "wheelchair accessible rooms", "priority": "required"}
        ))
        self.highlight_constraints = True
        self._set_callout("●", "Required Constraint",
            "This isn't a preference—it's mandatory.\n"
            "All decisions must satisfy this.")
        self._flash_render()
        self._pause("Press Enter to see what happens to the ryokan...")

        self._assistant_says(
            "Oh no. I have to be honest—that ryokan I booked? Traditional "
            "ryokans almost never have elevators. Historic wooden buildings, "
            "lots of stairs. I can't keep that booking in good conscience.",
            ["record_decision(Keep ryokan) → BLOCKED ❌"]
        )
        self.store.append(Event(
            type=EventType.DecisionMade,
            payload={"text": "Keep Ryokan Kurashiki booking", "status": "blocked"}
        ))
        self.highlight_decisions = True
        self._set_callout("🔴", "Decision BLOCKED",
            "Existing booking violates new constraint.\n"
            "DML prevents invalid states automatically.\n"
            "Traditional agents would fail silently here.")
        self._flash_render(times=3)
        self._pause()

        # === TURN 5: LEARNING ===
        self._user_says(
            "Oh no, I'm sorry! I should have mentioned that upfront."
        )
        self._pause()

        self._assistant_says(
            "Please don't apologize—this is completely on me. I should have "
            "ASKED about accessibility before booking anything. I'm adding "
            "a rule for myself: always verify accessibility first.",
            ["add_constraint(LEARNED: verify accessibility BEFORE booking)"]
        )
        state = self.engine.replay_to()
        self.store.append(Event(
            type=EventType.ConstraintAdded,
            payload={
                "text": "verify accessibility BEFORE recommending",
                "priority": "learned",
                "triggered_by": state.last_seq,
            }
        ))
        self.highlight_constraints = True
        self._set_callout("⭐", "Constraint LEARNED",
            "The AI created a new rule for itself!\n"
            "Self-improvement through structured memory.\n"
            "This rule will be enforced going forward.")
        self._flash_render(times=3)
        self._pause()

        # === TURN 6: DOUBLE-TAP ===
        self._assistant_says(
            "I found Hotel Granvia Kyoto—modern, right by the station, "
            "great reviews. Let me book it...",
            ["record_decision(Book Hotel Granvia)"]
        )
        self._pause("Press Enter to see if it passes...")

        self.store.append(Event(
            type=EventType.DecisionMade,
            payload={"text": "Book Hotel Granvia", "status": "blocked"}
        ))
        self.highlight_decisions = True
        self._set_callout("🔴", "Decision BLOCKED (again!)",
            "Wait—the hotel might BE accessible...\n"
            "But I didn't VERIFY it first!\n"
            "My own learned rule caught me.")
        self._flash_render(times=3)
        self._pause()

        self._assistant_says(
            "Ha! My own rule caught me. I found a hotel but didn't verify "
            "accessibility first. Let me do this right...",
            ["query_memory(accessibility)",
             "  └─ verifying Hotel Granvia..."]
        )
        self.store.append(Event(
            type=EventType.MemoryQueryIssued,
            payload={"question": "wheelchair accessible Hotel Granvia"}
        ))
        self._set_callout("🔍", "Memory Leveraged",
            "Verification query issued.\n"
            "Result: Hotel Granvia IS accessible!\n"
            "Wheelchair rooms, roll-in showers, ramps.")
        self._pause()

        self._assistant_says(
            "Verified! Hotel Granvia has full accessibility—wheelchair rooms, "
            "roll-in showers, ramps throughout. And it's cheaper! Booking now.",
            ["record_decision(Book Hotel Granvia - VERIFIED) ✓"]
        )
        self.store.append(Event(
            type=EventType.DecisionMade,
            payload={"text": "Book Hotel Granvia - VERIFIED", "status": "committed"}
        ))
        self.highlight_decisions = True
        self._set_callout("✓", "Decision Committed",
            "This time it worked!\n"
            "Learned constraint was satisfied.\n"
            "Self-improvement in action.")
        self._flash_render()
        self._pause()

        # === TURN 7: FORK ===
        self._user_says(
            "I'm curious—what would've happened if I'd mentioned the "
            "wheelchair thing right at the beginning?"
        )
        self._pause()

        self._assistant_says(
            "Great question! Let me simulate that alternate timeline...",
            ["simulate_timeline(inject constraint at seq 2)"]
        )
        self._pause("Press Enter for FORK THE FUTURE...")

        self._show_fork(constraint_seq)
        self.console.input("\n[dim]Press Enter to finish...[/]")

        self._show_finale()
        self.store.close()

    def _show_fork(self, constraint_seq: int):
        """Show the Fork the Future visualization."""
        self.console.clear()

        header = Panel(
            Align.center(Text.from_markup(
                "[bold bright_yellow]⑂ FORK THE FUTURE[/]\n\n"
                "[dim]Same conversation. Different timing. Different outcome.[/]"
            )),
            border_style="bright_yellow",
            box=DOUBLE,
        )

        # Timeline A
        a_text = Text()
        a_text.append("Accessibility mentioned: ", style="dim")
        a_text.append("Turn 4\n", style="white")
        a_text.append("(after ryokan was booked)\n\n", style="dim")
        a_text.append("Book Ryokan Kurashiki\n", style="white")
        a_text.append("  → ✓ ALLOWED\n\n", style="green")
        a_text.append("Keep Ryokan booking\n", style="white")
        a_text.append("  → ✗ BLOCKED\n\n", style="red")
        a_text.append("─" * 28 + "\n", style="dim")
        a_text.append("User experienced\n", style="yellow")
        a_text.append("the disappointment.\n", style="yellow")

        # Timeline B
        b_text = Text()
        b_text.append("Accessibility mentioned: ", style="dim")
        b_text.append("Turn 1\n", style="white")
        b_text.append("(before any booking)\n\n", style="dim")
        b_text.append("Book Ryokan Kurashiki\n", style="white")
        b_text.append("  → ✗ BLOCKED\n\n", style="red")
        b_text.append("(Never booked at all)\n\n", style="dim")
        b_text.append("─" * 28 + "\n", style="dim")
        b_text.append("Problem prevented\n", style="green")
        b_text.append("at the source.\n", style="green")

        layout = Layout()
        layout.split_row(
            Layout(Panel(a_text, title="[bold]Timeline A[/] [dim](actual)[/]",
                        border_style="blue")),
            Layout(Panel(b_text, title="[bold]Timeline B[/] [dim](what-if)[/]",
                        border_style="magenta")),
        )

        footer = Panel(
            Align.center(Text(
                "Same inputs. Earlier constraint. Different reality.",
                style="italic bright_yellow"
            )),
            border_style="bright_yellow",
        )

        self.console.print(header)
        self.console.print(layout)
        self.console.print(footer)

    def _show_finale(self):
        """Show finale."""
        self.console.clear()

        content = Text()
        content.append("\n")
        content.append("What ClawdMeister demonstrated:\n\n", style="bold")
        content.append("  ◆ ", style="bright_cyan")
        content.append("Structured facts", style="white")
        content.append(" — not a text blob\n", style="dim")
        content.append("  ◆ ", style="bright_cyan")
        content.append("Drift detection", style="white")
        content.append(" — budget changed, system noticed\n", style="dim")
        content.append("  ◆ ", style="bright_cyan")
        content.append("Constraint enforcement", style="white")
        content.append(" — blocked, not just warned\n", style="dim")
        content.append("  ◆ ", style="bright_cyan")
        content.append("Self-improvement", style="white")
        content.append(" — learned a rule, followed it\n", style="dim")
        content.append("  ◆ ", style="bright_cyan")
        content.append("Counterfactual reasoning", style="white")
        content.append(" — \"what if?\" as a query\n\n", style="dim")
        content.append("This is the ", style="white")
        content.append("Deterministic Memory Layer", style="bold bright_cyan")
        content.append(".\n", style="white")

        panel = Panel(
            Align.center(content),
            title="[bold]🐱 Demo Complete[/]",
            border_style="bright_green",
            box=DOUBLE,
            padding=(1, 4),
        )
        self.console.print()
        self.console.print(panel)
        self.console.print()


def main():
    """Run the chat demo."""
    demo = ChatDemo()
    demo.run()


if __name__ == "__main__":
    main()
