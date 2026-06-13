---
name: model-mix
description: "Turn the session into a tiered orchestrator: Opus 4.8 orchestrates, handles design, and takes the hard problems; Sonnet 4.6 takes routine work; Codex CLI takes cross-vendor work and is the escalation valve when Opus is stuck. Trigger: /model-mix"
trigger: /model-mix
---

# /model-mix

Tiered model orchestration for the rest of this session. The orchestrator (this session,
recommended to run on **Claude Opus 4.8**) decomposes work, handles design and review itself,
takes the genuinely hard problems, and delegates execution via the Agent tool. Opus is the
**ceiling** here — there is no higher Claude tier in this setup — so when Opus is stuck, the move
is a *different model family* (Codex), not a more expensive Claude.

> Namespacing note: if model-mix was installed as a plugin, the agent names below are prefixed —
> use `subagent_type: "model-mix:mix-opus-worker"` etc. If installed manually into
> `~/.claude/agents/`, use the bare names as written.

- Orchestrator — Claude Opus 4.8 (this session): design, decomposition, review, hard problems
- `mix-sonnet-worker` — Claude Sonnet 4.6 (routine work)
- Codex CLI (`codex exec`, via Bash) — OpenAI's coding agent: cross-vendor worker and escalation valve
- `mix-opus-worker` — Claude Opus 4.8 (parallel implementation capacity)

## Usage

```
/model-mix              # activate tiered orchestration for the rest of the session
/model-mix <task>       # activate and immediately decompose + route <task>
/model-mix stats        # per-model token/cost report for this project (see Stats)
```

## Stats

`/model-mix stats` reports how tokens and cost were actually distributed across the tiers, plus
the estimated savings vs. running everything on Opus 4.8 (the orchestrator tier — i.e. not
routing routine work down to Sonnet). Run the bundled script via Bash, resolving it from this
skill's base directory (shown as "Base directory for this skill" when the skill was invoked):

```bash
SKILL_DIR="<base directory for this skill>"
python3 "$(ls "$SKILL_DIR/scripts/stats.py" "$SKILL_DIR/../../scripts/stats.py" 2>/dev/null | head -n1)" --project
```

(The first candidate is the manual-install layout — `install.sh` copies the script into the
skill directory; the second is a plugin install or repo checkout, where the script lives at
the repo root under `scripts/`.)

