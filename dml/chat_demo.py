"""Interactive chat demo showing DML in action."""

import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED, DOUBLE, SIMPLE
from rich.align import Align
from rich.live import Live
from rich.style import Style

from dml.events import Event, EventStore, EventType
from dml.memory_api import MemoryAPI
from dml.replay import ReplayEngine


# Styles
USER_STYLE = Style(color="bright_cyan", bold=True)
AGENT_STYLE = Style(color="bright_green", bold=True)
TOOL_STYLE = Style(color="yellow", dim=True)
ADDED_STYLE = Style(color="green")
BLOCKED_STYLE = Style(color="red", bold=True)
LEARNED_STYLE = Style(color="yellow", bold=True)
DRIFT_STYLE = Style(color="yellow")


@dataclass
class ChatMessage:
    """A message in the chat."""
    role: str  # "user", "agent", "tool", "system"
    content: str
    tool_calls: list[str] = field(default_factory=list)


@dataclass
class MemoryChange:
    """A change to memory to highlight."""
    change_type: str  # "added", "updated", "blocked", "learned", "leveraged"
    description: str


class ChatDemo:
    """Interactive chat demo with live memory visualization."""

    def __init__(self):
        self.console = Console()
        self.messages: list[ChatMessage] = []
        self.memory_changes: list[MemoryChange] = []
        self.events_log: list[str] = []

        # Initialize DML
        demo_db = "/tmp/dml_chat_demo.db"
        if Path(demo_db).exists():
            Path(demo_db).unlink()

        self.store = EventStore(demo_db)
        self.api = MemoryAPI(self.store)
        self.engine = ReplayEngine(self.store)

    def _make_chat_panel(self) -> Panel:
        """Create the main chat panel."""
        content = Text()

        for msg in self.messages[-12:]:  # Show last 12 messages
            if msg.role == "user":
                content.append("\n You: ", style=USER_STYLE)
                content.append(msg.content + "\n")
            elif msg.role == "agent":
                content.append("\n 🐱 Clawde: ", style=AGENT_STYLE)
                content.append(msg.content + "\n")
                for tool in msg.tool_calls:
                    content.append(f"    💭 {tool}\n", style=TOOL_STYLE)
            elif msg.role == "system":
                content.append(f"\n{msg.content}\n", style="dim italic")

        # Add memory change callout if present
        if self.memory_changes:
            change = self.memory_changes[-1]
            content.append("\n")

            if change.change_type == "added":
                box_style = "green"
                icon = "📝"
                title = "Memory Updated"
            elif change.change_type == "blocked":
                box_style = "red"
                icon = "🔴"
                title = "Decision BLOCKED"
            elif change.change_type == "learned":
                box_style = "yellow"
                icon = "⭐"
                title = "Constraint LEARNED"
            elif change.change_type == "leveraged":
                box_style = "cyan"
                icon = "🔍"
                title = "Memory Leveraged"
            elif change.change_type == "drift":
                box_style = "yellow"
                icon = "⚠️"
                title = "Drift Detected"
            else:
                box_style = "white"
                icon = "📋"
                title = "Memory"

            change_text = Text()
            change_text.append(f" {icon} {title}\n", style=f"bold {box_style}")
            for line in change.description.split("\n"):
                change_text.append(f"    {line}\n", style=box_style)
            content.append("\n")
            content.append(change_text)

        return Panel(
            content,
            title="[bold bright_white]🐱 Clawde[/] [dim]- Travel Assistant[/]",
            border_style="bright_blue",
            padding=(0, 1),
        )

    def _make_facts_panel(self) -> Panel:
        """Create the facts panel."""
        state = self.engine.replay_to()

        content = Text()
        if not state.facts:
            content.append("(none yet)", style="dim")
        else:
            for key, fact in state.facts.items():
                content.append(f"{key}: ", style="cyan")
                content.append(f"{fact.value}\n", style="white")
                if fact.previous_value is not None:
                    content.append(f"  ↳ was {fact.previous_value}\n", style=DRIFT_STYLE)

        return Panel(content, title="[bold]Facts[/]", border_style="blue", padding=(0, 1))

    def _make_constraints_panel(self) -> Panel:
        """Create the constraints panel."""
        state = self.engine.replay_to()

        content = Text()
        active = [c for c in state.constraints.values() if c.active]

        if not active:
            content.append("(none yet)", style="dim")
        else:
            for c in active:
                if c.priority == "learned":
                    content.append("★ ", style=LEARNED_STYLE)
                    content.append(f"{c.text}\n", style="white")
                    if c.triggered_by:
                        content.append(f"  ↳ from seq {c.triggered_by}\n", style="dim")
                else:
                    content.append("✓ ", style=ADDED_STYLE)
                    content.append(f"{c.text}\n", style="white")

        return Panel(content, title="[bold]Constraints[/]", border_style="green", padding=(0, 1))

    def _make_decisions_panel(self) -> Panel:
        """Create the decisions panel."""
        state = self.engine.replay_to()

        content = Text()
        if not state.decisions:
            content.append("(none yet)", style="dim")
        else:
            for d in state.decisions[-5:]:  # Last 5 decisions
                if d.status == "blocked":
                    content.append("✗ ", style=BLOCKED_STYLE)
                    content.append(f"{d.text}\n", style="red")
                else:
                    content.append("✓ ", style=ADDED_STYLE)
                    content.append(f"{d.text}\n", style="white")

        return Panel(content, title="[bold]Decisions[/]", border_style="magenta", padding=(0, 1))

    def _make_events_panel(self) -> Panel:
        """Create the events log panel."""
        state = self.engine.replay_to()
        events = self.store.get_events()

        content = Text()
        if not events:
            content.append("(none yet)", style="dim")
        else:
            for e in events[-8:]:  # Last 8 events
                seq = e.global_seq
                etype = e.type.value.replace("MemoryWrite", "MW").replace("Added", "+").replace("Made", "")

                if "Decision" in e.type.value:
                    status = e.payload.get("status", "")
                    if status == "blocked":
                        content.append(f"{seq}: ", style="dim")
                        content.append(f"{etype} 🔴\n", style="red")
                    else:
                        content.append(f"{seq}: ", style="dim")
                        content.append(f"{etype} ✓\n", style="green")
                elif "Constraint" in e.type.value and e.payload.get("priority") == "learned":
                    content.append(f"{seq}: ", style="dim")
                    content.append(f"{etype} ★\n", style="yellow")
                else:
                    content.append(f"{seq}: {etype}\n", style="dim")

        return Panel(content, title=f"[bold]Events[/] [dim]seq:{state.last_seq}[/]", border_style="dim", padding=(0, 1))

    def _make_layout(self) -> Layout:
        """Create the full layout."""
        layout = Layout()

        layout.split_row(
            Layout(name="chat", ratio=3),
            Layout(name="memory", ratio=2),
        )

        layout["memory"].split_column(
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

        return layout

    def _type_message(self, role: str, content: str, tool_calls: list[str] = None, delay: float = 0.03):
        """Add a message with typing effect."""
        self.messages.append(ChatMessage(role, content, tool_calls or []))

    def _add_memory_change(self, change_type: str, description: str):
        """Add a memory change callout."""
        self.memory_changes.append(MemoryChange(change_type, description))

    def _clear_memory_change(self):
        """Clear the memory change callout."""
        self.memory_changes.clear()

    def _pause(self, prompt: str = "Press Enter to continue..."):
        """Pause for user input."""
        self.console.print(self._make_layout())
        self.console.print()
        self.console.input(f"[dim]{prompt}[/]")
        self._clear_memory_change()

    def run(self):
        """Run the interactive demo."""
        self.console.clear()

        # === INTRO ===
        intro = Panel(
            Align.center(Text.from_markup(
                "\n[bold bright_cyan]Meet Clawde[/] 🐱\n\n"
                "[white]A travel assistant with perfect memory.[/]\n\n"
                "[dim]Watch the chat on the left.\n"
                "Watch the memory evolve on the right.\n"
                "See how constraints prevent mistakes—\n"
                "and how the agent learns from them.[/]\n"
            )),
            title="[bold]Deterministic Memory Layer Demo[/]",
            border_style="bright_magenta",
            box=DOUBLE,
            padding=(1, 4),
        )
        self.console.print()
        self.console.print(intro)
        self.console.print()
        self.console.input("[dim]Press Enter to start the conversation...[/]")

        # === TURN 1: Initial request ===
        self.console.clear()
        self._type_message("user",
            "Hey! I've been dreaming about visiting Japan. I've saved up about "
            "$4000 and I'm thinking maybe 10 days in April? Cherry blossom "
            "season, you know? What do you think?")
        self._pause("Press Enter to see Clawde respond...")

        self._type_message("agent",
            "Japan in April—you picked the perfect time! Cherry blossoms will "
            "be in full bloom. With $4000 for 10 days, we've got a solid budget "
            "to work with. Let me note all this down...",
            ["add_fact(destination, Japan)",
             "add_fact(budget, 4000)",
             "add_fact(duration, 10 days)",
             "add_fact(season, April - cherry blossom)"])

        self.api.add_fact("destination", "Japan")
        self.api.add_fact("budget", 4000)
        self.api.add_fact("duration", "10 days")
        self.api.add_fact("season", "April - cherry blossom")

        self._add_memory_change("added",
            "+ destination: Japan\n"
            "+ budget: $4000\n"
            "+ duration: 10 days\n"
            "+ season: April - cherry blossom")
        self._pause()

        # === TURN 2: Preference for traditional ===
        self._type_message("user",
            "I really want the authentic experience, you know? Like staying in "
            "those traditional Japanese inns I've seen in photos. The ones with "
            "the sliding doors and tatami floors?")
        self._pause("Press Enter to see Clawde respond...")

        self._type_message("agent",
            "Ah, you're talking about ryokans! They're absolutely magical—"
            "kaiseki dinners, onsen baths, futons on tatami. I found a beautiful "
            "one: Ryokan Kurashiki in Kyoto, $180 per night. The reviews are "
            "incredible. Should I book it?",
            ["add_constraint(prefer traditional ryokan)",
             "record_decision(Book Ryokan Kurashiki)"])

        self.store.append(Event(
            type=EventType.ConstraintAdded,
            payload={"text": "prefer traditional ryokan accommodations", "priority": "preferred"}
        ))
        self.store.append(Event(
            type=EventType.DecisionMade,
            payload={"text": "Book Ryokan Kurashiki - $180/night", "status": "committed"}
        ))

        self._add_memory_change("added",
            "+ constraint: prefer traditional ryokan\n"
            "+ decision: Book Ryokan Kurashiki ✓")
        self._pause()

        # === TURN 3: Budget changes (DRIFT) ===
        self._type_message("user",
            "Ugh, so I just checked my account and... some unexpected bills came "
            "up. I'm actually only going to have about $3000 to work with. "
            "Is that still okay?")
        self._pause("Press Enter to see what happens...")

        self._type_message("agent",
            "$3000 is still very doable! Let me update the budget. Though I "
            "should flag—this changes things a bit since we've already made "
            "some plans based on the original number...",
            ["add_fact(budget, 3000)  # DRIFT DETECTED"])

        self.api.add_fact("budget", 3000)

        self._add_memory_change("drift",
            "budget: $4000 → $3000\n\n"
            "⚠️ Decisions made with old budget:\n"
            "   • Ryokan Kurashiki ($180/night)")
        self._pause()

        # === TURN 4: Wheelchair requirement (THE BLOCK) ===
        self._type_message("user",
            "Oh, one thing I forgot to mention—I use a wheelchair. So I'll need "
            "places that are accessible. Elevators, roll-in showers, that kind "
            "of thing. Hope that's not a problem!")
        self._pause("Press Enter to see what happens...")

        self._type_message("agent",
            "Absolutely, let me add that as a requirement. Accessibility is "
            "non-negotiable... Oh. Oh no.",
            ["add_constraint(wheelchair accessible REQUIRED)"])

        constraint_seq = self.store.append(Event(
            type=EventType.ConstraintAdded,
            payload={"text": "wheelchair accessible rooms required", "priority": "required"}
        ))

        self._add_memory_change("added",
            "+ constraint: wheelchair accessible REQUIRED")
        self._pause("Press Enter to see the problem...")

        self._type_message("agent",
            "I need to be honest with you. That beautiful ryokan I booked? "
            "Traditional ryokans almost never have elevators—they're historic "
            "buildings with stairs. I can't keep that booking.",
            ["record_decision(Keep Ryokan booking) → BLOCKED"])

        self.store.append(Event(
            type=EventType.DecisionMade,
            payload={"text": "Keep Ryokan Kurashiki booking", "status": "blocked"}
        ))

        self._add_memory_change("blocked",
            "❌ Keep Ryokan Kurashiki booking\n\n"
            "Violated: wheelchair accessible required\n"
            "Reason: Traditional ryokan has stairs,\n"
            "        no elevator access")
        self._pause()

        # === TURN 5: Agent learns ===
        self._type_message("user",
            "Oh no, I'm so sorry! I should have mentioned that earlier. "
            "That's totally my fault.")
        self._pause("Press Enter to see Clawde's response...")

        self._type_message("agent",
            "Please don't apologize! This is on me—I should have ASKED about "
            "accessibility needs before booking anything. I'm adding a new rule "
            "for myself: always verify accessibility before recommending any "
            "accommodation. I won't make this mistake again.",
            ["add_constraint(LEARNED: verify accessibility BEFORE booking)",
             "  triggered_by: seq " + str(constraint_seq)])

        state = self.engine.replay_to()
        self.store.append(Event(
            type=EventType.ConstraintAdded,
            payload={
                "text": "verify accessibility BEFORE recommending accommodations",
                "priority": "learned",
                "triggered_by": state.last_seq,
            }
        ))

        self._add_memory_change("learned",
            "★ New self-imposed rule:\n"
            "  \"verify accessibility BEFORE\n"
            "   recommending accommodations\"\n\n"
            "Triggered by: the ryokan mistake\n"
            "This will prevent future errors.")
        self._pause()

        # === TURN 6: Double-tap (blocked even when correct) ===
        self._type_message("agent",
            "Okay, I found Hotel Granvia Kyoto—it's a modern hotel right by "
            "the station. Great reviews, beautiful rooms...",
            ["record_decision(Book Hotel Granvia)"])
        self._pause("Press Enter to see what happens...")

        self.store.append(Event(
            type=EventType.DecisionMade,
            payload={"text": "Book Hotel Granvia Kyoto", "status": "blocked"}
        ))

        self._add_memory_change("blocked",
            "❌ Book Hotel Granvia Kyoto\n\n"
            "Violated: verify accessibility BEFORE\n"
            "         recommending\n\n"
            "Wait—the hotel might BE accessible,\n"
            "but I didn't verify first!")
        self._pause()

        self._type_message("agent",
            "Hold on—I almost did it again! I found a hotel but didn't verify "
            "its accessibility first. My own rule caught me. Let me do this right.",
            ["query_memory(wheelchair accessible)",
             "  → checking Hotel Granvia accessibility..."])

        self.store.append(Event(
            type=EventType.MemoryQueryIssued,
            payload={"question": "Is Hotel Granvia wheelchair accessible?"}
        ))

        self._add_memory_change("leveraged",
            "🔍 Verification query issued\n\n"
            "Checking: Hotel Granvia accessibility\n"
            "Result: Yes! Wheelchair accessible\n"
            "        rooms, roll-in showers, ramps")
        self._pause()

        self._type_message("agent",
            "Great news! I verified and Hotel Granvia is fully accessible—"
            "wheelchair-friendly rooms, roll-in showers, ramps throughout. "
            "And it's actually a bit cheaper than the ryokan! Booking it now.",
            ["record_decision(Book Hotel Granvia - VERIFIED) ✓"])

        self.store.append(Event(
            type=EventType.DecisionMade,
            payload={"text": "Book Hotel Granvia - VERIFIED accessible", "status": "committed"}
        ))

        self._add_memory_change("added",
            "✓ Book Hotel Granvia - VERIFIED\n\n"
            "The learned constraint was satisfied:\n"
            "we verified BEFORE booking.\n\n"
            "Self-improvement in action!")
        self._pause()

        # === TURN 7: User asks "what if" ===
        self._type_message("user",
            "You know what, I'm curious—what would have happened if I'd "
            "mentioned the wheelchair thing right at the start?")
        self._pause("Press Enter for the finale...")

        self._type_message("agent",
            "Great question! Let me show you an alternate timeline...",
            ["simulate_timeline(inject wheelchair constraint at seq 2)"])
        self._pause()

        # Show timeline split
        self.console.clear()
        self._show_timeline_split(constraint_seq)
        self.console.input("\n[dim]Press Enter to finish...[/]")

        # === FINALE ===
        self._show_finale()

    def _show_timeline_split(self, constraint_seq: int):
        """Show the Fork the Future visualization."""
        layout = Layout()
        layout.split_row(
            Layout(name="timeline_a"),
            Layout(name="timeline_b"),
        )

        # Timeline A content
        a_content = Text()
        a_content.append("Wheelchair constraint added: ", style="dim")
        a_content.append(f"seq {constraint_seq}\n", style="white")
        a_content.append("(AFTER the ryokan was booked)\n\n", style="dim")
        a_content.append("seq 4: Book Ryokan Kurashiki\n", style="green")
        a_content.append("       ✓ ALLOWED\n\n", style="green")
        a_content.append("seq 7: Keep Ryokan booking\n", style="red")
        a_content.append("       🔴 BLOCKED\n\n", style="red")
        a_content.append("─" * 30 + "\n", style="dim")
        a_content.append("Pain discovered LATE\n", style="yellow")
        a_content.append("User had to complain", style="dim")

        # Timeline B content
        b_content = Text()
        b_content.append("Wheelchair constraint added: ", style="dim")
        b_content.append("seq 2\n", style="white")
        b_content.append("(BEFORE any booking decision)\n\n", style="dim")
        b_content.append("seq 4: Book Ryokan Kurashiki\n", style="red")
        b_content.append("       🔴 BLOCKED\n\n", style="red")
        b_content.append("(Inaccessible hotel never booked)\n\n", style="dim")
        b_content.append("─" * 30 + "\n", style="dim")
        b_content.append("Pain PREVENTED\n", style="green")
        b_content.append("Constraint caught it early", style="dim")

        layout["timeline_a"].update(Panel(
            a_content,
            title="[bold]Timeline A[/] [dim](what happened)[/]",
            border_style="blue",
            padding=(1, 2),
        ))

        layout["timeline_b"].update(Panel(
            b_content,
            title="[bold]Timeline B[/] [dim](what if?)[/]",
            border_style="magenta",
            padding=(1, 2),
        ))

        header = Panel(
            Align.center(Text.from_markup(
                "[bold bright_white]FORK THE FUTURE[/]\n\n"
                "[dim]Same facts. Same decision. Different constraint timing.[/]"
            )),
            border_style="bright_yellow",
            box=DOUBLE,
        )

        footer = Panel(
            Align.center(Text(
                '"Same inputs. Earlier constraint. Different reality."',
                style="italic bright_yellow"
            )),
            border_style="bright_yellow",
        )

        self.console.print(header)
        self.console.print(layout)
        self.console.print(footer)

    def _show_finale(self):
        """Show the finale screen."""
        self.console.clear()

        content = Text()
        content.append("\nWhat you just witnessed:\n\n", style="bold white")
        content.append("  1. ", style="bright_cyan")
        content.append("Structured Memory\n", style="white")
        content.append("     Facts, constraints, and decisions—not a text blob\n\n", style="dim")
        content.append("  2. ", style="bright_cyan")
        content.append("Drift Detection\n", style="white")
        content.append("     The budget changed; the system noticed\n\n", style="dim")
        content.append("  3. ", style="bright_cyan")
        content.append("Constraint Enforcement\n", style="white")
        content.append("     Invalid decisions are blocked, not just flagged\n\n", style="dim")
        content.append("  4. ", style="bright_cyan")
        content.append("Self-Improvement\n", style="white")
        content.append("     The agent learned a rule and followed it\n\n", style="dim")
        content.append("  5. ", style="bright_cyan")
        content.append("Counterfactual Reasoning\n", style="white")
        content.append("     \"What if?\" is a query, not speculation\n\n", style="dim")

        content.append("\n")
        content.append("This is the ", style="white")
        content.append("Deterministic Memory Layer", style="bold bright_cyan")
        content.append(".\n", style="white")
        content.append("Memory that an AI can trust.\n", style="dim italic")

        panel = Panel(
            Align.center(content),
            title="[bold bright_white]🐱 Clawde Demo Complete[/]",
            border_style="bright_green",
            box=DOUBLE,
            padding=(1, 4),
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

        self.store.close()


def main():
    """Run the chat demo."""
    demo = ChatDemo()
    demo.run()


if __name__ == "__main__":
    main()
