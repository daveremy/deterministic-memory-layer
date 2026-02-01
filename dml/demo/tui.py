"""Demo TUI that runs real Claude prompts with DML monitor."""

import subprocess
import time
from pathlib import Path
from dataclasses import dataclass, field

import yaml
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.box import ROUNDED, DOUBLE

from dml.events import EventStore
from dml.replay import ReplayEngine


def load_demo_prompts(name: str = "japan_trip") -> tuple[dict, list[dict]]:
    """Load prompts from YAML file.

    Returns:
        Tuple of (script_info, prompts) where script_info contains name/description.
    """
    prompts_file = Path(__file__).parent / "prompts.yaml"
    if not prompts_file.exists():
        raise FileNotFoundError(f"Demo prompts file not found: {prompts_file}")
    with open(prompts_file) as f:
        data = yaml.safe_load(f)
    if name not in data:
        available = list(data.keys())
        raise KeyError(f"Demo script '{name}' not found. Available: {available}")
    script = data[name]
    return script, script["prompts"]


# Chat bubble width for rendering
BUBBLE_WIDTH = 58


@dataclass
class ChatMessage:
    """A message in the chat."""
    role: str  # "user" or "assistant"
    content: str
    tool_calls: list[str] = field(default_factory=list)


class DemoTUI:
    """Demo TUI that runs real Claude prompts with live DML monitor."""

    def __init__(
        self,
        script_name: str = "japan_trip",
        pause_between: bool = False,
        db_path: str | None = None,
    ):
        self.console = Console()
        self.messages: list[ChatMessage] = []
        self.status = "Ready"
        self.script_name = script_name
        self.pause_between = pause_between

        # Use default path if not specified
        if db_path is None:
            db_path = str(Path.home() / ".dml" / "memory.db")
        self.db_path = db_path

    def run_claude_prompt(self, prompt: str, continue_session: bool = False) -> str:
        """Run claude -p and return response."""
        cmd = ["claude", "-p", prompt, "--allowedTools", "mcp__dml__*"]
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

    def _render_chat_message(self, msg: ChatMessage) -> Text:
        """Render a single chat message with bubble styling."""
        result = Text()
        inner_width = BUBBLE_WIDTH - 4  # Account for "| " and " |"

        # Simple word-wrap
        def wrap_text(text: str, width: int) -> list[str]:
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

        if msg.role == "user":
            result.append("You\n", style="bold bright_cyan")
            result.append("+" + "-" * (BUBBLE_WIDTH - 2) + "+\n", style="cyan")

            for line in wrap_text(msg.content, inner_width):
                padded = f"| {line}".ljust(BUBBLE_WIDTH - 1) + "|\n"
                result.append(padded, style="cyan")

            result.append("+" + "-" * (BUBBLE_WIDTH - 2) + "+\n", style="cyan")

        else:
            result.append("Claude\n", style="bold bright_green")
            result.append("+" + "-" * (BUBBLE_WIDTH - 2) + "+\n", style="green")

            # Truncate long responses for display
            content = msg.content
            if len(content) > 500:
                content = content[:500] + "..."

            for line in wrap_text(content, inner_width):
                padded = f"| {line}".ljust(BUBBLE_WIDTH - 1) + "|\n"
                result.append(padded, style="green")

            result.append("+" + "-" * (BUBBLE_WIDTH - 2) + "+\n", style="green")

        return result

    def _make_chat_panel(self) -> Panel:
        """Create the main chat panel."""
        content = Text()

        # Show last few messages
        for msg in self.messages[-4:]:
            content.append(self._render_chat_message(msg))
            content.append("\n")

        # Status at bottom
        content.append(f"\n[{self.status}]", style="dim italic")

        return Panel(
            content,
            title="[bold bright_white]Chat[/]",
            subtitle="[dim]Claude + DML[/]",
            border_style="bright_blue",
            box=DOUBLE,
            padding=(0, 1),
        )

    def _make_facts_panel(self, state) -> Panel:
        """Create the facts panel."""
        content = Text()

        if state is None or not state.facts:
            content.append("(waiting...)", style="dim")
        else:
            for key, fact in state.facts.items():
                content.append(f"{key}: ", style="cyan bold")
                content.append(f"{fact.value}\n", style="white")

        return Panel(content, title="[bold]Facts[/]", border_style="blue")

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
                for c in active:
                    if c.priority == "learned":
                        content.append("* ", style="yellow bold")
                        content.append(f"{c.text}\n", style="yellow")
                    elif c.priority == "required":
                        content.append("! ", style="red bold")
                        content.append(f"{c.text}\n", style="white")
                    else:
                        content.append("o ", style="green")
                        content.append(f"{c.text}\n", style="dim")

        return Panel(content, title="[bold]Constraints[/]", border_style="green")

    def _make_decisions_panel(self, state) -> Panel:
        """Create the decisions panel."""
        content = Text()

        if state is None:
            content.append("(waiting...)", style="dim")
        else:
            if not state.decisions:
                content.append("(none)", style="dim")
            else:
                for d in state.decisions[-5:]:
                    if d.status == "blocked":
                        content.append("X ", style="red bold")
                        content.append(f"{d.text}\n", style="red")
                    else:
                        content.append("+ ", style="green bold")
                        content.append(f"{d.text}\n", style="white")

        return Panel(content, title="[bold]Decisions[/]", border_style="magenta")

    def _make_events_panel(self, state, events) -> Panel:
        """Create the events panel."""
        content = Text()

        if not events:
            content.append("(waiting...)", style="dim")
        else:
            for e in events[-8:]:
                seq = e.global_seq
                etype = e.type.value
                short = etype.replace("Added", "+").replace("Made", "").replace("Memory", "")

                if "Decision" in etype:
                    status = e.payload.get("status", "")
                    if status == "blocked":
                        content.append(f"{seq:2} {short} ", style="dim")
                        content.append("BLOCKED\n", style="red bold")
                    else:
                        content.append(f"{seq:2} {short} ", style="dim")
                        content.append("OK\n", style="green")
                elif "Constraint" in etype:
                    priority = e.payload.get("priority", "")
                    if priority == "required":
                        content.append(f"{seq:2} {short} ", style="dim")
                        content.append("REQUIRED\n", style="red")
                    else:
                        content.append(f"{seq:2} {short}\n", style="dim")
                elif "Fact" in etype:
                    key = e.payload.get("key", "?")
                    content.append(f"{seq:2} Fact+ ", style="dim")
                    content.append(f"{key}\n", style="cyan")
                else:
                    content.append(f"{seq:2} {short}\n", style="dim")

        seq_display = state.last_seq if state else 0
        return Panel(content, title=f"[bold]Events[/] [dim]#{seq_display}[/]", border_style="dim")

    def _make_layout(self) -> Layout:
        """Create the full split layout."""
        state, events = self._get_dml_state()

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
        layout["facts"].update(self._make_facts_panel(state))
        layout["constraints"].update(self._make_constraints_panel(state))
        layout["decisions"].update(self._make_decisions_panel(state))
        layout["events"].update(self._make_events_panel(state, events))

        return layout

    def run(self):
        """Run the demo."""
        # Load prompts
        try:
            script_info, prompts = load_demo_prompts(self.script_name)
        except (FileNotFoundError, KeyError) as e:
            self.console.print(f"[red]Error: {e}[/]")
            return

        script_name = script_info.get("name", self.script_name)

        # Reset DML first
        self.console.print(f"[dim]Resetting DML database...[/]")
        subprocess.run(
            ["uv", "run", "dml", "reset", "--force"],
            capture_output=True
        )

        # Show intro
        self.console.clear()
        intro = Panel(
            Text.from_markup(
                f"\n[bold bright_cyan]{script_name}[/]\n\n"
                f"[white]{script_info.get('description', '')}[/]\n\n"
                f"[dim]{len(prompts)} prompts will be sent to Claude.[/]\n"
                f"[dim]Watch the DML monitor panel on the right.[/]\n"
            ),
            title="[bold]DML Live Demo[/]",
            border_style="bright_magenta",
            box=DOUBLE,
            padding=(1, 4),
        )
        self.console.print()
        self.console.print(intro)
        self.console.print()

        if self.pause_between:
            self.console.input("[dim]Press Enter to start...[/]")
        else:
            self.console.print("[dim]Starting in 3 seconds...[/]")
            time.sleep(3)

        self.console.clear()

        with Live(self._make_layout(), refresh_per_second=4, console=self.console) as live:

            for i, prompt_data in enumerate(prompts):
                prompt = prompt_data["prompt"]
                desc = prompt_data.get("description", f"Prompt {i+1}")

                # Show user prompt
                self.status = f"[{i+1}/{len(prompts)}] {desc}"
                self.messages.append(ChatMessage("user", prompt))
                live.update(self._make_layout())

                # Pause if requested
                if self.pause_between:
                    self.console.print()
                    self.console.input(f"[dim]Press Enter to send prompt {i+1}...[/]")

                # Run Claude
                self.status = f"[{i+1}/{len(prompts)}] Claude thinking..."
                live.update(self._make_layout())

                response = self.run_claude_prompt(prompt, continue_session=(i > 0))

                # Add response
                self.messages.append(ChatMessage("assistant", response))
                self.status = f"[{i+1}/{len(prompts)}] {desc} - Done"
                live.update(self._make_layout())

                # Pause between prompts
                if self.pause_between:
                    self.console.print()
                    self.console.input("[dim]Press Enter to continue...[/]")
                else:
                    time.sleep(3)

        self.console.print()
        self.console.print("[bold green]Demo complete![/]")


def main(script_name: str = "japan_trip", pause: bool = False, db_path: str | None = None):
    """Run the demo TUI."""
    demo = DemoTUI(script_name=script_name, pause_between=pause, db_path=db_path)
    demo.run()


if __name__ == "__main__":
    main()
