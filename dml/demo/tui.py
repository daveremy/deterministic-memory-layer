"""Demo TUI that runs real Claude prompts with DML monitor and narrator."""

import subprocess
import time
from pathlib import Path
from dataclasses import dataclass, field

import yaml
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.box import ROUNDED, DOUBLE, HEAVY
from rich.align import Align
from rich.padding import Padding

from dml.events import EventStore
from dml.replay import ReplayEngine


def load_demo_prompts(name: str = "japan_trip") -> dict:
    """Load a demo script from YAML file.

    Returns full script dict with intro, prompts, outro, etc.
    """
    prompts_file = Path(__file__).parent / "prompts.yaml"
    if not prompts_file.exists():
        raise FileNotFoundError(f"Demo prompts file not found: {prompts_file}")
    with open(prompts_file) as f:
        data = yaml.safe_load(f)
    if name not in data:
        available = list(data.keys())
        raise KeyError(f"Demo script '{name}' not found. Available: {available}")
    return data[name]


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    user_input: str
    claude_response: str = ""
    narrator: str = ""


class DemoTUI:
    """Demo TUI that looks like real Claude CLI with narrator and DML monitor."""

    def __init__(
        self,
        script_name: str = "japan_trip",
        pause_between: bool = False,
        db_path: str | None = None,
    ):
        self.console = Console()
        self.turns: list[ConversationTurn] = []
        self.current_narrator: str = ""
        self.status: str = ""
        self.script_name = script_name
        self.pause_between = pause_between

        # Use default path if not specified
        if db_path is None:
            db_path = str(Path.home() / ".dml" / "memory.db")
        self.db_path = db_path

    def run_claude_prompt(self, prompt: str, continue_session: bool = False) -> str:
        """Run claude -p and return response."""
        cmd = ["claude", "-p", prompt.strip(), "--allowedTools", "mcp__dml__*"]
        if continue_session:
            cmd.append("-c")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return "[Timeout - Claude took too long to respond]"
        except FileNotFoundError:
            return "[Error: claude command not found. Install Claude Code first.]"

    def _get_dml_state(self):
        """Get current DML state for monitor display."""
        try:
            store = EventStore(self.db_path)
            engine = ReplayEngine(store)
            state = engine.replay_to()
            events = store.get_events()
            store.close()
            return state, events
        except Exception:
            return None, []

    def _make_chat_panel(self) -> Panel:
        """Create chat panel that looks like Claude CLI."""
        content = Text()

        # Show conversation turns
        visible_turns = self.turns[-3:]  # Show last 3 turns to fit
        for turn in visible_turns:
            # User input with > prefix (like Claude CLI)
            for i, line in enumerate(turn.user_input.strip().split('\n')):
                if i == 0:
                    content.append("> ", style="bright_green bold")
                else:
                    content.append("  ", style="bright_green")
                content.append(line + "\n", style="white")
            content.append("\n")

            # Claude response
            if turn.claude_response:
                # Show full response, preserve formatting
                response_lines = turn.claude_response.split('\n')
                for line in response_lines:
                    content.append(line + "\n", style="white")
                content.append("\n")

        # Status line at bottom
        if self.status:
            content.append(self.status, style="dim italic")

        return Panel(
            content,
            title="[bold white]claude[/]",
            border_style="bright_blue",
            box=ROUNDED,
            padding=(0, 1),
        )

    def _make_narrator_panel(self) -> Panel:
        """Create narrator panel with current commentary."""
        if not self.current_narrator:
            content = Text("Watching the conversation...", style="dim italic")
        else:
            content = Text()
            lines = self.current_narrator.strip().split('\n')

            # First line is usually the title
            if lines:
                content.append(lines[0] + "\n\n", style="bold bright_yellow")
                for line in lines[1:]:
                    content.append(line + "\n", style="white")

        return Panel(
            content,
            title="[bold bright_yellow]Narrator[/]",
            border_style="yellow",
            box=HEAVY,
            padding=(0, 1),
        )

    def _make_facts_panel(self, state) -> Panel:
        """Create the facts panel."""
        content = Text()

        if state is None or not state.facts:
            content.append("(waiting...)", style="dim")
        else:
            for key, fact in list(state.facts.items())[:8]:  # Limit to 8
                content.append(f"{key}: ", style="cyan bold")
                content.append(f"{fact.value}\n", style="white")

        return Panel(
            content,
            title="[bold]Facts[/]",
            border_style="blue",
            box=ROUNDED,
        )

    def _make_constraints_panel(self, state) -> Panel:
        """Create the constraints panel."""
        content = Text()

        if state is None:
            content.append("(waiting...)", style="dim")
        else:
            active = [c for c in state.constraints.values() if c.active]
            if not active:
                content.append("(none)", style="dim")
            else:
                for c in active[:5]:  # Limit to 5
                    if c.priority == "required":
                        content.append("! ", style="red bold")
                    else:
                        content.append("o ", style="green")
                    # Truncate long constraints
                    text = c.text[:40] + "..." if len(c.text) > 40 else c.text
                    content.append(f"{text}\n", style="white")

        return Panel(
            content,
            title="[bold]Constraints[/]",
            border_style="green",
            box=ROUNDED,
        )

    def _make_decisions_panel(self, state) -> Panel:
        """Create the decisions panel."""
        content = Text()

        if state is None:
            content.append("(waiting...)", style="dim")
        else:
            if not state.decisions:
                content.append("(none)", style="dim")
            else:
                for d in state.decisions[-5:]:  # Last 5
                    if d.status == "blocked":
                        content.append("X ", style="red bold")
                        text = d.text[:35] + "..." if len(d.text) > 35 else d.text
                        content.append(f"{text}\n", style="red")
                    else:
                        content.append("+ ", style="green bold")
                        text = d.text[:35] + "..." if len(d.text) > 35 else d.text
                        content.append(f"{text}\n", style="white")

        return Panel(
            content,
            title="[bold]Decisions[/]",
            border_style="magenta",
            box=ROUNDED,
        )

    def _make_events_panel(self, state, events) -> Panel:
        """Create the events panel."""
        content = Text()

        if not events:
            content.append("(waiting...)", style="dim")
        else:
            for e in events[-6:]:  # Last 6 events
                seq = e.global_seq
                etype = e.type.value

                if "Decision" in etype:
                    status = e.payload.get("status", "")
                    if status == "blocked":
                        content.append(f"{seq:2} ", style="dim")
                        content.append("BLOCKED\n", style="red bold")
                    else:
                        content.append(f"{seq:2} ", style="dim")
                        content.append("Decision+\n", style="green")
                elif "Constraint" in etype:
                    priority = e.payload.get("priority", "")
                    content.append(f"{seq:2} ", style="dim")
                    if priority == "required":
                        content.append("Constraint!\n", style="red")
                    else:
                        content.append("Constraint+\n", style="yellow")
                elif "Fact" in etype:
                    key = e.payload.get("key", "?")[:12]
                    content.append(f"{seq:2} ", style="dim")
                    content.append(f"Fact+ {key}\n", style="cyan")
                elif "Query" in etype:
                    content.append(f"{seq:2} ", style="dim")
                    content.append("Query\n", style="bright_blue")
                else:
                    short = etype.replace("Memory", "").replace("Added", "+")[:15]
                    content.append(f"{seq:2} {short}\n", style="dim")

        seq_display = state.last_seq if state else 0
        return Panel(
            content,
            title=f"[bold]Events[/] [dim]#{seq_display}[/]",
            border_style="dim",
            box=ROUNDED,
        )

    def _make_layout(self) -> Layout:
        """Create the full layout."""
        state, events = self._get_dml_state()

        layout = Layout()

        # Main split: left (chat + narrator) and right (DML monitor)
        layout.split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1),
        )

        # Left side: chat on top, narrator on bottom
        layout["left"].split_column(
            Layout(name="chat", ratio=3),
            Layout(name="narrator", ratio=1),
        )

        # Right side: DML panels stacked
        layout["right"].split_column(
            Layout(name="facts"),
            Layout(name="constraints"),
            Layout(name="decisions"),
            Layout(name="events"),
        )

        layout["chat"].update(self._make_chat_panel())
        layout["narrator"].update(self._make_narrator_panel())
        layout["facts"].update(self._make_facts_panel(state))
        layout["constraints"].update(self._make_constraints_panel(state))
        layout["decisions"].update(self._make_decisions_panel(state))
        layout["events"].update(self._make_events_panel(state, events))

        return layout

    def _show_intro(self, script: dict):
        """Show intro screen."""
        self.console.clear()

        intro_text = script.get("intro", "").strip()
        name = script.get("name", self.script_name)

        content = Text()
        content.append(f"\n{name}\n", style="bold bright_cyan")
        content.append("─" * 50 + "\n\n", style="dim")
        content.append(intro_text + "\n", style="white")

        panel = Panel(
            Align.center(content),
            title="[bold]DML Demo[/]",
            border_style="bright_magenta",
            box=DOUBLE,
            padding=(1, 4),
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()
        self.console.input("[dim]Press Enter to begin...[/]")

    def _show_outro(self, script: dict):
        """Show outro screen."""
        self.console.clear()

        outro_text = script.get("outro", "Demo complete.").strip()

        content = Text()
        for line in outro_text.split('\n'):
            if line.strip().startswith('•'):
                content.append("  " + line + "\n", style="bright_cyan")
            elif line.strip() and line == line.upper():
                content.append("\n" + line + "\n\n", style="bold bright_green")
            else:
                content.append(line + "\n", style="white")

        panel = Panel(
            Align.center(content),
            border_style="bright_green",
            box=DOUBLE,
            padding=(1, 4),
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

    def run(self):
        """Run the demo."""
        # Load script
        try:
            script = load_demo_prompts(self.script_name)
        except (FileNotFoundError, KeyError) as e:
            self.console.print(f"[red]Error: {e}[/]")
            return

        prompts = script.get("prompts", [])
        if not prompts:
            self.console.print("[red]Error: No prompts in script[/]")
            return

        # Reset DML first
        self.console.print("[dim]Resetting DML database...[/]")
        subprocess.run(
            ["uv", "run", "dml", "reset", "--force"],
            capture_output=True
        )
        time.sleep(0.5)

        # Show intro
        self._show_intro(script)
        self.console.clear()

        with Live(self._make_layout(), refresh_per_second=4, console=self.console) as live:

            for i, prompt_data in enumerate(prompts):
                prompt = prompt_data.get("prompt", "").strip()
                narrator = prompt_data.get("narrator", "").strip()

                # Create new turn with user input
                turn = ConversationTurn(user_input=prompt)
                self.turns.append(turn)
                self.current_narrator = ""
                self.status = f"Sending message {i+1}/{len(prompts)}..."
                live.update(self._make_layout())

                # Small pause to show the user message
                time.sleep(1)

                # Run Claude
                self.status = "Claude is thinking..."
                live.update(self._make_layout())

                response = self.run_claude_prompt(prompt, continue_session=(i > 0))

                # Update turn with response
                turn.claude_response = response
                self.status = ""
                live.update(self._make_layout())

                # Pause to read response
                time.sleep(2)

                # Show narrator commentary
                if narrator:
                    self.current_narrator = narrator
                    live.update(self._make_layout())

                    if self.pause_between:
                        self.console.print()
                        self.console.input("[dim]Press Enter to continue...[/]")
                    else:
                        # Auto-advance after reading time
                        time.sleep(4)

        # Show outro
        self._show_outro(script)


def main(script_name: str = "japan_trip", pause: bool = False, db_path: str | None = None):
    """Run the demo TUI."""
    demo = DemoTUI(script_name=script_name, pause_between=pause, db_path=db_path)
    demo.run()


if __name__ == "__main__":
    main()
