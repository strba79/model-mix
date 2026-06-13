#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"

# ---------------------------------------------------------------------------
# a. Syntax checks
# ---------------------------------------------------------------------------
bash -n "$REPO/install.sh"
python3 -m py_compile "$REPO/scripts/stats.py"
echo "PASS: syntax checks"

# ---------------------------------------------------------------------------
# b. Fresh install
# ---------------------------------------------------------------------------
CLAUDE_DIR=$(mktemp -d)
CLAUDE_DIR="$CLAUDE_DIR" bash "$REPO/install.sh"

for f in \
  skills/model-mix/SKILL.md \
  skills/model-mix/scripts/stats.py \
  agents/mix-opus-worker.md \
  agents/mix-sonnet-worker.md \
  CLAUDE.md
do
  if [[ ! -f "$CLAUDE_DIR/$f" ]]; then
    echo "FAIL: expected file missing: $CLAUDE_DIR/$f"
    exit 1
  fi
done

if ! grep -q 'skill: "model-mix"' "$CLAUDE_DIR/CLAUDE.md"; then
  echo 'FAIL: CLAUDE.md does not contain skill: "model-mix"'
  exit 1
fi
echo "PASS: fresh install"

# ---------------------------------------------------------------------------
# c. Idempotency
# ---------------------------------------------------------------------------
out=$(CLAUDE_DIR="$CLAUDE_DIR" bash "$REPO/install.sh" 2>&1)
if ! echo "$out" | grep -q "already registered"; then
  echo "FAIL: idempotency — expected 'already registered' in output"
  echo "Output was: $out"
  exit 1
fi
echo "PASS: idempotency"

# ---------------------------------------------------------------------------
# d. Plugin-form guard
# ---------------------------------------------------------------------------
CLAUDE_DIR2=$(mktemp -d)
mkdir -p "$CLAUDE_DIR2"
cat > "$CLAUDE_DIR2/CLAUDE.md" <<'HEREDOC'
# model-mix
When the user types /model-mix, invoke the Skill tool with `skill: "model-mix:model-mix"` before doing anything else.
HEREDOC

CLAUDE_DIR="$CLAUDE_DIR2" bash "$REPO/install.sh"

count=$(grep -c 'model-mix' "$CLAUDE_DIR2/CLAUDE.md" || true)
# We only care that there is exactly one line mentioning the trigger pattern
trigger_count=$(grep -cE 'skill: "model-mix(:model-mix)?"' "$CLAUDE_DIR2/CLAUDE.md" || true)
if [[ "$trigger_count" -ne 1 ]]; then
  echo "FAIL: plugin-form guard — expected exactly 1 trigger mention, got $trigger_count"
  cat "$CLAUDE_DIR2/CLAUDE.md"
  exit 1
fi
echo "PASS: plugin-form guard"

# ---------------------------------------------------------------------------
# e. stats.py correctness on fixture
# ---------------------------------------------------------------------------
fixture="$REPO/tests/fixtures/session.jsonl"
output=$(python3 "$REPO/scripts/stats.py" --file "$fixture" 2>&1)

# Sonnet row: 2 reqs, input 107 (100 deduped + 7 no-id)
if ! echo "$output" | grep -qE 'sonnet[^ ]*[[:space:]]+2[[:space:]]+107'; then
  echo "FAIL: stats.py — expected sonnet row with 2 reqs and 107 input tokens"
  echo "Output:"
  echo "$output"
  exit 1
fi

# Haiku row present in table
if ! echo "$output" | grep -q "haiku"; then
  echo "FAIL: stats.py — expected haiku row in output"
  echo "Output:"
  echo "$output"
  exit 1
fi

# Counterfactual line contains haiku exclusion note
if ! echo "$output" | grep -q "haiku background calls excluded"; then
  echo "FAIL: stats.py — expected 'haiku background calls excluded' in counterfactual line"
  echo "Output:"
  echo "$output"
  exit 1
fi
echo "PASS: stats.py fixture correctness"

# ---------------------------------------------------------------------------
echo ""
echo "ALL TESTS PASSED"
