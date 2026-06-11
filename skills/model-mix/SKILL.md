---
name: model-mix
description: "Turn the session into a tiered orchestrator: Opus 4.8 orchestrates and handles design, Sonnet 4.6 takes routine work, Codex CLI takes cross-vendor work, and Fable 5 is held in reserve — escalated to only for genuinely hard or urgent problems. Trigger: /model-mix"
trigger: /model-mix
---

# /model-mix

Tiered model orchestration for the rest of this session. The orchestrator (this session,
recommended to run on **Claude Opus 4.8**) decomposes work, handles design and review itself,
and delegates via the Agent tool. **Fable 5 is deliberately held in reserve** — it is the most
capable and most expensive tier, spared from everyday work so it's available when something is
genuinely hard or urgent.

> Namespacing note: if model-mix was installed as a plugin, the agent names below are prefixed —
> use `subagent_type: "model-mix:mix-opus-worker"` etc. If installed manually into
> `~/.claude/agents/`, use the bare names as written.

- Orchestrator — Claude Opus 4.8 (this session)
- `mix-sonnet-worker` — Claude Sonnet 4.6 (routine work)
- Codex CLI (`codex exec`, via Bash) — OpenAI's coding agent, cross-vendor worker
- `mix-opus-worker` — Claude Opus 4.8 (parallel implementation capacity)
- `mix-fable-worker` — Claude Fable 5 (**reserved escalation tier — see gate below**)

## Usage

```
/model-mix              # activate tiered orchestration for the rest of the session
/model-mix <task>       # activate and immediately decompose + route <task>
/model-mix heavy        # heavy mode: recommend Fable 5 AS the orchestrator (see Modes)
```

## Modes

**Default (spare-Fable):** Opus 4.8 orchestrates, Fable is the gated escalation tier. Right for
interactive day-to-day work, where most tasks never need Fable.

**Heavy (`/model-mix heavy`):** for long-horizon autonomous work — multi-hour builds, large
migrations, overnight runs. Fable's standout strength is precisely orchestration and delegation,
so benching it there wastes its best skill. In heavy mode, tell the user to flip the session to
Fable via `/model` and re-invoke; Fable then orchestrates using this same routing policy (the
`mix-fable-worker` row becomes "handle it yourself"), still pushing execution down to the cheap
tiers, so the cost premium applies mostly to the thin orchestration layer, not the bulk work.
Suggest heavy mode proactively when the user describes a long autonomous task; suggest switching
back to default when the heavy task is done.

## Preflight (do this first, once)

1. State which model this session is running on.
2. If it is Fable 5, warn the user: this setup is designed to spare Fable — run `/model` and
   select Opus 4.8 as the session model, then re-invoke `/model-mix`. (If they prefer Fable as
   orchestrator anyway, continue; the routing policy still applies, and the `mix-fable-worker`
   escalation row becomes "handle it yourself".)
3. Confirm activation in one line, e.g. "model-mix active: Opus 4.8 orchestrating, Sonnet 4.6 /
   Codex workers, Fable 5 in reserve."

## Routing policy

For every piece of work, route by task class. **Default to delegation** for execution work — the
orchestrator does hands-on work only for the first row.

| Task class | Who | How |
|---|---|---|
| Architecture and design decisions, tradeoffs, task decomposition, complex implementation, reviewing and integrating worker output, user communication | Orchestrator (Opus 4.8) itself | no delegation |
| Genuinely hard or urgent: deep ambiguous reasoning, critical design calls, debugging the orchestrator failed at, time-critical correctness, or the user invokes urgency/Fable | `mix-fable-worker` | Agent tool, `subagent_type: "mix-fable-worker"` — only after passing the escalation gate below |
| Parallel implementation capacity: a second complex workstream while the orchestrator works on another | `mix-opus-worker` | Agent tool, `subagent_type: "mix-opus-worker"` |
| Codebase searches and exploration, boilerplate, single-file edits, doc updates, running tests/builds and reporting results, mechanical renames, lint fixes | `mix-sonnet-worker` | Agent tool, `subagent_type: "mix-sonnet-worker"` |
| Cross-vendor second opinions, independent parallel implementation attempts, code review from a different model family, anything the user explicitly asks to send to Codex | Codex CLI | Bash, `codex exec` (see Codex delegation below) |

## Fable escalation gate

Fable 5 is the scarce resource this setup protects. Before spawning `mix-fable-worker`, at least
one of these must be true:

1. **The cheaper tiers already failed** — the orchestrator (or an opus worker) made a real
   attempt and it's wrong, stuck, or going in circles. Include what was tried and how it failed
   in the escalation prompt.
2. **The cost of being wrong is high and immediate** — production incident, data-loss risk,
   irreversible decision, hard deadline ("urgent" from the user counts).
3. **The user explicitly asked** for Fable on this task.

If none apply, do not escalate — handle it at the orchestrator tier. Never route routine or
merely-complex work to Fable "to be safe." When escalating, give the Fable worker everything:
full problem statement, evidence gathered, failed attempts, file paths, and what a correct answer
must satisfy — its time is the most expensive in the system, don't make it re-discover context.

## Codex delegation

Codex is not a Claude Code subagent — delegate to it by running the Codex CLI through Bash.
It is a **peer worker, not a default tier**: don't auto-route routine work there (Sonnet is the
default cheap tier). Use Codex when the user asks for it, when a cross-vendor second opinion or
review adds value, or when racing two independent implementations of the same scoped task.

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
- **Escalate up, don't retry sideways.** If `mix-sonnet-worker` fails or reports the task is
  bigger than scoped, re-delegate to `mix-opus-worker` with the failure context. If the opus tier
  (worker or orchestrator) fails, that satisfies the Fable escalation gate — escalate to
  `mix-fable-worker` with the full failure history.
- **Review before integrating — with teeth.** Worker output is a draft until checked against the
  acceptance criteria. Prefer mechanical verification over judgment: if tests/build/typecheck can
  arbitrate, run them (or have `mix-sonnet-worker` run them) — a confident wrong answer doesn't
  survive a failing test. For load-bearing results that tests can't arbitrate (design claims,
  root-cause diagnoses, security-relevant changes), get one cheap independent check before
  integrating: a read-only Codex pass (`codex exec -s read-only`) or a fresh sonnet worker asked
  to verify, not re-implement. Spot-read the actual diffs regardless.
- **Two bounces = it's hard.** If the same task has been re-scoped, retried, or "fixed" twice and
  still isn't right, stop treating it as routine — that history is evidence for the Fable
  escalation gate. Escalate with the full bounce history instead of paying for a third cheap
  attempt.
- **Continue, don't respawn.** To follow up with a worker that already has context, use
  SendMessage with its agent ID instead of spawning a fresh one.
- **Report routing to the user.** When summarizing, say briefly which tier did what, so the cost
  structure stays visible.
