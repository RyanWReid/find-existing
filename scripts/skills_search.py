"""Search the public Claude Code skills catalog (majiayu000/claude-skill-registry, ~320k skills, refreshed daily)
before building anything

    python3 scripts/skills_search.py sync                  # download the 256 index shards (~45 MB gz), ~1 min
    python3 scripts/skills_search.py search voice agent turn taking [-n 15]
Ranking: every word must appear in name/description/tags/repo; then by GitHub stars of the repo. One line per repo.
The catalog is data, not endorsement: read a skill's SKILL.md and license before installing it."""
import concurrent.futures as cf, gzip, json, math, os, sys, urllib.request
BASE = "https://raw.githubusercontent.com/majiayu000/claude-skill-registry/main/"
DIR = os.path.expanduser("~/.cache/skill-registry")
INDEX = f"{DIR}/index.jsonl"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return r.read()


def sync():
    os.makedirs(DIR, exist_ok=True)
    man = json.loads(get("registry-manifest.json"))
    def one(s):
        return json.loads(gzip.decompress(get(s["gzip_path"])))["skills"]
    n = 0
    with cf.ThreadPoolExecutor(16) as ex, open(INDEX + ".tmp", "w") as f:
        for skills in ex.map(one, man["shards"]):
            for s in skills:
                f.write(json.dumps({k: s.get(k) for k in ("name", "description", "repo", "stars", "license",
                                                           "source_url", "category", "tags")}) + "\n")
                n += 1
    os.replace(INDEX + ".tmp", INDEX)
    print(f"synced {n} skills (catalog {man.get('generated_at', '?')[:10]})")


def search(words, n=15):
    if not os.path.exists(INDEX):
        sync()
    words = [w.lower() for w in words]
    hits = {}
    for line in open(INDEX):
        s = json.loads(line)
        hay = " ".join(str(s.get(k) or "") for k in ("name", "description", "repo", "tags")).lower()
        if all(w in hay for w in words):
            key = s["repo"]
            if key not in hits or (s.get("stars") or 0) > (hits[key].get("stars") or 0):
                hits[key] = s
    ranked = sorted(hits.values(), key=lambda s: -math.log1p(s.get("stars") or 0))[:n]
    for s in ranked:
        print(f"{s.get('stars') or 0:>7}★  {s['name'][:40]:40}  {s.get('license') or '?':10}  {s['source_url']}")
        print(f"          {(s.get('description') or '')[:150]}")
    print(f"({len(hits)} repos matched)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("sync", "search"):
        sys.exit(__doc__)
    if a[0] == "sync":
        sync()
    else:
        n = 15
        if "-n" in a:
            i = a.index("-n"); n = int(a[i + 1]); a = a[:i] + a[i + 2:]
        search(a[1:], n)
