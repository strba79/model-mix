# model-mix

Tiered model orchestration for Claude Code. One command turns your session into a
cost/capability-routed setup: a mid-tier model runs the show, cheap models do the routine work,
and the most capable (most expensive) model is **held in reserve** for the moments that actually
need it.

| Tier | Model | Role |
|---|---|---|
| Orchestrator | Claude Opus 4.8 (your session model) | decomposes work, design, review, integration |
| `mix-sonnet-worker` | Claude Sonnet 4.6 | routine work: searches, boilerplate, single-file edits, running tests |
| Codex CLI | OpenAI Codex (`codex exec` via Bash) | cross-vendor second opinions, code review, parallel implementation races |
| `mix-opus-worker` | Claude Opus 4.8 | parallel implementation capacity |
| `mix-fable-worker` | Claude Fable 5 | **reserved** — escalated to only when cheaper tiers failed, the stakes are high/urgent, or you ask for it |

Why: Fable 5 costs 2× Opus per token and its tokenizer produces ~30% more tokens for the same
content — an all-Fable working day costs roughly 2.5× an Opus one. Most of that day doesn't need
Fable. model-mix keeps the premium for the minutes that do.

## Install

### As a plugin (recommended)

```
/plugin marketplace add strba79/model-mix     # or a local path to this repo
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

### Requirements

- Claude Code with access to Fable 5, Opus 4.8, and Sonnet 4.6
- Optional: [Codex CLI](https://github.com/openai/codex) on PATH and logged in (`codex login`)
  for the cross-vendor tier — without it that row is simply skipped

## How to best use it

### 1. Set the session model once

Run `/model` and pick **Opus 4.8**. The orchestrator can't switch its own model, and the whole
design assumes the session itself is the mid-tier. If the session is on Fable, `/model-mix` will
warn you.

### 2. Activate and just work

```
/model-mix              # activate tiered orchestration for the rest of the session
/model-mix <task>       # activate and immediately decompose + route <task>
/model-mix heavy        # long autonomous build: Fable 5 orchestrates, cheap tiers execute
/model-mix stats        # per-tier token/cost report + savings vs all-Fable counterfactual
```

After activation you don't manage the routing — you give normal instructions and the
orchestrator routes. What that looks like in practice:

| You say | What happens |
|---|---|
| "find every place we read `AUTH_TOKEN` and rename it to `SESSION_TOKEN`" | sonnet worker does the search + mechanical rename, orchestrator spot-checks the diff |
| "add CSV export to the reports page" | orchestrator designs the approach, delegates the implementation, runs the tests via a sonnet worker |
| "refactor the payment module while I keep working with you on the API design" | opus worker takes the refactor in the background; orchestrator stays with you on the design |
| "have codex review this diff" / "race codex on this" | `codex exec` runs read-only review, or both vendors implement the same scoped task in separate worktrees and the orchestrator picks |
| "this is urgent — prod is double-charging customers" | "urgent" satisfies the escalation gate → Fable gets the problem with all gathered evidence |
| "use fable for this" | explicit request — gate satisfied, no questions |

### 3. The bits worth knowing

- **Workers are a warm pool, not per-task hires.** The first routine task spawns a sonnet worker;
  later tasks are routed to that same worker (it keeps everything it learned — files read,
  conventions, prior fixes), so follow-ups cost a fraction of a cold spawn. Workers are retired
  when their context goes stale or they drift. Fable is the exception: never kept warm, spawned
  per escalation only.
- **Small things are done directly.** The skill has a briefing threshold: if delegating costs
  more than doing (quick reads, one-file tweaks), the orchestrator just does it. Don't be
  surprised when no worker spawns for small asks — that's the overhead guard working.
- **Fable doesn't fire just because something is "complex."** The gate requires one of: a cheaper
  tier already failed at it, high/urgent stakes, or your explicit request. If a task bounces
  twice without getting fixed, that history auto-satisfies the gate.
- **Worker output gets verified, not trusted.** Tests/build/typecheck arbitrate where they can;
  load-bearing claims that tests can't check (root causes, design claims, security changes) get
  one cheap independent check (read-only Codex pass or a fresh sonnet verifier) before
  integration.
- **Give intent, not just instructions.** "I'm adding billing for the EU launch next week — add
  VAT handling to checkout" routes and scopes better than "add VAT handling," because the
  orchestrator can judge stakes (and stakes feed the escalation gate).
- **Long autonomous run? Use heavy mode.** For multi-hour builds and migrations, `/model-mix
  heavy` flips Fable into the orchestrator seat — orchestration is its actual strength — while
  execution still flows down to the cheap tiers. Switch back to default when the big task is
  done.

### 4. Measure what you saved

```bash
python3 scripts/stats.py             # most recent session of the current project
python3 scripts/stats.py --project   # all sessions of the current project
python3 scripts/stats.py --all --days 7   # everything, last week
```

The script parses the transcripts Claude Code already writes under `~/.claude/projects/`,
aggregates tokens per model (subagent runs included), prices them at current API rates, and
prints the estimated cost had the same work run entirely on Fable 5 (including its ~30%
tokenizer overhead) — i.e. your savings number. Codex usage is billed by OpenAI and not
included.

## Anti-patterns

- **Don't run the session on Sonnet to save more.** The orchestrator's judgment *is* the
  product — decomposition, routing, and review quality degrade below Opus, and bad routing costs
  more than it saves.
- **Don't pre-route yourself** ("use the sonnet worker to design the architecture"). State the
  task and the stakes; override routing only when you have a reason the policy can't see.
- **Don't soften the Fable gate** ("escalate whenever unsure"). Defensive escalation is exactly
  the cost leak this setup exists to close.

## How it works

- `skills/model-mix/SKILL.md` — the orchestration policy: routing table, escalation gate,
  briefing threshold, verification rules, modes
- `agents/mix-*-worker.md` — Claude Code agent definitions with the model pinned in frontmatter
  (`model: sonnet|opus|fable`); workers get tightly scoped briefs and report tersely
- `scripts/stats.py` — transcript-based per-tier cost reporting
- `.claude-plugin/` — plugin + marketplace manifests, so the repo installs directly via `/plugin`

## License

MIT
