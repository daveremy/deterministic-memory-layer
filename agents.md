# Headless AI Assistant Guide

Documentation for calling CLI AI assistants programmatically from DML.

## Use Cases in DML

- Cross-validate memory decisions with multiple models
- Run eval scenarios across different agents
- Automated testing of agent behavior with memory layer
- Multi-model consensus on constraint interpretations

## Claude Code

Anthropic's CLI for Claude.

### Headless Execution

```bash
# Basic prompt (non-interactive)
claude -p "prompt"

# Pipe input
cat file.txt | claude -p "analyze this"

# Specify model
claude -p --model sonnet "prompt"
claude -p --model opus "prompt"
claude -p --model haiku "prompt"

# With working directory context
claude -p "explain this codebase" --cwd /path/to/project
```

### Example: Validate Memory Decision

```bash
# Ask Claude to validate a proposed memory write
claude -p "Given constraint 'Never use eval()', should this decision be allowed: 'Use eval() for dynamic parsing'? Answer YES or NO with brief reason."
```

## Codex CLI

OpenAI's CLI for code tasks.

### Headless Execution

```bash
# Basic execution
codex exec "prompt"

# Specify model
codex exec "prompt" --model o3
codex exec "prompt" --model gpt-4

# Pipe input
cat file.txt | codex exec "analyze this"
```

### Example: Cross-Validate Decision

```bash
# Get second opinion on memory decision
codex exec "Constraint: 'Never use eval()'. Proposed: 'Use json.loads() for parsing'. Is this compliant? YES/NO"
```

## Gemini CLI

Google's CLI with large context window.

### Headless Execution

```bash
# Basic prompt (positional argument)
gemini "prompt"

# Pipe input
cat file.txt | gemini "analyze this"

# Include specific files
gemini "@file.txt @dir/ analyze these"

# Include all project files
gemini --all_files "analyze entire project"

# Multiple file references
gemini "@src/ @tests/ @README.md explain this project"
```

### Example: Analyze Memory State

```bash
# Use large context to analyze full event history
gemini "@memory.db analyze all events and identify potential constraint conflicts"
```

## Multi-Agent Validation Pattern

Use multiple agents to validate critical memory operations:

```bash
#!/bin/bash
# validate_decision.sh - Get consensus from multiple models

CONSTRAINT="Never use eval()"
DECISION="Use json.loads() for safe parsing"
PROMPT="Constraint: '$CONSTRAINT'. Decision: '$DECISION'. Is this compliant? Answer only YES or NO."

# Query each model
CLAUDE=$(claude -p "$PROMPT" 2>/dev/null | tail -1)
CODEX=$(codex exec "$PROMPT" 2>/dev/null | tail -1)
GEMINI=$(gemini "$PROMPT" 2>/dev/null | tail -1)

echo "Claude: $CLAUDE"
echo "Codex: $CODEX"
echo "Gemini: $GEMINI"

# Check consensus
if [[ "$CLAUDE" == "YES" && "$CODEX" == "YES" && "$GEMINI" == "YES" ]]; then
    echo "CONSENSUS: APPROVED"
elif [[ "$CLAUDE" == "NO" && "$CODEX" == "NO" && "$GEMINI" == "NO" ]]; then
    echo "CONSENSUS: REJECTED"
else
    echo "CONSENSUS: SPLIT - requires human review"
fi
```

## Integration with DML Eval

```bash
# Run DML eval with multi-model validation
python cli.py eval

# Pipe eval results to an agent for analysis
python cli.py replay | claude -p "Analyze this memory state for potential issues"

# Use Gemini for large history analysis
python cli.py replay | gemini "Identify patterns and anomalies in this event history"
```

## Best Practices

1. **Use non-interactive flags** (`-p` for Claude, `exec` for Codex)
2. **Keep prompts focused** - single question, clear expected output
3. **Parse output programmatically** - expect YES/NO or structured responses
4. **Handle failures gracefully** - agents may timeout or refuse
5. **Log all responses** - for audit trail and debugging

## Environment Setup

```bash
# Claude Code
# Install: npm install -g @anthropic-ai/claude-code
# Auth: claude login

# Codex CLI
# Install: pip install openai-codex
# Auth: export OPENAI_API_KEY=...

# Gemini CLI
# Install: pip install google-generativeai
# Auth: export GOOGLE_API_KEY=...
```
