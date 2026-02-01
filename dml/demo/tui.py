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


def load_all_scripts() -> dict:
    """Load all demo scripts from YAML file."""
    prompts_file = Path(__file__).parent / "prompts.yaml"
    if not prompts_file.exists():
        raise FileNotFoundError(f"Demo prompts file not found: {prompts_file}")
    with open(prompts_file) as f:
        return yaml.safe_load(f)


def load_demo_prompts(name: str) -> dict:
    """Load a specific demo script from YAML file."""
    data = load_all_scripts()
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
    margin-top: 1;
    margin-bottom: 1;
}

.claude-response {
    margin-bottom: 2;
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

.inline-loading {
    height: auto;
    padding: 0 0 1 0;
    color: $primary-lighten-2;
}

.inline-loading LoadingIndicator {
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

    TITLE = "Deterministic Memory Layer Demo"
    CSS = CSS
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("space", "next_step", "Next"),
        ("1", "select_script(1)", "Script 1"),
        ("2", "select_script(2)", "Script 2"),
        ("3", "select_script(3)", "Script 3"),
    ]

    # Reactive state
    current_prompt_index = reactive(0)
    narrator_text = reactive("")
    status_text = reactive("Press SPACE to start...")
    is_running = reactive(False)

    def __init__(
        self,
        script_name: str | None = None,
        auto_advance: bool = False,
        db_path: str | None = None,
    ):
        super().__init__()
        self.script_name = script_name  # None means show selection
        self.auto_advance = auto_advance
        self.db_path = db_path or str(Path.home() / ".dml" / "memory.db")
        self.script = None
        self.prompts = []
        self.demo_started = False
        self.script_selected = script_name is not None
        self.available_scripts = []

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header(show_clock=True)

        with Horizontal(id="main-container"):
            # Left pane: chat + narrator (2/3 width)
            with Vertical(id="left-pane"):
                with Vertical(id="chat-container"):
                    yield Label(" claude ", classes="panel-title")
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
        # Load available scripts
        try:
            all_scripts = load_all_scripts()
            self.available_scripts = list(all_scripts.keys())
        except Exception as e:
            self.notify(f"Error loading scripts: {e}", severity="error")
            return

        # If no script specified, show selection screen
        if self.script_name is None:
            self._show_script_selection()
        else:
            self._load_script(self.script_name)

        # Start DML state refresh
        self.set_interval(0.5, self.refresh_dml_state)

    def _show_script_selection(self) -> None:
        """Show script selection on intro overlay."""
        all_scripts = load_all_scripts()
        intro_title = self.query_one("#intro-title", Static)
        intro_content = self.query_one("#intro-content", Static)
        intro_prompt = self.query_one("#intro-prompt", Static)

        intro_title.update("[bold]Deterministic Memory Layer[/]")

        # Build content with context and script list
        lines = [
            "[bold cyan]What is DML?[/]",
            "DML gives AI agents structured, auditable memory. Instead of facts",
            "getting lost in conversation history, DML captures them as queryable",
            "data with full provenance tracking.",
            "",
            "[bold cyan]How it works[/]",
            "This is LIVE - real Claude, real responses. The prompts are scripted",
            "but Claude's responses are not. Claude is connected to the DML MCP",
            "server and every tool call you see is actually happening.",
            "",
            "[bold]Select a demo:[/]",
            "",
        ]
        for i, (key, script) in enumerate(all_scripts.items(), 1):
            name = script.get("name", key)
            desc = script.get("description", "")
            lines.append(f"  [bold cyan]{i}[/]  [bold]{name}[/]")
            if desc:
                lines.append(f"      {desc}")
            lines.append("")

        intro_content.update("\n".join(lines))
        intro_prompt.update(">>> Press 1, 2, or 3 to select, Q to quit <<<")

    def _load_script(self, script_name: str) -> None:
        """Load a specific script and populate overlays."""
        try:
            self.script = load_demo_prompts(script_name)
            self.prompts = self.script.get("prompts", [])
            self.script_name = script_name
            self.script_selected = True
            display_name = self.script.get("name", script_name)
        except Exception as e:
            self.notify(f"Error loading script: {e}", severity="error")
            return

        # Reset DML database
        subprocess.run(
            ["uv", "run", "dml", "reset", "--force"],
            capture_output=True
        )

        # Populate intro overlay
        intro_title = self.query_one("#intro-title", Static)
        intro_content = self.query_one("#intro-content", Static)
        intro_prompt = self.query_one("#intro-prompt", Static)

        intro_title.update(f"[bold]{display_name}[/]")
        intro = self.script.get("intro", "").strip()
        if intro:
            intro_content.update(intro)
        else:
            intro_content.update(f"{len(self.prompts)} prompts in this demo.")
        intro_prompt.update(">>> Press SPACE to start, Q to quit <<<")

        # Populate outro overlay
        outro_content = self.query_one("#outro-content", Static)
        outro = self.script.get("outro", "Demo complete!").strip()
        outro_content.update(outro)

    def action_select_script(self, number: int) -> None:
        """Handle script selection by number key."""
        if self.script_selected or self.demo_started:
            return  # Already selected or running

        if not self.available_scripts:
            return

        # Map number to script (1-indexed)
        if 1 <= number <= len(self.available_scripts):
            script_name = self.available_scripts[number - 1]
            self._load_script(script_name)

    def action_quit(self) -> None:
        """Quit the app."""
        self.exit()

    def action_next_step(self) -> None:
        """Advance to next step."""
        if self.is_running:
            return  # Already running a prompt

        if not self.script_selected:
            return  # Need to select a script first (press 1, 2, or 3)

        if not self.demo_started:
            # First press after script selected - hide intro and start
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
        context_text = prompt_data.get("context", "").strip()
        narrator_text = prompt_data.get("narrator", "").strip()

        # Get UI elements
        status_bar = self.query_one("#status-bar", Static)
        narrator = self.query_one("#narrator-content", Static)
        chat_scroll = self.query_one("#chat-scroll", VerticalScroll)

        # Show context in narrator before sending
        if context_text:
            narrator.update(context_text)
        else:
            narrator.update(f"[dim]Sending prompt {self.current_prompt_index + 1}...[/]")

        status_bar.update(f"[{self.current_prompt_index + 1}/{len(self.prompts)}] Sending to Claude... [dim](Q to quit)[/]")

        # Add user message to chat with > prefix
        user_lines = prompt.split('\n')
        user_text = ""
        for i, line in enumerate(user_lines):
            prefix = "> " if i == 0 else "  "
            user_text += f"{prefix}{line}\n"
        await chat_scroll.mount(Static(user_text, classes="user-prompt"))

        # Add inline loading indicator after user message
        loading_widget = Horizontal(
            LoadingIndicator(),
            Static(" Claude is thinking..."),
            classes="inline-loading",
            id="inline-loading"
        )
        await chat_scroll.mount(loading_widget)
        chat_scroll.scroll_end(animate=False)

        # Update narrator to show waiting state while keeping context visible
        if context_text:
            narrator.update(context_text + "\n\n[dim italic]Waiting for Claude...[/]")
        else:
            narrator.update("[dim italic]Waiting for Claude...[/]")

        # Capture state before Claude runs
        state_before = self._get_dml_state()

        # Run Claude
        response = await self.run_claude(prompt, continue_session=(self.current_prompt_index > 0))

        # Capture state after Claude runs
        state_after = self._get_dml_state()

        # Check expectations
        expects = prompt_data.get("expects")
        expectation_warning = self._check_expectation(expects, state_before, state_after)

        # Remove inline loading indicator
        try:
            loading_widget = self.query_one("#inline-loading")
            await loading_widget.remove()
        except Exception:
            pass

        # Add Claude response as markdown
        await chat_scroll.mount(Markdown(response, classes="claude-response"))
        chat_scroll.scroll_end(animate=False)

        # Update status
        self.current_prompt_index += 1
        is_complete = self.current_prompt_index >= len(self.prompts)

        # Build narrator text with optional warning
        final_narrator = narrator_text
        if expectation_warning:
            final_narrator = f"[yellow bold]⚠ {expectation_warning}[/]\n\n{narrator_text}" if narrator_text else f"[yellow bold]⚠ {expectation_warning}[/]"

        if is_complete:
            status_bar.update("[bold]Demo complete![/] Press SPACE to see summary, Q to quit.")
            if final_narrator:
                narrator.update(final_narrator)
            else:
                narrator.update("[bold]Demo complete![/]")
        else:
            # Update narrator with commentary
            if self.auto_advance:
                if final_narrator:
                    narrator.update(final_narrator + "\n\n[dim]Auto-advancing in 5 seconds...[/]")
                else:
                    narrator.update("[dim]Auto-advancing in 5 seconds...[/]")
                status_bar.update(f"[{self.current_prompt_index}/{len(self.prompts)}] Auto-advancing... [dim](Q to quit)[/]")
            else:
                if final_narrator:
                    narrator.update(final_narrator + "\n\n[bold green]>>> Press SPACE to continue <<<[/]")
                else:
                    narrator.update("[bold green]>>> Press SPACE to continue <<<[/]")
                status_bar.update(f"[{self.current_prompt_index}/{len(self.prompts)}] Press SPACE to continue, Q to quit")

        self.is_running = False

        # Auto-advance after delay if enabled
        if self.auto_advance and not is_complete:
            await asyncio.sleep(5)
            self.run_next_prompt()

    def _get_dml_state(self) -> dict | None:
        """Get current DML state for comparison."""
        try:
            store = EventStore(self.db_path)
            engine = ReplayEngine(store)
            state = engine.replay_to()
            events = store.get_events()
            store.close()
            return {
                "num_facts": len(state.facts),
                "num_constraints": len([c for c in state.constraints.values() if c.active]),
                "num_decisions": len(state.decisions),
                "num_blocked": len([d for d in state.decisions if d.status == "blocked"]),
                "last_seq": state.last_seq,
            }
        except Exception:
            return None

    def _check_expectation(self, expects: str | None, before: dict | None, after: dict | None) -> str | None:
        """Check if expected outcome occurred. Returns warning message if not."""
        if not expects or not before or not after:
            return None

        if expects == "facts":
            if after["num_facts"] <= before["num_facts"]:
                return "Expected new facts to be recorded, but none were added."

        elif expects == "decision":
            new_decisions = after["num_decisions"] - before["num_decisions"]
            if new_decisions == 0:
                return "Expected a decision to be recorded, but none was made."

        elif expects == "constraint":
            if after["num_constraints"] <= before["num_constraints"]:
                return "Expected a constraint to be added, but none was."

        elif expects == "blocked":
            new_blocked = after["num_blocked"] - before["num_blocked"]
            if new_blocked == 0:
                return "Expected a decision to be BLOCKED, but it wasn't."

        return None

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

        # Update Facts - show key: value, with previous value if changed
        facts_content = self.query_one("#facts-content", Static)
        if state.facts:
            lines = []
            for key, fact in list(state.facts.items())[:8]:
                lines.append(f"[bold cyan]{key}[/]")
                if fact.previous_value is not None:
                    lines.append(f"  {fact.value} [dim](was: {fact.previous_value})[/]")
                else:
                    lines.append(f"  {fact.value}")
            facts_content.update("\n".join(lines))
        else:
            facts_content.update("[dim]No facts recorded yet[/]")

        # Update Constraints - show priority indicator and full text
        constraints_content = self.query_one("#constraints-content", Static)
        active = [c for c in state.constraints.values() if c.active]
        if active:
            lines = []
            for c in active[:5]:
                if c.priority == "required":
                    lines.append(f"[red bold]● REQUIRED[/]")
                    lines.append(f"  {c.text}")
                else:
                    lines.append(f"[yellow]○ preferred[/]")
                    lines.append(f"  {c.text}")
            constraints_content.update("\n".join(lines))
        else:
            constraints_content.update("[dim]No constraints active[/]")

        # Update Decisions - show status and text, newest first
        decisions_content = self.query_one("#decisions-content", Static)
        if state.decisions:
            lines = []
            # Show newest decisions first
            for d in reversed(state.decisions[-5:]):
                if d.status == "blocked":
                    lines.append(f"[red bold]✗ BLOCKED[/]")
                    lines.append(f"  [red]{d.text}[/]")
                else:
                    lines.append(f"[green bold]✓ Committed[/]")
                    lines.append(f"  {d.text}")
            decisions_content.update("\n".join(lines))
        else:
            decisions_content.update("[dim]No decisions recorded[/]")

        # Update Events - show newest first with descriptive text
        events_content = self.query_one("#events-content", Static)
        if events:
            lines = []
            # Show newest events first
            for e in reversed(events[-6:]):
                seq = e.global_seq
                etype = e.type.value
                if "Decision" in etype:
                    status = e.payload.get("status", "")
                    text = e.payload.get("text", "")[:30]
                    if status == "blocked":
                        lines.append(f"[dim]#{seq}[/] [red bold]Decision BLOCKED[/]")
                        lines.append(f"     [dim]{text}...[/]")
                    else:
                        lines.append(f"[dim]#{seq}[/] [green]Decision committed[/]")
                        lines.append(f"     [dim]{text}...[/]")
                elif "Constraint" in etype:
                    priority = e.payload.get("priority", "")
                    text = e.payload.get("text", "")[:30]
                    if priority == "required":
                        lines.append(f"[dim]#{seq}[/] [red]Constraint added (required)[/]")
                    else:
                        lines.append(f"[dim]#{seq}[/] [yellow]Constraint added[/]")
                    lines.append(f"     [dim]{text}...[/]")
                elif "Fact" in etype:
                    key = e.payload.get("key", "?")
                    value = str(e.payload.get("value", ""))[:20]
                    lines.append(f"[dim]#{seq}[/] [cyan]Fact recorded[/]")
                    lines.append(f"     [dim]{key} = {value}[/]")
                elif "Query" in etype:
                    lines.append(f"[dim]#{seq}[/] [blue]Memory queried[/]")
                elif "Simulate" in etype:
                    lines.append(f"[dim]#{seq}[/] [magenta]Timeline simulated[/]")
                else:
                    lines.append(f"[dim]#{seq} {etype}[/]")
            events_content.update("\n".join(lines))
        else:
            events_content.update("[dim]No events yet[/]")


def main(script_name: str = "japan_trip", auto: bool = False, db_path: str | None = None):
    """Run the demo TUI."""
    app = DemoApp(script_name=script_name, auto_advance=auto, db_path=db_path)
    app.run()


if __name__ == "__main__":
    main()
