#!/usr/bin/env python3
"""Search GitHub repositories directly, the way a person browses it (2026-11-07).

GitHub's repo search ANDs every word, so one long sentence ("obsidian memory claude code") finds nothing.
This runs several short queries plus topic: queries, merges them, drops dead repos, and ranks by stars
with a bonus for recent pushes.

  gh_search.py "obsidian memory" "second brain claude" --topics obsidian,claude-code [--months 12] [--n 25]

Each quoted phrase is its own query (keep them 1-3 words). Every --topics value also runs alone and
paired with the others. Uses the logged-in gh CLI (5,000 requests/hour), not a web search engine.
"""
import argparse
import itertools
import json
import subprocess
import time
from datetime import datetime, timezone

FIELDS = "fullName,description,stargazersCount,pushedAt,url"


def run(args):
    p = subprocess.run(["gh", "search", "repos", *args, "--limit", "30", "--json", FIELDS],
                       capture_output=True, text=True)
    if p.returncode:
        return []
    return json.loads(p.stdout or "[]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phrases", nargs="*")
    ap.add_argument("--topics", default="")
    ap.add_argument("--months", type=int, default=12, help="drop repos not pushed in this many months")
    ap.add_argument("--n", type=int, default=25)
    a = ap.parse_args()
    topics = [t.strip() for t in a.topics.split(",") if t.strip()]
    queries = []
    for ph in a.phrases:
        queries += [ph.split() + ["--sort", "stars"], ph.split() + ["--sort", "updated"]]
    for t in topics:
        queries.append([f"topic:{t}", "--sort", "stars"])
    for t1, t2 in itertools.combinations(topics, 2):
        queries.append([f"topic:{t1}", f"topic:{t2}", "--sort", "stars"])
    for ph in a.phrases:
        for t in topics:
            queries.append(ph.split() + [f"topic:{t}", "--sort", "stars"])
    seen = {}
    now = datetime.now(timezone.utc)
    for q in queries:
        for r in run(q):
            r.setdefault("hits", 0)
            cur = seen.setdefault(r["fullName"], r)
            cur["hits"] = cur.get("hits", 0) + 1
        time.sleep(0.3)
    rows = []
    for r in seen.values():
        pushed = datetime.fromisoformat(r["pushedAt"].replace("Z", "+00:00"))
        age_m = (now - pushed).days / 30.4
        if age_m > a.months:
            continue
        # relevance first: a repo found by several of the short queries beats a famous repo found once
        score = r["hits"] ** 2 * __import__("math").log10(r["stargazersCount"] + 10) * (1.3 if age_m < 1 else 1.0)
        rows.append((score, r, age_m))
    rows.sort(key=lambda x: x[0], reverse=True)
    print(f"{len(queries)} queries, {len(seen)} repos, {len(rows)} pushed in the last {a.months} months\n")
    for score, r, age in rows[:a.n]:
        when = "this month" if age < 1 else f"{age:.0f} mo ago"
        print(f"{r['stargazersCount']:>7,}★  {r['fullName']}  (pushed {when}, matched {r['hits']}x)")
        print(f"          {(r['description'] or '')[:150]}")


if __name__ == "__main__":
    main()
