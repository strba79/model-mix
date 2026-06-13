# model-mix

Tiered model orchestration for Claude Code. One command turns your session into a
cost/capability-routed setup: a capable model runs the show and handles the hard problems, cheap
models do the routine work, and a different model family is on call for when the orchestrator
gets stuck.

| Tier | Model | Role |
|---|---|---|
| Orchestrator | Claude Opus 4.8 (your session model) | decomposes work, design, review, integration, and the genuinely hard problems |
| `mix-sonnet-worker` | Claude Sonnet 4.6 | routine work: searches, boilerplate, single-file edits, running tests |
| Codex CLI | OpenAI Codex (`codex exec` via Bash) | cross-vendor second opinions, code review, parallel implementation races, and the escalation valve when Opus is stuck |
| `mix-opus-worker` | Claude Opus 4.8 | parallel implementation capacity |

Why: most of a working day is routine — searches, renames, boilerplate, running tests — that
doesn't need the orchestrator's judgment. Opus per-token costs ~1.7× Sonnet; routing that routine
work down to Sonnet keeps the Opus premium for the decomposition, design, and review where it
actually earns its keep. Opus is the ceiling here, so when it gets stuck the answer is a *different
model family* (Codex), not a more expensive Claude.

## Install

### As a plugin (recommended)

```
/plugin marketplace add strba79/model-mix     # or a local path to this repo
/plugin install model-mix
```

Note: installed as a plugin, the agents are namespaced — `model-mix:mix-opus-worker`,
`model-mix:mix-sonnet-worker` — and the skill is invoked as `/model-mix:model-mix` (or
auto-triggers from its description).

### Manual (un-namespaced, plain `/model-mix`)

```bash
./install.sh
```

Copies the skill to `~/.claude/skills/model-mix/`, the two agents to `~/.claude/agents/`, and
registers the `/model-mix` trigger in `~/.claude/CLAUDE.md`. Idempotent; re-run to update.

### Requirements

- Claude Code with access to Opus 4.8 and Sonnet 4.6
- Optional: [Codex CLI](https://github.com/openai/codex) on PATH and logged in (`codex login`)
  for the cross-vendor tier — without it that row is simply skipped

## How to best use it

### 1. Set the session model once

Run `/model` and pick **Opus 4.8**. The orchestrator can't switch its own model, and the whole
design assumes the session itself is the capable tier. If the session is on a cheaper model,
`/model-mix` will recommend switching.

### 2. Activate and just work

```
/model-mix              # activate tiered orchestration for the rest of the session
/model-mix <task>       # activate and immediately decompose + route <task>
/model-mix stats        # per-tier token/cost report + savings vs all-Opus counterfactual
```

After activation you don't manage the routing — you give normal instructions and the
orchestrator routes. What that looks like in practice:

| You say | What happens |
|---|---|
| "find every place we read `AUTH_TOKEN` and rename it to `SESSION_TOKEN`" | sonnet worker does the search + mechanical rename, orchestrator spot-checks the diff |
| "add CSV export to the reports page" | orchestrator designs the approach, delegates the implementation, runs the tests via a sonnet worker |
| "refactor the payment module while I keep working with you on the API design" | opus worker takes the refactor in the background; orchestrator stays with you on the design |
| "have codex review this diff" / "race codex on this" | `codex exec` runs read-only review, or both vendors implement the same scoped task in separate worktrees and the orchestrator picks |
| "we've tried this three ways and it's still broken" | Opus is stuck → the problem goes to Codex (a different model family) with the full failure history, or a fresh independent opus run, instead of a fourth identical retry |
| "this is urgent — prod is double-charging customers" | high/immediate stakes → the orchestrator solves it directly and cross-checks the fix with a read-only Codex pass before shipping |

### 3. The bits worth knowing

- **Workers are a warm pool, not per-task hires.** The first routine task spawns a sonnet worker;
  later tasks are routed to that same worker (it keeps everything it learned — files read,
  conventions, prior fixes), so follow-ups cost a fraction of a cold spawn. Workers are retired
  when their context goes stale or they drift.
- **Small things are done directly.** The skill has a briefing threshold: if delegating costs
  more than doing (quick reads, one-file tweaks), the orchestrator just does it. Don't be
  surprised when no worker spawns for small asks — that's the overhead guard working.
- **Stuck means change approach, not retry.** Opus is the top Claude tier here. When the
  orchestrator (or an opus worker) has genuinely tried and is wrong/stuck/circling, the next move
  is a *different model family* — the problem goes to Codex with the full failure history, or a
  fresh independent opus run — not a third identical attempt. A task that bounces twice trips this
  automatically.
- **Worker output gets verified, not trusted.** Tests/build/typecheck arbitrate where they can;
  load-bearing claims that tests can't check (root causes, design claims, security changes) get
  one cheap independent check (read-only Codex pass or a fresh sonnet verifier) before
  integration.
- **Give intent, not just instructions.** "I'm adding billing for the EU launch next week — add
  VAT handling to checkout" routes and scopes better than "add VAT handling," because the
  orchestrator can judge stakes (and high stakes mean it cross-checks the result before shipping).

### 4. Measure what you saved

```bash
python3 scripts/stats.py             # most recent session of the current project
python3 scripts/stats.py --project   # all sessions of the current project
python3 scripts/stats.py --all --days 7   # everything, last week
```

The script parses the transcripts Claude Code already writes under `~/.claude/projects/`,
aggregates tokens per model (subagent runs included), prices them at current API rates, and
prints the estimated cost had the same work run entirely on Opus 4.8 — i.e. your savings from
routing routine work down to Sonnet. Codex usage is billed by OpenAI and not included.

## Anti-patterns

- **Don't run the session on Sonnet to save more.** The orchestrator's judgment *is* the
  product — decomposition, routing, and review quality degrade below Opus, and bad routing costs
  more than it saves.
- **Don't pre-route yourself** ("use the sonnet worker to design the architecture"). State the
  task and the stakes; override routing only when you have a reason the policy can't see.
- **Don't reach for Codex on every "complex" task.** A different model family is for breaking a
  genuine Opus deadlock or a cross-vendor cross-check — not a reflex for anything that looks hard.
  Merely-complex work is the orchestrator's job.

## How it works

- `skills/model-mix/SKILL.md` — the orchestration policy: routing table, escalation gate,
  briefing threshold, verification rules, modes
- `agents/mix-*-worker.md` — Claude Code agent definitions with the model pinned in frontmatter
  (`model: sonnet|opus`); workers get tightly scoped briefs and report tersely
- `scripts/stats.py` — transcript-based per-tier cost reporting
- `.claude-plugin/` — plugin + marketplace manifests, so the repo installs directly via `/plugin`

## License

MIT
