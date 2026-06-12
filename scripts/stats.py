#!/usr/bin/env python3
"""model-mix stats: per-model token/cost report from Claude Code transcripts.

Reads the JSONL session transcripts Claude Code writes under ~/.claude/projects/,
aggregates token usage by model (main session + subagent sidechains), prices it,
and shows the counterfactual cost had everything run on Fable 5.

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
PRICES = {
    "fable": (10.0, 50.0),
    "mythos": (10.0, 50.0),
    "opus": (5.0, 25.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
}
# Fable's tokenizer yields ~30% more tokens for the same content than Opus-tier models.
FABLE_TOKENIZER_FACTOR = 1.30


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
    hdr = f"{'model':<22}{'reqs':>6}{'input':>12}{'cache-w':>12}{'cache-r':>14}{'output':>10}{'cost $':>10}"
    print(hdr)
    print("-" * len(hdr))

    total_cost = 0.0
    fable_counterfactual = 0.0
    haiku_excluded = False
    unpriced = []
    for model, (n, inp, cw, cr, out) in sorted(stats.items()):
        key = price_key(model)
        if key is None:
            unpriced.append(model)
            print(f"{model:<22}{n:>6}{inp:>12,}{cw:>12,}{cr:>14,}{out:>10,}{'?':>10}")
            continue
        c = cost(key, inp, cw, cr, out)
        total_cost += c
        if key == "haiku":
            # Haiku usage is Claude Code background calls (title generation etc.) that would
            # never have run on Fable; model-mix has no haiku tier — exclude from counterfactual.
            haiku_excluded = True
        else:
            # same work on Fable: Fable prices + tokenizer inflation (skip if already Fable-tier)
            factor = 1.0 if key in ("fable", "mythos") else FABLE_TOKENIZER_FACTOR
            fable_counterfactual += cost("fable", inp * factor, cw * factor, cr * factor, out * factor)
        print(f"{model:<22}{n:>6}{inp:>12,}{cw:>12,}{cr:>14,}{out:>10,}{c:>10.2f}")

    print("-" * len(hdr))
    print(f"{'TOTAL':<22}{'':>6}{'':>12}{'':>12}{'':>14}{'':>10}{total_cost:>10.2f}")
    if fable_counterfactual > total_cost > 0:
        saved = fable_counterfactual - total_cost
        haiku_note = "; haiku background calls excluded" if haiku_excluded else ""
        print(f"\nall-Fable counterfactual (est., incl. ~30% tokenizer overhead{haiku_note}): ${fable_counterfactual:.2f}")
        print(f"estimated savings from the mix: ${saved:.2f} ({saved / fable_counterfactual * 100:.0f}%)")
    if unpriced:
        print(f"\nnote: no price table entry for: {', '.join(unpriced)} (excluded from totals)")
    print("note: Codex CLI usage is billed by OpenAI and not visible in Claude transcripts.")


if __name__ == "__main__":
    main()
