"""Demo TUI using Textual for proper scrolling and interactivity."""

import os
import subprocess
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, field


# Load .env file if it exists (for WANDB_API_KEY, etc.)
def _load_dotenv():
    """Simple .env loader without external dependency."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

import yaml
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Header, Footer, Markdown, Label, Rule, LoadingIndicator
from textual.reactive import reactive
from textual import work
from rich.markup import escape as rich_escape

from dml.events import EventStore
from dml.replay import ReplayEngine
from dml.tracing import WEAVE_AVAILABLE, init_tracing

# Load .env before checking for WANDB_API_KEY
_load_dotenv()

# Try to import weave client for trace fetching
if WEAVE_AVAILABLE:
    import weave


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
#app-container {
    width: 100%;
    height: 100%;
}

#main-container {
    width: 100%;
    height: 1fr;
}

#left-pane {
    width: 2fr;
}

#right-pane {
    width: 1fr;
    height: 100%;
}

#events-panel.flash {
    background: $warning 30%;
}

/* Weave observability pane - bottom drawer */
#weave-pane {
    height: auto;
    max-height: 40%;
    border-top: heavy $primary;
    background: $surface-darken-1;
    display: none;
}

#weave-pane.visible {
    display: block;
}

#weave-pane-header {
    background: $primary-darken-2;
    padding: 0 1;
    height: 1;
}

#weave-pane-content {
    padding: 1;
    height: auto;
    max-height: 18;
}

#weave-pane.flash {
    border-top: heavy $warning;
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
    height: 2fr;
    border: double $warning;
    background: $warning 8%;
    padding: 1 2;
}

.narrator-title {
    color: $warning;
    text-style: bold;
    background: $warning 20%;
    padding: 0 1;
}

.narrator-text {
    color: $text;
    text-style: bold;
    padding: 1 0;
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

.panel-scroll {
    height: 1fr;
    scrollbar-gutter: stable;
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
        ("enter", "next_step", "Next"),
        ("o", "toggle_observability", "Toggle obs"),
        ("r", "start_recording", "Record"),
        ("ctrl+left", "focus_prev_pane", "Prev pane"),
        ("ctrl+right", "focus_next_pane", "Next pane"),
        ("1", "select_script(1)", "Script 1"),
        ("2", "select_script(2)", "Script 2"),
        ("3", "select_script(3)", "Script 3"),
        ("4", "select_script(4)", "Script 4"),
    ]

    # Reactive state
    current_prompt_index = reactive(0)
    narrator_text = reactive("")
    status_text = reactive("Press ENTER/SPACE to start...")
    is_running = reactive(False)

    def __init__(
        self,
        script_name: str | None = None,
        auto_advance: bool = False,
        db_path: str | None = None,
        debug: bool = False,
    ):
        super().__init__()
        self.script_name = script_name  # None means show selection
        self.auto_advance = auto_advance
        # Check env var if db_path not provided, resolve to absolute path
        raw_path = db_path or os.environ.get("DML_DB_PATH") or str(Path.home() / ".dml" / "memory.db")
        self.db_path = str(Path(raw_path).expanduser().resolve())
        self.debug_mode = debug
        self.debug_log = Path.home() / ".dml" / "demo-debug.log" if debug else None
        self.script = None
        self.prompts = []
        self.demo_started = False
        self.demo_complete = False
        self.script_selected = script_name is not None
        self.available_scripts = []
        # Create unique temp directory for this demo session (enables -c to work)
        import tempfile
        self.session_id = str(uuid.uuid4())
        self.demo_dir = Path(tempfile.gettempdir()) / "dml-demo" / self.session_id
        self.demo_dir.mkdir(parents=True, exist_ok=True)
        if self.debug_log:
            self.debug_log.write_text(f"=== Demo session {self.session_id} ===\n")
            self.debug_log.open("a").write(f"Demo dir: {self.demo_dir}\n")
        # Track event count and timer for flash indicator
        self._last_event_count = 0
        self._flash_timer = None
        # Weave client for trace fetching
        self._weave_client = None
        self._weave_initialized = False
        self._last_trace_count = 0
        self._weave_dashboard_url = (
            os.environ.get("WEAVE_DASHBOARD_URL")
            or os.environ.get("WANDB_DASHBOARD_URL")
            or "https://wandb.ai/daveremy-remzota-labs/dml-mcp-server/weave"
        )
        # Karaoke highlight effect state
        self._typewriter_text: str = ""
        self._typewriter_suffix: str = ""
        self._typewriter_timer = None
        self._highlight_sentences: list[str] = []
        self._highlight_idx: int = 0
        self._highlight_ticks: int = 0
        self._static_suffix: str = ""
        self._intro_menu_text: str = ""
        self._outro_text: str = "Demo complete!"

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header(show_clock=True)

        with Vertical(id="app-container"):
            with Horizontal(id="main-container"):
                # Left pane: chat + narrator (2/3 width)
                with Vertical(id="left-pane"):
                    with Vertical(id="chat-container"):
                        yield Label(" claude ", classes="panel-title")
                        yield VerticalScroll(id="chat-scroll")

                    with Vertical(id="narrator-container"):
                        yield Label(" Narrator ", classes="panel-title narrator-title")
                        yield Static("", id="narrator-content", classes="narrator-text")

                # Right pane: DML state monitor (1/3 width) - always visible
                with VerticalScroll(id="right-pane"):
                    with Vertical(id="facts-panel"):
                        yield Label(" Facts ", classes="panel-title")
                        with VerticalScroll(classes="panel-scroll"):
                            yield Static("(waiting...)", id="facts-content")

                    with Vertical(id="constraints-panel"):
                        yield Label(" Constraints ", classes="panel-title")
                        with VerticalScroll(classes="panel-scroll"):
                            yield Static("(none)", id="constraints-content")

                    with Vertical(id="decisions-panel"):
                        yield Label(" Decisions ", classes="panel-title")
                        with VerticalScroll(classes="panel-scroll"):
                            yield Static("(none)", id="decisions-content")

                    with Vertical(id="events-panel"):
                        yield Label(" Events ", classes="panel-title")
                        with VerticalScroll(classes="panel-scroll"):
                            yield Static("(waiting...)", id="events-content")

            # Weave observability pane - bottom drawer (toggle with 'o')
            with Vertical(id="weave-pane"):
                yield Label(" Observability [dim](Weave provider, press 'o' to hide)[/] ", id="weave-pane-header", classes="panel-title")
                with VerticalScroll(id="weave-pane-content"):
                    yield Static("(initializing...)", id="weave-content")

        yield Static("ENTER/SPACE: proceed  •  Q: quit  •  O: observability  •  Ctrl+←/→: focus pane", id="status-bar")
        yield Footer()

        # Intro overlay (shown on top initially)
        with Vertical(id="intro-overlay"):
            yield Static("", id="intro-title")
            yield Static("", id="intro-content")
            yield Static(">>> Press ENTER/SPACE to start <<<", id="intro-prompt")

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

        # Initialize event count from store to avoid initial flash
        try:
            store = EventStore(self.db_path)
            self._last_event_count = len(store.get_events())
            store.close()
        except Exception:
            pass  # Keep default of 0

        # Initialize Weave for tracing (if available)
        self._initialize_weave()

        # Allow focusing scroll panes for keyboard navigation
        for selector in ("#chat-scroll", "#right-pane", "#weave-pane-content"):
            try:
                self.query_one(selector).can_focus = True
            except Exception:
                pass

        # Start DML state refresh
        self.set_interval(0.5, self.refresh_dml_state)
        # Start Weave trace refresh (separate interval)
        self.set_interval(1.0, self.refresh_weave_traces)

    def _show_script_selection(self) -> None:
        """Show script selection on intro overlay."""
        all_scripts = load_all_scripts()
        intro_title = self.query_one("#intro-title", Static)
        intro_content = self.query_one("#intro-content", Static)
        intro_prompt = self.query_one("#intro-prompt", Static)

        intro_title.update("[bold]Deterministic Memory Layer[/]")

        # Build informational content (highlighted)
        info_lines = [
            "[bold cyan]What is DML?[/]",
            "DML gives AI agents structured, auditable memory. It's an [bold]MCP server[/]",
            "that Claude connects to - a standardized tool interface for memory operations.",
            "",
            "[bold cyan]Event-Driven Memory[/]",
            "Unlike traditional state-based memory (where you only see current values),",
            "DML is [bold]inspired by event sourcing[/]: every change is an immutable event",
            "with a sequence number and source ID. Nothing is overwritten - history is preserved.",
            "",
            "[bold cyan]Observability Integration[/]",
            "Every DML operation is traced via Weave. Press [bold]O[/] during the demo to",
            "see the observability pane. Each trace links back to its source event -",
            "something impossible with traditional memory approaches.",
            "",
            "[bold cyan]This Demo[/]",
            "This is [bold]LIVE[/] - real Claude, real responses. Prompts are scripted but",
            "Claude's responses are not. Watch the right panels update in real-time.",
        ]

        # Build menu content (shown immediately, not highlighted)
        menu_lines = [
            "",
            "[bold]Select a demo:[/]",
            "",
        ]
        for i, (key, script) in enumerate(all_scripts.items(), 1):
            name = script.get("name", key)
            desc = script.get("description", "")
            menu_lines.append(f"  [bold cyan]{i}[/]  [bold]{name}[/]")
            if desc:
                menu_lines.append(f"      {desc}")
            menu_lines.append("")

        # Store menu text to append after highlighting completes
        self._intro_menu_text = "\n".join(menu_lines)

        # Use highlight effect for info section only
        num_scripts = len(all_scripts)
        if num_scripts <= 3:
            prompt_text = "[bold green]>>> Press 1, 2, or 3 to select  •  R to record  •  Q to quit <<<[/]"
        else:
            prompt_text = f"[bold green]>>> Press 1-{num_scripts} to select  •  R to record  •  Q to quit <<<[/]"
        intro_prompt.update("")  # Hide until highlighting completes
        self._start_typewriter(
            "\n".join(info_lines),
            prompt_text,
            target_id="#intro-content",
            words_per_tick=4,
            suffix_target_id="#intro-prompt",
            static_suffix=self._intro_menu_text,  # Menu shown immediately below
        )

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

        # Ensure DB parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Reset DML database (--db must come before subcommand for Click)
        result = subprocess.run(
            ["uv", "run", "dml", "--db", self.db_path, "reset", "--force"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            self.notify(f"Reset failed: {result.stderr}", severity="error")

        # Reset event count after clearing DB
        self._last_event_count = 0

        # Refresh state display to show empty state
        self.refresh_dml_state()

        # Populate intro overlay with typewriter effect
        intro_title = self.query_one("#intro-title", Static)
        intro_prompt = self.query_one("#intro-prompt", Static)

        intro_title.update(f"[bold]{display_name}[/]")
        intro = self.script.get("intro", "").strip()
        intro_text = intro if intro else f"{len(self.prompts)} prompts in this demo."
        intro_prompt.update("")  # Hide until typewriter completes
        self._start_typewriter(
            intro_text,
            "[bold green]>>> Press ENTER/SPACE to start, Q to quit <<<[/]",
            target_id="#intro-content",
            words_per_tick=3,
            suffix_target_id="#intro-prompt",
        )

        # Store outro text for typewriter effect when shown
        self._outro_text = self.script.get("outro", "Demo complete!").strip()

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

    def action_toggle_observability(self) -> None:
        """Toggle the Weave observability pane visible/hidden."""
        pane = self.query_one("#weave-pane", Vertical)
        if pane.has_class("visible"):
            pane.remove_class("visible")
        else:
            pane.add_class("visible")
            # Refresh traces when opening
            self.refresh_weave_traces()

    def action_start_recording(self) -> None:
        """Start recording the demo with asciinema."""
        # Only allow from script selection screen (not during demo)
        if self.demo_started or self.script_selected:
            self.notify("Recording can only be started from the menu", severity="warning")
            return

        # Check if asciinema is available
        import shutil
        if not shutil.which("asciinema"):
            self.notify("asciinema not found. Install with: brew install asciinema", severity="error")
            return

        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        recordings_dir = Path.home() / ".dml" / "recordings"
        recordings_dir.mkdir(parents=True, exist_ok=True)
        output_file = recordings_dir / f"dml_demo_{timestamp}.cast"

        # Exit and relaunch with asciinema
        self.exit(result=("record", str(output_file)))

    def _start_typewriter(
        self,
        text: str,
        suffix: str = "",
        target_id: str = "#narrator-content",
        words_per_tick: int = 2,  # unused, kept for compatibility
        suffix_target_id: str | None = None,
        static_suffix: str = "",  # Text shown immediately below (not highlighted)
    ) -> None:
        """Start karaoke-style highlight effect - shows all text, highlights current sentence.

        Args:
            text: The text to display (will be highlighted sentence by sentence)
            suffix: Text to show after highlighting completes (e.g., "Press ENTER...")
            target_id: CSS selector for the Static widget to update
            words_per_tick: Unused (kept for API compatibility)
            suffix_target_id: If provided, suffix goes to this separate widget instead of appending
            static_suffix: Text shown immediately below highlighted text (not part of highlighting)
        """
        import re

        # Cancel any existing effect
        if self._typewriter_timer:
            self._typewriter_timer.stop()
            self._typewriter_timer = None

        # Store state
        self._typewriter_text = text or ""
        self._typewriter_suffix = suffix
        self._typewriter_target = target_id
        self._typewriter_suffix_target = suffix_target_id
        self._static_suffix = static_suffix

        # Split into sentences (keep delimiters, handle abbreviations loosely)
        # Match sentences ending with .!? followed by space/newline or end
        self._highlight_sentences = []
        if self._typewriter_text:
            # Split on sentence boundaries but keep the structure
            parts = re.split(r'(?<=[.!?])(?=\s|$)', self._typewriter_text)
            self._highlight_sentences = [p for p in parts if p.strip()]

        self._highlight_idx = 0
        self._highlight_ticks = 0  # Ticks spent on current sentence

        if not self._highlight_sentences:
            # No text, just show suffix
            try:
                if suffix_target_id:
                    self.query_one(suffix_target_id, Static).update(suffix)
                else:
                    self.query_one(target_id, Static).update(suffix)
            except Exception:
                pass
            return

        # Show initial state with first sentence highlighted
        self._update_highlight()

        # Start the timer (tick every 150ms)
        self._typewriter_timer = self.set_interval(0.15, self._typewriter_tick)

    def _update_highlight(self) -> None:
        """Update display with current sentence highlighted."""
        if not self._highlight_sentences:
            return

        # Build text with current sentence highlighted
        parts = []
        for i, sentence in enumerate(self._highlight_sentences):
            if i == self._highlight_idx:
                # Highlight current sentence (yellow/bold)
                parts.append(f"[bold yellow]{sentence}[/]")
            else:
                # Dim completed sentences, normal for upcoming
                if i < self._highlight_idx:
                    parts.append(f"[dim]{sentence}[/]")
                else:
                    parts.append(sentence)

        highlighted_text = "".join(parts)

        # Append static suffix (e.g., menu) if present
        if self._static_suffix:
            highlighted_text += self._static_suffix

        try:
            target = self.query_one(self._typewriter_target, Static)
            target.update(highlighted_text)
        except Exception:
            pass

    def _typewriter_tick(self) -> None:
        """Advance the sentence highlight."""
        if self._highlight_idx >= len(self._highlight_sentences):
            # Done - show final text and suffix
            if self._typewriter_timer:
                self._typewriter_timer.stop()
                self._typewriter_timer = None

            try:
                target = self.query_one(self._typewriter_target, Static)
                final_text = self._typewriter_text
                if self._static_suffix:
                    final_text += self._static_suffix
                target.update(final_text)  # Show clean text

                # Show suffix in appropriate location
                if self._typewriter_suffix:
                    if self._typewriter_suffix_target:
                        self.query_one(self._typewriter_suffix_target, Static).update(self._typewriter_suffix)
                    else:
                        target.update(final_text + "\n\n" + self._typewriter_suffix)
            except Exception:
                pass
            return

        # Calculate how long to stay on this sentence based on word count
        current_sentence = self._highlight_sentences[self._highlight_idx]
        word_count = len(current_sentence.split())
        # ~250 words per minute = ~4 words per second = ~0.6 ticks per word at 150ms
        ticks_needed = max(2, int(word_count * 0.6))

        self._highlight_ticks += 1
        if self._highlight_ticks >= ticks_needed:
            # Move to next sentence
            self._highlight_idx += 1
            self._highlight_ticks = 0
            self._update_highlight()

    def _pane_focusables(self) -> list:
        focusables = []
        for selector in ("#chat-scroll", "#right-pane"):
            try:
                focusables.append(self.query_one(selector))
            except Exception:
                pass
        try:
            weave_pane = self.query_one("#weave-pane", Vertical)
            if weave_pane.has_class("visible"):
                focusables.append(self.query_one("#weave-pane-content"))
        except Exception:
            pass
        return focusables

    def action_focus_next_pane(self) -> None:
        focusables = self._pane_focusables()
        if not focusables:
            return
        current = self.focused
        if current in focusables:
            idx = (focusables.index(current) + 1) % len(focusables)
        else:
            idx = 0
        self.set_focus(focusables[idx])

    def action_focus_prev_pane(self) -> None:
        focusables = self._pane_focusables()
        if not focusables:
            return
        current = self.focused
        if current in focusables:
            idx = (focusables.index(current) - 1) % len(focusables)
        else:
            idx = 0
        self.set_focus(focusables[idx])

    def _initialize_weave(self) -> None:
        """Initialize Weave client for trace fetching."""
        if not WEAVE_AVAILABLE:
            return

        # Check if WANDB_API_KEY is set
        if not os.environ.get("WANDB_API_KEY"):
            return

        try:
            # Initialize Weave - use same project as MCP server
            self._weave_client = weave.init("dml-mcp-server")
            self._weave_initialized = True
            self.notify("Weave tracing enabled", severity="information")
        except Exception as e:
            self.notify(f"Weave init failed: {e}", severity="warning")

    @staticmethod
    def _coerce_datetime(value):
        if value is None:
            return None
        if not isinstance(value, datetime):
            return None
        if getattr(value, "tzinfo", None) is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @classmethod
    def _weave_duration_ms(cls, call) -> int | None:
        started = cls._coerce_datetime(getattr(call, "started_at", None))
        ended = cls._coerce_datetime(getattr(call, "ended_at", None))
        if started and ended:
            return int((ended - started).total_seconds() * 1000)
        return None

    @staticmethod
    def _percentile(values: list[int], pct: float) -> int | None:
        if not values:
            return None
        vals = sorted(values)
        if len(vals) == 1:
            return vals[0]
        k = (pct / 100.0) * (len(vals) - 1)
        f = int(k)
        c = min(f + 1, len(vals) - 1)
        if f == c:
            return vals[f]
        d = k - f
        return int(vals[f] + (vals[c] - vals[f]) * d)

    @staticmethod
    def _sparkline(values: list[int], width: int = 20) -> str:
        if not values:
            return ""
        series = values[-width:]
        low = min(series)
        high = max(series)
        chars = " .:-=+*#%@"
        if high == low:
            return chars[len(chars) // 2] * len(series)
        out = []
        for val in series:
            idx = int((val - low) / (high - low) * (len(chars) - 1))
            out.append(chars[idx])
        return "".join(out)

    @classmethod
    def _format_relative_time(cls, value, now) -> str:
        dt = cls._coerce_datetime(value)
        if dt is None:
            return "?"
        delta = now - dt
        seconds = max(0, int(delta.total_seconds()))
        if seconds < 60:
            return f"{seconds}s"
        if seconds < 3600:
            return f"{seconds // 60}m"
        if seconds < 86400:
            return f"{seconds // 3600}h"
        return f"{seconds // 86400}d"

    @staticmethod
    def _weave_category(op_name: str) -> tuple[str, str]:
        op = op_name.lower()
        if "constraint" in op:
            return "Constraints", "red"
        if "decision" in op:
            return "Decisions", "green"
        if "fact" in op:
            return "Facts", "cyan"
        if "event" in op:
            return "Events", "blue"
        return "Other", "magenta"

    @staticmethod
    def _truncate(value: str, limit: int = 36) -> str:
        if len(value) <= limit:
            return value
        return value[: max(0, limit - 3)] + "..."

    @classmethod
    def _event_from_call(cls, call) -> tuple[int | None, str | None, dict | None]:
        inputs = getattr(call, "inputs", None)
        output = getattr(call, "output", None)
        if not isinstance(inputs, dict):
            if isinstance(output, int):
                return output, None, None
            return None, None, None
        event_obj = inputs.get("event")
        if event_obj is None:
            if isinstance(output, int):
                return output, None, None
            return None, None, None
        if isinstance(event_obj, dict):
            seq = event_obj.get("global_seq") or event_obj.get("seq")
            ev_type = event_obj.get("type")
            payload = event_obj.get("payload")
        else:
            seq = getattr(event_obj, "global_seq", None) or getattr(event_obj, "seq", None)
            ev_type = getattr(event_obj, "type", None)
            payload = getattr(event_obj, "payload", None)
        if hasattr(ev_type, "value"):
            ev_type = ev_type.value
        if seq is None and isinstance(output, int):
            seq = output
        if isinstance(payload, dict):
            return seq, str(ev_type) if ev_type is not None else None, payload
        return seq, str(ev_type) if ev_type is not None else None, None

    @staticmethod
    def _event_color(event_type: str | None) -> str:
        if not event_type:
            return "magenta"
        et = event_type.lower()
        if "fact" in et:
            return "cyan"
        if "constraint" in et:
            return "red"
        if "decision" in et:
            return "green"
        if "memorywrite" in et:
            return "yellow"
        return "blue"

    @staticmethod
    def _payload_summary(payload: dict | None, limit_keys: int = 3) -> str:
        if not isinstance(payload, dict) or not payload:
            return ""
        parts = []
        for idx, (key, value) in enumerate(payload.items()):
            if idx >= limit_keys:
                break
            text = str(value).replace("\n", " ")
            if len(text) > 24:
                text = text[:21] + "..."
            parts.append(f"{key}={text}")
        remaining = len(payload) - limit_keys
        if remaining > 0:
            parts.append(f"+{remaining} more")
        return " ".join(parts)

    @classmethod
    def _call_name(cls, call) -> str:
        for attr in ("op_name", "display_name", "name", "op"):
            val = getattr(call, attr, None)
            if hasattr(val, "name"):
                val = getattr(val, "name", None)
            if isinstance(val, str) and val:
                return val
        return "unknown"

    @classmethod
    def _call_label_and_detail(cls, call) -> tuple[str, str | None]:
        name = cls._call_name(call)
        short = name.split(".")[-1] if "." in name else name
        if ":" in short and len(short) > 16:
            short = short.split(":", 1)[0]

        detail = None
        inputs = getattr(call, "inputs", None)
        output = getattr(call, "output", None)
        name_lower = name.lower()
        if "event.append" in name_lower:
            seq = None
            if isinstance(output, int):
                seq = output
            if isinstance(inputs, dict):
                event_obj = inputs.get("event")
                if event_obj is not None:
                    if isinstance(event_obj, dict):
                        if seq is None:
                            seq = event_obj.get("global_seq") or event_obj.get("seq")
                        ev_type = event_obj.get("type")
                        payload = event_obj.get("payload")
                    else:
                        if seq is None:
                            seq = getattr(event_obj, "global_seq", None) or getattr(event_obj, "seq", None)
                        ev_type = getattr(event_obj, "type", None)
                        payload = getattr(event_obj, "payload", None)
                    if hasattr(ev_type, "value"):
                        ev_type = ev_type.value
                    payload_snippet = None
                    if isinstance(payload, dict) and payload:
                        key = next(iter(payload.keys()))
                        payload_snippet = f"{key}={payload.get(key)}"
                    parts = []
                    if seq is not None:
                        parts.append(f"#{seq}")
                    if ev_type:
                        parts.append(str(ev_type))
                    if payload_snippet:
                        parts.append(payload_snippet)
                    if parts:
                        detail = " ".join(parts)

        if isinstance(inputs, dict):
            if "key" in inputs and "value" in inputs:
                detail = f"{inputs.get('key')} = {inputs.get('value')}"
            elif "query" in inputs:
                detail = str(inputs.get("query"))
            elif "items" in inputs and isinstance(inputs.get("items"), list):
                detail = f"{len(inputs.get('items'))} items"
            elif "event" in inputs:
                event = inputs.get("event")
                event_type = getattr(event, "type", None)
                if event_type is not None:
                    detail = str(event_type)
                payload = getattr(event, "payload", None)
                if isinstance(payload, dict) and payload:
                    key = next(iter(payload.keys()))
                    detail = f"{detail + ' ' if detail else ''}{key}={payload.get(key)}"

        if detail is not None:
            detail = cls._truncate(str(detail), 40)

        if short.startswith("dml.memory."):
            short = short.split("dml.memory.", 1)[-1]
        if short.startswith("dml.event."):
            short = short.split("dml.event.", 1)[-1]

        return short, detail

    def refresh_weave_traces(self) -> None:
        """Refresh the Weave observability pane."""
        weave_content = self.query_one("#weave-content", Static)
        weave_pane = self.query_one("#weave-pane", Vertical)

        # If Weave not available or not initialized, show setup instructions
        if not self._weave_initialized or not self._weave_client:
            if WEAVE_AVAILABLE and not os.environ.get("WANDB_API_KEY"):
                weave_content.update(
                    "[bold]Observability[/] [dim](Weave provider)[/]\n"
                    f"[dim]Dashboard:[/] {self._weave_dashboard_url}\n\n"
                    "[dim]Not configured. To enable:[/]\n"
                    "1. Sign up at wandb.ai\n"
                    "2. Get API key from wandb.ai/authorize\n"
                    "3. Set WANDB_API_KEY in .env file"
                )
            elif not WEAVE_AVAILABLE:
                weave_content.update(
                    "[bold]Observability[/] [dim](Weave provider)[/]\n"
                    f"[dim]Dashboard:[/] {self._weave_dashboard_url}\n\n"
                    "[dim]Weave package not installed.[/]"
                )
            else:
                weave_content.update(
                    "[bold]Observability[/] [dim](Weave provider)[/]\n"
                    f"[dim]Dashboard:[/] {self._weave_dashboard_url}\n\n"
                    "[dim]Weave not initialized[/]"
                )
            return

        try:
            # Fetch recent traces from Weave
            calls = list(self._weave_client.get_calls(
                limit=50,
                sort_by=[{"field": "started_at", "direction": "desc"}],
            ))
            # Filter to last 2 minutes for recency (relative to latest call to avoid clock skew)
            now = datetime.now(timezone.utc)
            started_times = [
                self._coerce_datetime(getattr(call, "started_at", None))
                for call in calls
            ]
            started_times = [t for t in started_times if t is not None]
            if started_times:
                latest = max(started_times)
                cutoff = latest - timedelta(seconds=120)
                recent_calls = []
                for call in calls:
                    started = self._coerce_datetime(getattr(call, "started_at", None))
                    if started and started >= cutoff:
                        recent_calls.append(call)
                if recent_calls:
                    calls = recent_calls

            # Flash indicator for new traces
            if len(calls) > self._last_trace_count and weave_pane.has_class("visible"):
                weave_pane.add_class("flash")
                if self._flash_timer:
                    self._flash_timer.stop()

                def clear_flash():
                    weave_pane.remove_class("flash")
                    self._flash_timer = None

                self._flash_timer = self.set_timer(0.3, clear_flash)
            self._last_trace_count = len(calls)

            if calls:
                # now already computed above
                durations = []
                recent_60s = 0
                errors = 0
                for call in calls:
                    duration_ms = self._weave_duration_ms(call)
                    if duration_ms is not None:
                        durations.append(duration_ms)
                    started = self._coerce_datetime(getattr(call, "started_at", None))
                    if started and now - started <= timedelta(seconds=60):
                        recent_60s += 1
                    if getattr(call, "error", None) or getattr(call, "exception", None):
                        errors += 1

                p50 = self._percentile(durations, 50)
                p95 = self._percentile(durations, 95)
                spark = self._sparkline(durations, width=20)

                lines = [
                    "[bold cyan]Observability[/] [dim](Weave calls, last 2 minutes)[/]",
                    f"[dim]Dashboard:[/] {self._weave_dashboard_url}",
                    f"[dim]Updated {now.strftime('%H:%M:%S')}[/]  "
                    f"[bold]Total[/]: {len(calls)}  "
                    f"[bold]1m[/]: {recent_60s}  "
                    f"[bold]Errors[/]: {errors}",
                    f"[bold]Latency[/]: "
                    f"p50 {p50 if p50 is not None else '--'}ms  "
                    f"p95 {p95 if p95 is not None else '--'}ms",
                ]

                if spark:
                    lines.append(f"[dim]Spark[/]: {spark}")
                lines.append("")

                event_calls = []
                other_calls = 0
                for call in calls[:25]:
                    inputs = getattr(call, "inputs", None)
                    if isinstance(inputs, dict) and "event" in inputs:
                        event_calls.append(call)
                    else:
                        other_calls += 1

                lines.append(
                    f"[bold]DML Events (from Weave)[/]: {len(event_calls)}  "
                    f"[dim]Other calls: {other_calls}[/]"
                )

                groups: dict[str, list] = {}
                for call in event_calls:
                    seq, ev_type, payload = self._event_from_call(call)
                    label = ev_type or "Unknown"
                    groups.setdefault(label, []).append((call, seq, payload))

                if not groups:
                    lines.append("[dim]No DML events in recent Weave calls yet.[/]")
                    if calls:
                        lines.append("[dim]Recent Weave calls:[/]")
                        for call in calls[:5]:
                            name = self._call_name(call)
                            inputs = getattr(call, "inputs", None)
                            attrs = getattr(call, "attributes", None)
                            input_keys = []
                            if isinstance(inputs, dict):
                                input_keys = list(inputs.keys())
                            attr_keys = []
                            if isinstance(attrs, dict):
                                attr_keys = list(attrs.keys())
                            name_text = self._truncate(name, 36)
                            keys_text = self._truncate(", ".join(input_keys), 28) if input_keys else "-"
                            attrs_text = self._truncate(", ".join(attr_keys), 28) if attr_keys else "-"
                            lines.append(
                                f"  [dim]{name_text}[/] [dim]inputs:[/] {keys_text} [dim]attrs:[/] {attrs_text}"
                            )
                else:
                    lines.append("")
                    for label in sorted(groups.keys()):
                        color = self._event_color(label)
                        lines.append(f"[bold]{label}[/] [dim]({len(groups[label])})[/]")
                        for call, seq, payload in groups[label][:3]:
                            duration_ms = self._weave_duration_ms(call)
                            started = getattr(call, "started_at", None)
                            rel = self._format_relative_time(started, now)
                            error = getattr(call, "error", None) or getattr(call, "exception", None)
                            status_symbol = "!" if error else "•"
                            status_color = "red" if error else color
                            seq_text = f"#{seq}" if seq is not None else "#?"
                            payload_snippet = None
                            if isinstance(payload, dict) and payload:
                                key = next(iter(payload.keys()))
                                payload_snippet = f"{key}={payload.get(key)}"
                            timing = f"{duration_ms}ms" if duration_ms is not None else "?"
                            if payload_snippet:
                                payload_snippet = self._truncate(str(payload_snippet), 32)
                                lines.append(
                                    f"  [{status_color}]{status_symbol}[/] "
                                    f"[{color}]{seq_text}[/] [dim]{payload_snippet}  {timing} {rel}[/]"
                                )
                            else:
                                lines.append(
                                    f"  [{status_color}]{status_symbol}[/] "
                                    f"[{color}]{seq_text}[/] [dim]{timing} {rel}[/]"
                                )
                        if len(groups[label]) > 3:
                            lines.append(f"  [dim]... +{len(groups[label]) - 3} more[/]")

                weave_content.update("\n".join(lines))
            else:
                weave_content.update("[dim]No Weave traces yet... Run the demo to generate traces.[/]")

        except Exception as e:
            weave_content.update(f"[red]Weave error: {rich_escape(str(e))}[/]")

    def action_quit(self) -> None:
        """Quit the app and clean up temp directory."""
        self._cleanup_demo_dir()
        self.exit()

    def _cleanup_demo_dir(self) -> None:
        """Remove the temp demo directory."""
        import shutil
        if self.demo_dir and self.demo_dir.exists():
            try:
                shutil.rmtree(self.demo_dir)
            except Exception:
                pass  # Best effort cleanup

    def action_next_step(self) -> None:
        """Advance to next step."""
        if self.is_running:
            return  # Already running a prompt

        if self.demo_complete:
            # Return to menu
            self._return_to_menu()
            return

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
            # Show outro overlay with typewriter effect
            self.demo_complete = True
            outro_overlay = self.query_one("#outro-overlay")
            outro_overlay.add_class("visible")
            self._start_typewriter(
                self._outro_text,
                "[bold green]>>> Press ENTER/SPACE to return to menu, Q to quit <<<[/]",
                target_id="#outro-content",
                words_per_tick=3,
            )

    def _return_to_menu(self) -> None:
        """Return to demo selection menu."""
        # Clean up current demo
        self._cleanup_demo_dir()

        # Reset state
        self.demo_started = False
        self.demo_complete = False
        self.script_selected = False
        self.current_prompt_index = 0
        self.script = None
        self.prompts = []

        # Create new demo directory for next run
        import tempfile
        self.session_id = str(uuid.uuid4())
        self.demo_dir = Path(tempfile.gettempdir()) / "dml-demo" / self.session_id
        self.demo_dir.mkdir(parents=True, exist_ok=True)

        # Hide outro, show intro with menu
        outro_overlay = self.query_one("#outro-overlay")
        outro_overlay.remove_class("visible")

        intro_overlay = self.query_one("#intro-overlay")
        intro_overlay.remove_class("hidden")

        # Clear chat
        chat_scroll = self.query_one("#chat-scroll", VerticalScroll)
        chat_scroll.remove_children()

        # Show selection menu
        self._show_script_selection()

    def reset_demo(self) -> None:
        """Reset DML database for fresh demo."""
        # Ensure DB parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Reset DML database (--db must come before subcommand for Click)
        result = subprocess.run(
            ["uv", "run", "dml", "--db", self.db_path, "reset", "--force"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            self.notify(f"Reset failed: {result.stderr}", severity="error")
        # Reset event count after clearing DB
        self._last_event_count = 0
        # Clear chat
        chat_scroll = self.query_one("#chat-scroll")
        chat_scroll.remove_children()
        # Refresh state display to show empty state
        self.refresh_dml_state()

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

        # Show context in narrator before sending (with karaoke effect)
        if context_text:
            self._start_typewriter(
                context_text,
                "[dim italic]Waiting for Claude...[/]",
                target_id="#narrator-content",
            )
        else:
            narrator.update(f"[dim]Sending prompt {self.current_prompt_index + 1}...[/]")

        status_bar.update(
            f"[{self.current_prompt_index + 1}/{len(self.prompts)}] Sending to Claude... "
            "[dim](ENTER/SPACE to proceed, Q to quit, O for observability)[/]"
        )

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

        # Note: context text karaoke already shows "Waiting for Claude..." as suffix
        # For no-context case, just show waiting
        if not context_text:
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
            status_bar.update("[bold]Demo complete![/] Press ENTER/SPACE to see summary, Q to quit.")
            if final_narrator:
                self._start_typewriter(final_narrator, "[bold green]>>> Press ENTER/SPACE for summary <<<[/]")
            else:
                self._start_typewriter("[bold]Demo complete![/]", "[bold green]>>> Press ENTER/SPACE for summary <<<[/]")
        else:
            # Update narrator with commentary using typewriter effect
            if self.auto_advance:
                suffix = "[dim]Auto-advancing in 5 seconds...[/]"
                self._start_typewriter(final_narrator or "", suffix)
                status_bar.update(
                    f"[{self.current_prompt_index}/{len(self.prompts)}] Auto-advancing... "
                    "[dim](Q to quit)[/]"
                )
            else:
                suffix = "[bold green]>>> Press ENTER/SPACE to continue <<<[/]"
                self._start_typewriter(final_narrator or "", suffix)
                status_bar.update(
                    f"[{self.current_prompt_index}/{len(self.prompts)}] Press ENTER/SPACE to continue, Q to quit"
                )

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
            # Check if any new events were recorded (covers both new facts and updates)
            if after["last_seq"] <= before["last_seq"]:
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
        """Run claude -p command asynchronously in a temp directory."""
        # Prepend /dml to invoke the DML skill
        # Normalize whitespace (prompts from YAML may have internal newlines)
        clean_prompt = " ".join(prompt.split())
        dml_prompt = f"/dml {clean_prompt}"
        cmd = [
            "claude", "-p", dml_prompt,
            "--dangerously-skip-permissions",  # Allow tool use without prompts
        ]
        if continue_session:
            cmd.append("-c")  # Continue most recent conversation in demo_dir

        # Debug logging
        if self.debug_log:
            import shlex
            with open(self.debug_log, "a") as f:
                f.write(f"\n--- Command (cwd: {self.demo_dir}) ---\n{shlex.join(cmd)}\n")

        # Pass DML_DB_PATH so Claude's MCP server uses same database
        env = os.environ.copy()
        env["DML_DB_PATH"] = self.db_path

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.demo_dir),
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            response = stdout.decode().strip()

            # Debug logging
            if self.debug_log:
                with open(self.debug_log, "a") as f:
                    f.write(f"\n--- Response ---\n{response}\n")
                    if stderr:
                        f.write(f"\n--- Stderr ---\n{stderr.decode()}\n")

            return response
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

        # Update Events panel - always show DML events
        events_content = self.query_one("#events-content", Static)
        events_panel = self.query_one("#events-panel", Vertical)

        # Flash indicator for new events
        if len(events) > self._last_event_count:
            events_panel.add_class("flash")
            # Cancel previous timer to avoid race conditions
            if self._flash_timer:
                self._flash_timer.stop()

            def clear_flash():
                events_panel.remove_class("flash")
                self._flash_timer = None

            self._flash_timer = self.set_timer(0.3, clear_flash)
        self._last_event_count = len(events)

        if events:
            lines = []
            # Show recent events, newest first (scrollable)
            for e in reversed(events[-50:]):
                seq = e.global_seq
                etype = e.type.value
                color = self._event_color(etype)
                turn_info = f" [magenta]T{e.turn_id}[/]" if e.turn_id is not None else ""
                seq_prefix = f"[dim]#{seq}[/]{turn_info}"

                label = etype
                if "Decision" in etype:
                    status = e.payload.get("status", "")
                    if status:
                        label = f"{etype} ({status})"
                elif "Constraint" in etype:
                    priority = e.payload.get("priority", "")
                    if priority:
                        label = f"{etype} ({priority})"

                lines.append(f"{seq_prefix} [{color}]{label}[/]")

                details = []
                payload_summary = self._payload_summary(e.payload)
                if payload_summary:
                    details.append(payload_summary)
                if e.caused_by is not None:
                    details.append(f"by #{e.caused_by}")
                if e.correlation_id:
                    details.append(f"corr {str(e.correlation_id)[:8]}")
                if details:
                    lines.append(f"     [dim]{' | '.join(details)}[/]")
            events_content.update("\n".join(lines))
        else:
            events_content.update("[dim]No events yet[/]")


def main(script_name: str | None = None, auto: bool = False, db_path: str | None = None, debug: bool = False, recording: bool = False):
    """Run the demo TUI."""
    # If already recording, just run the app
    if recording or os.environ.get("DML_RECORDING"):
        app = DemoApp(script_name=script_name, auto_advance=auto, db_path=db_path, debug=debug)
        app.run()
        if debug:
            print(f"\nDebug log written to: ~/.dml/demo-debug.log")
        return

    # Normal run - check if user wants to record
    app = DemoApp(script_name=script_name, auto_advance=auto, db_path=db_path, debug=debug)
    result = app.run()

    # Handle recording request
    if isinstance(result, tuple) and result[0] == "record":
        output_file = result[1]
        print(f"\n🎬 Starting recording to: {output_file}")
        print("Press Ctrl+D or type 'exit' when done to stop recording.\n")

        # Build command to relaunch inside asciinema
        import sys
        cmd = [
            "asciinema", "rec",
            "--stdin",  # Record stdin for interactive feel
            "-c", f"DML_RECORDING=1 uv run dml live",
            output_file
        ]

        try:
            subprocess.run(cmd, check=True)
            print(f"\n✅ Recording saved to: {output_file}")
            print(f"   Upload with: asciinema upload {output_file}")
            print(f"   Play with:   asciinema play {output_file}")
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Recording failed: {e}")
        except KeyboardInterrupt:
            print(f"\n⏹️  Recording stopped. File saved to: {output_file}")

    elif debug:
        print(f"\nDebug log written to: ~/.dml/demo-debug.log")


if __name__ == "__main__":
    main()
