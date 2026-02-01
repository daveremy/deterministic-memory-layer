"""Demo TUI using Textual for proper scrolling and interactivity."""

import subprocess
import asyncio
from pathlib import Path
from dataclasses import dataclass, field

import yaml
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Header, Footer, Markdown, Label, Rule, LoadingIndicator
from textual.reactive import reactive
from textual import work

from dml.events import EventStore
from dml.replay import ReplayEngine


def load_demo_prompts(name: str = "japan_trip") -> dict:
    """Load a demo script from YAML file."""
    prompts_file = Path(__file__).parent / "prompts.yaml"
    if not prompts_file.exists():
        raise FileNotFoundError(f"Demo prompts file not found: {prompts_file}")
    with open(prompts_file) as f:
        data = yaml.safe_load(f)
    if name not in data:
        available = list(data.keys())
        raise KeyError(f"Demo script '{name}' not found. Available: {available}")
    return data[name]


# CSS for the app
CSS = """
#main-container {
    width: 100%;
    height: 100%;
}

#left-pane {
    width: 2fr;
}

#right-pane {
    width: 1fr;
}

#chat-container {
    height: 3fr;
    border: solid $primary;
    background: $surface;
}

#chat-scroll {
    scrollbar-gutter: stable;
    padding: 0 1;
}

#narrator-container {
    height: 1fr;
    border: heavy $warning;
    background: $surface-darken-1;
    padding: 0 1;
}

.narrator-title {
    color: $warning;
    text-style: bold;
}

.narrator-text {
    color: $text;
}

.user-prompt {
    color: $success;
    margin-bottom: 1;
}

.claude-response {
    margin-bottom: 1;
}

.turn-divider {
    color: $text-muted;
    margin: 1 0;
}

#facts-panel {
    border: solid $primary;
    height: 1fr;
    padding: 0 1;
}

#constraints-panel {
    border: solid $success;
    height: 1fr;
    padding: 0 1;
}

#decisions-panel {
    border: solid $secondary;
    height: 1fr;
    padding: 0 1;
}

#events-panel {
    border: solid $surface-lighten-2;
    height: 1fr;
    padding: 0 1;
}

.panel-title {
    text-style: bold;
    background: $surface-darken-1;
    width: 100%;
}

#status-bar {
    dock: bottom;
    height: 1;
    background: $surface-darken-2;
    color: $text-muted;
    padding: 0 1;
}

#loading-container {
    height: auto;
    padding: 1;
    background: $primary-darken-3;
    display: none;
}

#loading-container.visible {
    display: block;
}

#loading-status {
    color: $primary-lighten-2;
}

LoadingIndicator {
    height: 1;
    color: $primary;
}

.waiting-input {
    color: $success;
    text-style: bold;
}

.waiting-claude {
    color: $warning;
    text-style: italic;
}

#intro-overlay {
    layer: overlay;
    width: 100%;
    height: 100%;
    background: $surface;
    padding: 2 4;
}

#intro-overlay.hidden {
    display: none;
}

#intro-title {
    text-align: center;
    text-style: bold;
    color: $primary;
    padding: 1;
}

#intro-content {
    padding: 2 4;
    color: $text;
}

#intro-prompt {
    text-align: center;
    text-style: bold;
    color: $success;
    padding: 2;
}

#outro-overlay {
    layer: overlay;
    width: 100%;
    height: 100%;
    background: $surface;
    padding: 2 4;
    display: none;
}

#outro-overlay.visible {
    display: block;
}
"""


class ChatMessage(Static):
    """A single chat message (user or Claude)."""
    pass