Flags: no flag = most recent session only; `--project` = all sessions of the current project;
`--all` = every project; `--days N` = limit window. Present the script's output to the user
as-is (it's already a table), adding one sentence of interpretation. Codex usage is billed by
OpenAI and not included.

## Preflight (do this first, once)

1. State which model this session is running on.
2. If it is not Opus 4.8 (e.g. Sonnet), recommend running `/model` and selecting Opus 4.8 before
   continuing — the orchestrator's judgment is the product, and decomposition/routing/review
   quality drops on a cheaper model. The policy still applies if they stay put.
3. Confirm activation in one line, e.g. "model-mix active: Opus 4.8 orchestrating, Sonnet 4.6
   routine worker, Codex cross-vendor."

## Routing policy

For every piece of work, route by task class. **Default to delegation** for execution work — the
orchestrator does hands-on work only for the first row.

| Task class | Who | How |
|---|---|---|
| Architecture and design decisions, tradeoffs, task decomposition, complex implementation, the genuinely hard problems (deep ambiguous reasoning, critical design calls, debugging), reviewing and integrating worker output, user communication | Orchestrator (Opus 4.8) itself | no delegation |
| Parallel implementation capacity: a second complex workstream while the orchestrator works on another | `mix-opus-worker` | Agent tool, `subagent_type: "mix-opus-worker"` |
| Codebase searches and exploration, boilerplate, single-file edits, doc updates, running tests/builds and reporting results, mechanical renames, lint fixes | `mix-sonnet-worker` | Agent tool, `subagent_type: "mix-sonnet-worker"` |
| Cross-vendor second opinions, independent parallel implementation attempts, code review from a different model family, **escalation when Opus is stuck**, anything the user explicitly asks to send to Codex | Codex CLI | Bash, `codex exec` (see Codex delegation below) |

## Warm worker pool

Treat workers as standing employees, not per-ticket hires. Lifecycle:

- **Lazy start.** Don't pre-spawn at activation — spawn the first sonnet worker when the first
  routine task arrives (`run_in_background: true` so the orchestrator keeps working), and keep
  its agent ID. Same for the first opus worker when complex implementation work shows up.
- **Reuse by default.** Subsequent tasks of that tier go to the warm worker via SendMessage.
  A warm worker that already explored the area finishes follow-up tasks in a fraction of the
  cold-start cost — this is the main answer to delegation overhead.
- **Scale out for fan-out.** Parallel independent tasks justify extra spawns; when the burst is
  over, go back to routing through one warm worker per tier.
- **Retire on drift.** A worker whose context is now irrelevant (project area changed completely)
  or polluted (it's confused, repeating mistakes) gets retired — just stop messaging it and spawn
  fresh. Don't send a confused worker "one more try."
- **Track the roster.** The orchestrator keeps a mental note of live workers (ID, tier, what
  context they hold) and mentions reuse in its routing reports ("sent to the warm sonnet worker
  that did the earlier rename").

## When Opus is stuck (escalation)

Opus is the top Claude tier here, so "escalate" no longer means climbing to a more capable
Claude — it means changing *approach*. When the orchestrator or an opus worker has made a real
attempt and is wrong, stuck, or going in circles, do not pay for a third identical retry. Reach
for a genuinely different angle:

1. **Cross-vendor attempt (Codex).** A different model family is the real "fresh eyes" — run the
   stuck problem through `codex exec` (read-only for diagnosis, workspace-write for an independent
   fix attempt in a separate worktree). Give it the full failure history; it starts cold.
2. **Parallel independent opus attempt.** Spawn a fresh `mix-opus-worker` to take an independent
   run from scratch (not a continuation of the stuck context), then compare.
3. **Bring it back to the user** when the stakes are high and both approaches disagree — an
   irreversible or production-critical call with no clear winner is a decision to surface, not
   to gamble on.

When the cost of being wrong is high and immediate (production incident, data-loss risk,
irreversible decision, hard deadline), skip straight to a cross-vendor cross-check rather than
shipping the first plausible answer.

## Codex delegation

Codex is not a Claude Code subagent — delegate to it by running the Codex CLI through Bash.
It is both a **peer worker** and the **escalation valve** when Opus is stuck: don't auto-route
routine work there (Sonnet is the default cheap tier), but do reach for it for cross-vendor
second opinions, code review, racing two independent implementations, or breaking an Opus
deadlock.

```bash
# Implementation task (writes allowed inside the workspace only)
codex exec -s workspace-write -C <project-dir> --skip-git-repo-check "<scoped task prompt>"

# Analysis / second opinion (no writes)
codex exec -s read-only -C <project-dir> --skip-git-repo-check "<question or review ask>"

# Code review of the current repo
codex exec review -C <project-dir>

# Follow-up in the same Codex session (it keeps context)
codex exec resume --last "<follow-up>"
```

Rules for Codex tasks:

- Scope the prompt exactly like a worker prompt: task, file paths, acceptance criteria. Codex
  starts cold and cannot see this conversation.
- Use `run_in_background: true` on the Bash call for anything non-trivial — Codex runs can take
  minutes — and keep orchestrating meanwhile.
- Never use `--dangerously-bypass-approvals-and-sandbox`. `workspace-write` is the ceiling.
- When Codex edits files, review the diff (`git diff`) before integrating, same as any worker.
  When racing Codex against a Claude worker, run them in separate copies/worktrees so they don't
  write over each other, then the orchestrator picks or merges.
- If `codex exec` fails with an auth error, tell the user to run `codex login` themselves
  (suggest typing `! codex login` so it runs in-session).

## Operating rules

- **Don't delegate below the briefing threshold.** Delegation has a fixed cost: writing the
  briefing, the worker re-reading files cold, the round trip. If doing the task directly would
  take fewer tool calls than briefing a worker (quick read, one-file tweak, a question answerable
  from context already in this session), do it directly — routing discipline is for real work,
  not a tax on small tasks. Likewise, batch several related small tasks into one worker run
  instead of spawning one worker each.
- **Decompose before delegating.** Break the user's request into scoped deliverables, then route
  each one. Don't forward the raw user prompt to a worker.
- **One scoped deliverable per worker prompt.** Include: the exact task, the relevant file paths
  (workers start cold — give them the context you already have), acceptance criteria, and how to
  verify. A well-scoped prompt is what keeps the cheaper tiers cheap — it removes the need for
  the worker to explore.
- **Fan out in parallel.** Independent tasks go out as multiple Agent calls in a single block.
  Use `run_in_background: true` for long-running workers and keep orchestrating meanwhile.
- **Escalate by changing approach, don't retry sideways.** If `mix-sonnet-worker` fails or reports
  the task is bigger than scoped, re-delegate to `mix-opus-worker` (or take it yourself) with the
  failure context. If the opus tier (worker or orchestrator) then fails, don't pay for a third
  identical attempt — switch to a different model family via Codex or a fresh independent opus
  run. See "When Opus is stuck".
- **Review before integrating — with teeth.** Worker output is a draft until checked against the
  acceptance criteria. Prefer mechanical verification over judgment: if tests/build/typecheck can
  arbitrate, run them (or have `mix-sonnet-worker` run them) — a confident wrong answer doesn't
  survive a failing test. For load-bearing results that tests can't arbitrate (design claims,
  root-cause diagnoses, security-relevant changes), get one cheap independent check before
  integrating: a read-only Codex pass (`codex exec -s read-only`) or a fresh sonnet worker asked
  to verify, not re-implement. Spot-read the actual diffs regardless.
- **Two bounces = it's hard.** If the same task has been re-scoped, retried, or "fixed" twice and
  still isn't right, stop treating it as routine — that history means it's time for a different
  approach (cross-vendor Codex attempt or an independent opus run), not a third cheap retry.
- **Warm workers are the default — spawn is the exception.** Workers persist for the session;
  reuse them. Route a new task to an existing worker via SendMessage (it keeps everything it
  learned — files read, project conventions, prior fixes) instead of paying the cold start of a
  fresh Agent call. Spawn a new worker only when: no live worker of the right tier exists, you're
  fanning out in parallel and all warm workers are busy, or the new task is in a completely
  unrelated area where the worker's accumulated context is dead weight. See Warm worker pool.
- **Report routing to the user.** When summarizing, say briefly which tier did what, so the cost
  structure stays visible.
