#!/usr/bin/env python3
"""model-mix stats: per-model token/cost report from Claude Code transcripts.

Reads the JSONL session transcripts Claude Code writes under ~/.claude/projects/,
aggregates token usage by model (main session + subagent sidechains), prices it,
and shows the counterfactual cost had everything run on Opus 4.8 (the orchestrator
tier) instead of routing routine work down to Sonnet.

Usage:
  stats.py                 # current project (cwd), most recent session
  stats.py --project       # current project, all sessions
  stats.py --all           # every project
  stats.py --days N        # limit to the last N days (with --project/--all)
  stats.py --file PATH     # a specific session .jsonl
"""

import argparse
import glob
import json
import os
import sys
import time

# $/MTok: (input, output). Cache read = 0.1x input, cache write = 1.25x input (5m TTL).
# fable/mythos retained so historical transcripts still price correctly, but the
# counterfactual baseline is Opus (fable is no longer a tier in this setup).
PRICES = {
    "fable": (10.0, 50.0),
    "mythos": (10.0, 50.0),
    "opus": (5.0, 25.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
}


def price_key(model: str):
    for key in PRICES:
        if key in model:
            return key
    return None


def session_files(args):
    base = os.path.expanduser("~/.claude/projects")
    if args.file:
        return [os.path.expanduser(args.file)]
    if args.all:
        files = glob.glob(os.path.join(base, "*", "*.jsonl"))
    else:
        # Claude Code encodes project paths by replacing every non-alphanumeric char with '-'
        proj = "".join(c if c.isalnum() else "-" for c in os.getcwd())
        pdir = os.path.join(base, proj)
        if not os.path.isdir(pdir):
            sys.exit(f"no transcripts for this project ({pdir}); try --all")
        files = glob.glob(os.path.join(pdir, "*.jsonl"))
        if not args.project:
            files = [max(files, key=os.path.getmtime)] if files else []
    if args.days:
        cutoff = time.time() - args.days * 86400
        files = [f for f in files if os.path.getmtime(f) >= cutoff]
    return sorted(files)


def aggregate(files):
    # model -> [requests, input, cache_write, cache_read, output]
    stats = {}
    seen = {}  # message id -> usage line (keep last occurrence per id)
    for path in files:
        try:
            fh = open(path, encoding="utf-8")
        except OSError:
            continue
        with fh:
            for lineno, line in enumerate(fh):
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                m = d.get("message") or {}
                u, model = m.get("usage"), m.get("model")
                if not u or not model or model == "<synthetic>":
                    continue
                # int fallback can't collide with real (str) message ids
                seen[(path, m.get("id") or lineno)] = (model, u)
    for model, u in seen.values():
        row = stats.setdefault(model, [0, 0, 0, 0, 0])
        row[0] += 1
        row[1] += u.get("input_tokens", 0)
        row[2] += u.get("cache_creation_input_tokens", 0)
        row[3] += u.get("cache_read_input_tokens", 0)
        row[4] += u.get("output_tokens", 0)
    return stats


def cost(key, inp, cw, cr, out):
    pi, po = PRICES[key]
    return (inp * pi + cw * pi * 1.25 + cr * pi * 0.10 + out * po) / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--days", type=int)
    ap.add_argument("--file")
    args = ap.parse_args()

    files = session_files(args)
    if not files:
        sys.exit("no transcript files found")
    stats = aggregate(files)
    if not stats:
        sys.exit("no usage records found")

    print(f"model-mix stats — {len(files)} session file(s)\n")

    # First pass: price every model and accumulate the totals, so the table can show
    # each tier's share of cost (you can't compute a percentage until the total is known).
    rows = []  # (model, n, inp, cw, cr, out, key, cost or None)
    total_cost = 0.0
    mix_excl_haiku = 0.0       # actual mix cost, haiku background calls removed
    opus_counterfactual = 0.0  # same non-haiku work repriced at the Opus tier
    capability_cost = 0.0      # the top capability tier: fable/mythos historically, opus now
    fable_cost = 0.0           # the now-removed top tier specifically, for historical data
    haiku_excluded = False
    unpriced = []
    for model, (n, inp, cw, cr, out) in sorted(stats.items()):
        key = price_key(model)
        if key is None:
            unpriced.append(model)
            rows.append((model, n, inp, cw, cr, out, None, None))
            continue
        c = cost(key, inp, cw, cr, out)
        total_cost += c
        if key == "haiku":
            # Haiku usage is Claude Code background calls (title generation etc.) that would
            # never have run on Opus; model-mix has no haiku tier — exclude from the comparison
            # on both sides so it doesn't distort the savings number.
            haiku_excluded = True
        else:
            mix_excl_haiku += c
            # same work on the Opus orchestrator tier (all Claude models share a tokenizer,
            # so the token counts carry over directly)
            opus_counterfactual += cost("opus", inp, cw, cr, out)
        if key in ("fable", "mythos", "opus"):
            capability_cost += c
        if key in ("fable", "mythos"):
            fable_cost += c
        rows.append((model, n, inp, cw, cr, out, key, c))

    # "mine first": the orchestrator tier (Opus) leads the table, then everyone else by
    # descending cost, unpriced rows last. The table is about who did the work, and the
    # orchestrator is the fixed point you route everything else away from.
    rows.sort(key=lambda r: (0 if r[6] == "opus" else 1, r[6] is None, -(r[7] or 0)))

    # Request-count totals: the table's "% reqs" column (how often each tier was called) and
    # the headline below both divide by the same all-tiers request total.
    total_reqs = sum(r[1] for r in rows)
    cap_reqs = {}  # capability-tier key -> request count, for the calls-vs-cost summary below
    for _m, n, _i, _cw, _cr, _o, key, _c in rows:
        if key in ("fable", "mythos", "opus"):
            cap_reqs[key] = cap_reqs.get(key, 0) + n

    hdr = f"{'model':<22}{'reqs':>6}{'% reqs':>8}{'input':>12}{'cache-w':>12}{'cache-r':>14}{'output':>10}{'cost $':>10}{'% cost':>8}"
    print(hdr)
    print("-" * len(hdr))
    for model, n, inp, cw, cr, out, key, c in rows:
        preq = n / total_reqs * 100 if total_reqs else 0.0
        if c is None:
            print(f"{model:<22}{n:>6}{preq:>8.1f}{inp:>12,}{cw:>12,}{cr:>14,}{out:>10,}{'?':>10}{'':>8}")
            continue
        pct = c / total_cost * 100 if total_cost else 0.0
        print(f"{model:<22}{n:>6}{preq:>8.1f}{inp:>12,}{cw:>12,}{cr:>14,}{out:>10,}{c:>10.2f}{pct:>8.1f}")

    print("-" * len(hdr))
    total_pct = 100.0 if total_cost else 0.0
    print(f"{'TOTAL':<22}{'':>6}{'':>8}{'':>12}{'':>12}{'':>14}{'':>10}{total_cost:>10.2f}{total_pct:>8.1f}")

    # The expensive capability tiers (Opus/Fable) on both axes at once — share of calls and
    # share of cost. The two routinely diverge: a tier can be a minority of calls yet the
    # majority of spend, because each of its calls is pricier. This is a concentration measure,
    # not an escalation count — Opus is the orchestrator/ceiling here, and the real escalation
    # valve (Codex) is billed by OpenAI and never shows up in these transcripts.
    if total_cost > 0 and total_reqs and cap_reqs:
        cap_calls = sum(cap_reqs.values())
        # label only the capability tiers actually present (Opus first as the orchestrator),
        # so a normal Opus-only session doesn't claim a Fable tier it never used
        names = {"opus": "Opus", "fable": "Fable", "mythos": "Mythos"}
        cap_label = "/".join(names[k] for k in ("opus", "fable", "mythos") if k in cap_reqs)
        print(f"\nexpensive tier ({cap_label}): "
              f"{cap_calls / total_reqs * 100:.1f}% of calls, "
              f"{capability_cost / total_cost * 100:.1f}% of cost")
        if fable_cost > 0:
            fable_calls = cap_reqs.get("fable", 0) + cap_reqs.get("mythos", 0)
            print(f"  Fable (now-removed top tier): "
                  f"{fable_calls / total_reqs * 100:.1f}% of calls, "
                  f"{fable_cost / total_cost * 100:.1f}% of cost")

    if opus_counterfactual > mix_excl_haiku > 0:
        saved = opus_counterfactual - mix_excl_haiku
        haiku_note = "; haiku background calls excluded" if haiku_excluded else ""
        print(f"\nall-Opus counterfactual (est.{haiku_note}): ${opus_counterfactual:.2f}")
        print(f"estimated savings from the mix: ${saved:.2f} ({saved / opus_counterfactual * 100:.0f}%)")
    if unpriced:
        print(f"\nnote: no price table entry for: {', '.join(unpriced)} (excluded from totals)")
    print("note: Codex CLI usage is billed by OpenAI and not visible in Claude transcripts.")


if __name__ == "__main__":
    main()
