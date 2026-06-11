#!/usr/bin/env bash
# Manual installer for model-mix (alternative to /plugin install).
# Copies the skill and agents into ~/.claude and registers the /model-mix trigger
# in ~/.claude/CLAUDE.md. Idempotent — safe to re-run for updates.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"

mkdir -p "$CLAUDE_DIR/skills/model-mix" "$CLAUDE_DIR/agents"

cp "$SRC/skills/model-mix/SKILL.md" "$CLAUDE_DIR/skills/model-mix/SKILL.md"
cp "$SRC/agents/mix-opus-worker.md" \
   "$SRC/agents/mix-sonnet-worker.md" \
   "$SRC/agents/mix-fable-worker.md" \
   "$CLAUDE_DIR/agents/"

CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
if ! grep -q 'skill: "model-mix"' "$CLAUDE_MD" 2>/dev/null; then
  cat >> "$CLAUDE_MD" <<'EOF'
# model-mix
- **model-mix** (`~/.claude/skills/model-mix/SKILL.md`) - tiered orchestration: Opus 4.8 orchestrates; mix-sonnet-worker (Sonnet 4.6) takes routine work; Codex CLI (`codex exec` via Bash) takes cross-vendor second opinions and parallel attempts; mix-fable-worker (Fable 5) is held in reserve for genuinely hard or urgent problems only. Trigger: `/model-mix`
When the user types `/model-mix`, invoke the Skill tool with `skill: "model-mix"` before doing anything else.
EOF
  echo "Registered /model-mix trigger in $CLAUDE_MD"
else
  echo "/model-mix trigger already registered in $CLAUDE_MD"
fi

echo "model-mix installed. Start a new Claude Code session and type /model-mix."
