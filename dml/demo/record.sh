#!/bin/bash
# DML Demo Recording Script
# Uses claude -p (prompt) and -c (continue) for deterministic scripting
# Run inside tmux for best visual effect

set -e

cd "$(dirname "$0")/.."  # Go to project root

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
WAIT_BETWEEN=2  # seconds between prompts

echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       DML Demo Recording Script        ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo

# Check if we're in tmux
if [ -z "$TMUX" ]; then
    echo -e "${RED}Not in tmux. Starting tmux session with monitor...${NC}"

    # Reset first
    uv run dml reset --force

    # Kill existing session if any
    tmux kill-session -t dml-demo 2>/dev/null || true

    # Create tmux session (don't specify window, let tmux use default)
    tmux new-session -d -s dml-demo -x 200 -y 50

    # Split horizontally and start monitor in right pane
    tmux split-window -h -t dml-demo "uv run dml monitor"

    # Send script command to left pane (pane 0 of the active window)
    tmux send-keys -t dml-demo.0 "sleep 1 && $0" Enter

    # Focus left pane
    tmux select-pane -t dml-demo.0

    # Attach
    tmux attach -t dml-demo
    exit 0
fi

# We're inside tmux - just reset and run
echo -e "${YELLOW}Resetting DML database...${NC}"
uv run dml reset --force
sleep 1
echo

prompt() {
    local num=$1
    local text=$2
    local continue_flag=""

    if [ "$num" -gt 1 ]; then
        continue_flag="-c"
    fi

    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Prompt $num:${NC} $text"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    # -p: print mode (non-interactive)
    # -c: continue most recent conversation
    # --allowedTools: only allow DML MCP tools
    claude -p "$text" $continue_flag --allowedTools "mcp__dml__*"

    echo
    sleep $WAIT_BETWEEN
}

# Act 1: Setup
prompt 1 "Record these trip facts now: destination Japan, budget \$4000, dates spring 2026, origin Tucson, interest traditional Japanese culture. Don't ask questions, just record them."

prompt 2 "Recommend a traditional ryokan and record a decision to book it. Topic: accommodation."

# Act 2: The Twist
prompt 3 "Add a required constraint: all accommodations must be wheelchair accessible. My mom uses a wheelchair."

# Act 3: The Block
prompt 4 "Record a decision to confirm the Ryokan Kurashiki booking now. Topic: accommodation."

# Act 4: Recovery
prompt 5 "Query your memory for my constraints, then recommend an accessible alternative hotel."

prompt 6 "Record a decision to book the accessible onsen hotel. Topic: accommodation."

# Act 5: Time Travel
prompt 7 "Use simulate_timeline to test: if the wheelchair constraint existed from event 1, would the ryokan booking have been blocked?"

echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║          Demo Complete!                ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo
echo -e "${YELLOW}Press any key to exit...${NC}"
read -n 1
