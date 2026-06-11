# model-mix

Tiered model orchestration for Claude Code. One command turns your session into a
cost/capability-routed setup:

| Tier | Model | Role |
|---|---|---|
| Orchestrator | Claude Opus 4.8 (your session model) | decomposes work, design, review, integration |
| `mix-sonnet-worker` | Claude Sonnet 4.6 | routine work: searches, boilerplate, single-file edits, running tests |
| Codex CLI | OpenAI Codex (`codex exec` via Bash) | cross-vendor second opinions, code review, parallel implementation races |
| `mix-opus-worker` | Claude Opus 4.8 | parallel implementation capacity |
| `mix-fable-worker` | Claude Fable 5 | **reserved** — escalated to only when cheaper tiers failed, the stakes are high/urgent, or you ask for it |

The point: spare the most capable (most expensive) model from everyday work so it's available —
and affordable — when something is genuinely hard. Built-in guardrails: a briefing threshold so
small tasks aren't taxed with delegation overhead, mechanical verification of worker output
(tests > judgment), a two-bounce escalation tripwire, and a `heavy` mode that flips Fable into
the orchestrator seat for long autonomous builds (where orchestration is its actual strength).

## Install

### As a plugin (recommended)

```
/plugin marketplace add <this-repo-url-or-local-path>
/plugin install model-mix
```

Note: installed as a plugin, the agents are namespaced — `model-mix:mix-opus-worker`,
`model-mix:mix-sonnet-worker`, `model-mix:mix-fable-worker` — and the skill is invoked as
`/model-mix:model-mix` (or auto-triggers from its description).

### Manual (un-namespaced, plain `/model-mix`)

```bash
./install.sh
```

Copies the skill to `~/.claude/skills/model-mix/`, the three agents to `~/.claude/agents/`, and
registers the `/model-mix` trigger in `~/.claude/CLAUDE.md`. Idempotent; re-run to update.

## Usage

```
/model-mix              # activate tiered orchestration for the rest of the session
/model-mix <task>       # activate and immediately decompose + route <task>
/model-mix heavy        # long autonomous build: Fable 5 orchestrates, cheap tiers execute
```

Run your session on **Opus 4.8** (`/model`) for the default mode. The Codex tier requires the
[Codex CLI](https://github.com/openai/codex) installed and logged in (`codex login`); without it
the cross-vendor row is simply skipped.

## Requirements

- Claude Code with access to Fable 5, Opus 4.8, and Sonnet 4.6
- Optional: Codex CLI on PATH for the cross-vendor tier
