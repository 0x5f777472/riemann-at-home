"""Issue #12: a build is one file that each `submit` overwrites. Re-submitting a finished build must not move its
finish date (and so its whole-proof rank) or the time it first reached Level 2."""
import json, shutil, sys, tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

rb = SourceFileLoader("rahbot", str(Path(__file__).resolve().parent.parent / "rahbot")).load_module()
src = Path(__file__).resolve().parent / "fixtures" / "sample"
tmp = Path(tempfile.mkdtemp())
subs = tmp / "subs"
shutil.copytree(src / "main", subs / "main"); shutil.copytree(src / "open", subs / "open")
dirs = [subs / "main", subs / "open"]

def board(firsts):
    try:
        d = rb.build_data(dirs, firsts=firsts)
    except TypeError:                              # a bot without the ledger (proves this test catches the bug)
        d = rb.build_data(dirs)
    return {r["who"] or r["name"]: r for r in d["leaderboard"]}

ledger = {}
before = board(ledger)
wholes = {w: r for w, r in before.items() if r["whole_proof"]}
assert len(wholes) >= 2, f"fixture needs two whole proofs, has {sorted(wholes)}"
first = min(wholes.values(), key=lambda r: r["first_whole_proof_rank"])
who = first["who"] or first["name"]
print(f"  before: {who} finished {first['finished']}, rank {first['first_whole_proof_rank']}, validated_at {first.get('validated_at')}")

# the same person runs `submit` again much later: the same build file, rewritten with a new recorded time
f = next(p for d in dirs for p in d.glob(f"*/*.json") if p.parent.name == who and json.loads(p.read_text())["whole_proof"])
rec = json.loads(f.read_text()); rec["recorded"] = "2026-11-24T23:00:00Z"; f.write_text(json.dumps(rec))
after = board(ledger)[who]
print(f"  after re-submit: finished {after['finished']}, rank {after['first_whole_proof_rank']}, validated_at {after.get('validated_at')}")
assert after["finished"] == first["finished"], "re-submitting moved the finish date"
assert after["first_whole_proof_rank"] == first["first_whole_proof_rank"], "re-submitting moved the rank"
assert after.get("validated_at") == first.get("validated_at"), "re-submitting moved the Level 2 time"

if not hasattr(rb, "merge_firsts"): sys.exit("no ledger")
# the seed (times recovered from history) wins when it is earlier, and never makes a time later
seeded = rb.merge_firsts({who: {"whole": "2026-12-31T00:00:00Z"}}, {who: {"whole": "2026-01-01T00:00:00Z"}})
assert seeded[who]["whole"] == "2026-01-01T00:00:00Z", seeded
kept = rb.merge_firsts({who: {"whole": "2026-01-01T00:00:00Z"}}, {who: {"whole": "2026-12-31T00:00:00Z"}})
assert kept[who]["whole"] == "2026-01-01T00:00:00Z", kept
print("  seed merge: earlier time wins both ways")