class DemoApp(App):
    """Textual app for DML demo with scrolling chat."""

    CSS = CSS
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("space", "next_step", "Next"),
    ]

    # Reactive state
    current_prompt_index = reactive(0)
    narrator_text = reactive("")
    status_text = reactive("Press SPACE to start...")
    is_running = reactive(False)

    def __init__(
        self,
        script_name: str = "japan_trip",
        auto_advance: bool = False,
        db_path: str | None = None,
    ):
        super().__init__()
        self.script_name = script_name
        self.auto_advance = auto_advance
        self.db_path = db_path or str(Path.home() / ".dml" / "memory.db")
        self.script = None
        self.prompts = []
        self.demo_started = False

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header(show_clock=True)

        with Horizontal(id="main-container"):
            # Left pane: chat + narrator (2/3 width)
            with Vertical(id="left-pane"):
                with Vertical(id="chat-container"):
                    yield Label(" claude ", classes="panel-title")
                    with Horizontal(id="loading-container"):
                        yield LoadingIndicator()
                        yield Static("Waiting for Claude...", id="loading-status")
                    yield VerticalScroll(id="chat-scroll")

                with Vertical(id="narrator-container"):
                    yield Label(" Narrator ", classes="panel-title narrator-title")
                    yield Static("", id="narrator-content", classes="narrator-text")

            # Right pane: DML monitor (1/3 width)
            with Vertical(id="right-pane"):
                with Vertical(id="facts-panel"):
                    yield Label(" Facts ", classes="panel-title")
                    yield Static("(waiting...)", id="facts-content")

                with Vertical(id="constraints-panel"):
                    yield Label(" Constraints ", classes="panel-title")
                    yield Static("(none)", id="constraints-content")

                with Vertical(id="decisions-panel"):
                    yield Label(" Decisions ", classes="panel-title")
                    yield Static("(none)", id="decisions-content")

                with Vertical(id="events-panel"):
                    yield Label(" Events ", classes="panel-title")
                    yield Static("(waiting...)", id="events-content")

        yield Static("Press SPACE to start, Q to quit", id="status-bar")
        yield Footer()

        # Intro overlay (shown on top initially)
        with Vertical(id="intro-overlay"):
            yield Static("", id="intro-title")
            yield Static("", id="intro-content")
            yield Static(">>> Press SPACE to start <<<", id="intro-prompt")

        # Outro overlay (hidden initially)
        with Vertical(id="outro-overlay"):
            yield Static("", id="outro-content")

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Load script
        try:
            self.script = load_demo_prompts(self.script_name)
            self.prompts = self.script.get("prompts", [])
            script_name = self.script.get("name", self.script_name)
        except Exception as e:
            self.notify(f"Error loading script: {e}", severity="error")
            return

        # Reset DML database immediately on startup
        subprocess.run(
            ["uv", "run", "dml", "reset", "--force"],
            capture_output=True
        )

        # Populate intro overlay
        intro_title = self.query_one("#intro-title", Static)
        intro_content = self.query_one("#intro-content", Static)
        intro_title.update(f"[bold]{script_name}[/]")
        intro = self.script.get("intro", "").strip()
        if intro:
            intro_content.update(intro)
        else:
            intro_content.update(f"{len(self.prompts)} prompts in this demo.")

        # Populate outro overlay
        outro_content = self.query_one("#outro-content", Static)
        outro = self.script.get("outro", "Demo complete!").strip()
        outro_content.update(outro)

        # Start DML state refresh
        self.set_interval(0.5, self.refresh_dml_state)

    def action_quit(self) -> None:
        """Quit the app."""
        self.exit()

    def action_next_step(self) -> None:
        """Advance to next step."""
        if self.is_running:
            return  # Already running a prompt

        if not self.demo_started:
            # First press - hide intro and start
            self.demo_started = True
            intro_overlay = self.query_one("#intro-overlay")
            intro_overlay.add_class("hidden")
            self.reset_demo()
            self.run_next_prompt()
        elif self.current_prompt_index < len(self.prompts):
            self.run_next_prompt()
        else:
            # Show outro overlay
            outro_overlay = self.query_one("#outro-overlay")
            outro_overlay.add_class("visible")

    def reset_demo(self) -> None:
        """Reset DML database for fresh demo."""
        subprocess.run(
            ["uv", "run", "dml", "reset", "--force"],
            capture_output=True
        )
        # Clear chat
        chat_scroll = self.query_one("#chat-scroll")
        chat_scroll.remove_children()

    @work(exclusive=True)
    async def run_next_prompt(self) -> None:
        """Run the next prompt in the sequence."""
        if self.current_prompt_index >= len(self.prompts):
            return

        self.is_running = True
        prompt_data = self.prompts[self.current_prompt_index]
        prompt = prompt_data.get("prompt", "").strip()
        narrator_text = prompt_data.get("narrator", "").strip()

        # Get UI elements
        status_bar = self.query_one("#status-bar", Static)
        narrator = self.query_one("#narrator-content", Static)
        loading_container = self.query_one("#loading-container")
        loading_status = self.query_one("#loading-status", Static)
        chat_scroll = self.query_one("#chat-scroll", VerticalScroll)

        # Show loading indicator
        loading_container.add_class("visible")
        loading_status.update(f"Sending prompt {self.current_prompt_index + 1}/{len(self.prompts)}...")
        narrator.update(f"[dim]Sending message to Claude...[/]")
        status_bar.update(f"[{self.current_prompt_index + 1}/{len(self.prompts)}] Waiting for Claude...")

        # Add turn divider if not first turn
        if self.current_prompt_index > 0:
            await chat_scroll.mount(Static(f"─── Turn {self.current_prompt_index + 1} ───", classes="turn-divider"))

        # Add user message to chat with > prefix
        user_lines = prompt.split('\n')
        user_text = ""
        for i, line in enumerate(user_lines):
            prefix = "> " if i == 0 else "  "
            user_text += f"{prefix}{line}\n"
        await chat_scroll.mount(Static(user_text, classes="user-prompt"))
        chat_scroll.scroll_end(animate=False)

        # Update loading status
        loading_status.update("Claude is thinking...")

        # Run Claude
        response = await self.run_claude(prompt, continue_session=(self.current_prompt_index > 0))

        # Hide loading indicator
        loading_container.remove_class("visible")

        # Add Claude response as markdown
        await chat_scroll.mount(Markdown(response, classes="claude-response"))
        chat_scroll.scroll_end(animate=False)

        # Update status
        self.current_prompt_index += 1
        is_complete = self.current_prompt_index >= len(self.prompts)

        if is_complete:
            status_bar.update("[bold]Demo complete![/] Press SPACE to see summary, Q to quit.")
            if narrator_text:
                narrator.update(narrator_text)
            else:
                narrator.update("[bold]Demo complete![/]")
        else:
            # Update narrator with commentary
            if self.auto_advance:
                if narrator_text:
                    narrator.update(narrator_text + "\n\n[dim]Auto-advancing in 5 seconds...[/]")
                else:
                    narrator.update("[dim]Auto-advancing in 5 seconds...[/]")
                status_bar.update(f"[{self.current_prompt_index}/{len(self.prompts)}] Auto-advancing...")
            else:
                if narrator_text:
                    narrator.update(narrator_text + "\n\n[bold green]>>> Press SPACE to continue <<<[/]")
                else:
                    narrator.update("[bold green]>>> Press SPACE to continue <<<[/]")
                status_bar.update(f"[{self.current_prompt_index}/{len(self.prompts)}] Press SPACE for next prompt")

        self.is_running = False

        # Auto-advance after delay if enabled
        if self.auto_advance and not is_complete:
            await asyncio.sleep(5)
            self.run_next_prompt()

    async def run_claude(self, prompt: str, continue_session: bool = False) -> str:
        """Run claude -p command asynchronously."""
        cmd = ["claude", "-p", prompt.strip(), "--allowedTools", "mcp__dml__*"]
        if continue_session:
            cmd.append("-c")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            return stdout.decode().strip()
        except asyncio.TimeoutError:
            return "[Timeout - Claude took too long to respond]"
        except FileNotFoundError:
            return "[Error: claude command not found]"

    def refresh_dml_state(self) -> None:
        """Refresh DML panels from database."""
        try:
            store = EventStore(self.db_path)
            engine = ReplayEngine(store)
            state = engine.replay_to()
            events = store.get_events()
            store.close()
        except Exception:
            return

        # Update Facts
        facts_content = self.query_one("#facts-content", Static)
        if state.facts:
            lines = []
            for key, fact in list(state.facts.items())[:10]:
                lines.append(f"[cyan bold]{key}:[/] {fact.value}")
            facts_content.update("\n".join(lines))
        else:
            facts_content.update("(waiting...)")

        # Update Constraints
        constraints_content = self.query_one("#constraints-content", Static)
        active = [c for c in state.constraints.values() if c.active]
        if active:
            lines = []
            for c in active[:6]:
                if c.priority == "required":
                    lines.append(f"[red bold]![/] {c.text[:50]}")
                else:
                    lines.append(f"[green]o[/] {c.text[:50]}")
            constraints_content.update("\n".join(lines))
        else:
            constraints_content.update("(none)")

        # Update Decisions
        decisions_content = self.query_one("#decisions-content", Static)
        if state.decisions:
            lines = []
            for d in state.decisions[-6:]:
                if d.status == "blocked":
                    lines.append(f"[red bold]X[/] [red]{d.text[:40]}[/]")
                else:
                    lines.append(f"[green]+[/] {d.text[:40]}")
            decisions_content.update("\n".join(lines))
        else:
            decisions_content.update("(none)")

        # Update Events
        events_content = self.query_one("#events-content", Static)
        if events:
            lines = []
            for e in events[-8:]:
                seq = e.global_seq
                etype = e.type.value
                if "Decision" in etype:
                    status = e.payload.get("status", "")
                    if status == "blocked":
                        lines.append(f"[dim]{seq:2}[/] [red bold]BLOCKED[/]")
                    else:
                        lines.append(f"[dim]{seq:2}[/] [green]Decision+[/]")
                elif "Constraint" in etype:
                    priority = e.payload.get("priority", "")
                    if priority == "required":
                        lines.append(f"[dim]{seq:2}[/] [red]Constraint![/]")
                    else:
                        lines.append(f"[dim]{seq:2}[/] [yellow]Constraint+[/]")
                elif "Fact" in etype:
                    key = e.payload.get("key", "?")[:12]
                    lines.append(f"[dim]{seq:2}[/] [cyan]Fact+ {key}[/]")
                else:
                    lines.append(f"[dim]{seq:2} {etype[:15]}[/]")
            events_content.update("\n".join(lines))
        else:
            events_content.update("(waiting...)")


def main(script_name: str = "japan_trip", auto: bool = False, db_path: str | None = None):
    """Run the demo TUI."""
    app = DemoApp(script_name=script_name, auto_advance=auto, db_path=db_path)
    app.run()


if __name__ == "__main__":
    main()
