"""Regressions from the 2026-11-25 review: facts on the board must not vanish or move.
  1. a PR that goes away unmerged keeps its last accepted version on the board
  2. losing the bot's state cannot move finish / Level 2 / signing times (they come back from the published data.json)
  3. a person whose computers together cover every module, none whole, is not ranked above whole proofs
  4. build_hours is the value when they finished, not whatever a later re-submit says"""
import copy, json, shutil, sys, tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

rb = SourceFileLoader("rahbot", str(Path(__file__).resolve().parent.parent / "rahbot")).load_module()
src = Path(__file__).resolve().parent / "fixtures" / "sample"
tmp = Path(tempfile.mkdtemp())
shutil.copytree(src / "main", tmp / "main"); shutil.copytree(src / "open", tmp / "open")
dirs = [tmp / "main", tmp / "open"]
fails = 0
def check(ok, what):
    global fails
    print(("  ok    " if ok else "  FAIL  ") + what); fails += not ok
def bd(**kw):
    try:
        return rb.build_data(dirs, **kw)
    except TypeError:                                 # a bot without these options (shows the tests catch the bugs)
        kw.pop("published", None); kw.pop("firsts", None); return rb.build_data(dirs, **kw)
rows = lambda d: {r["who"] or r["name"]: r for r in d["leaderboard"]}

# 1
st_dir = tmp / "state"; st = rb.State(st_dir, persist=True)
f = next((tmp / "open").glob("*/*.json")); rp = f"submissions/{f.parent.name}/{f.name}"
st.pr(99)["path"] = rp; st.set_accepted(rp, f.read_bytes())
try:
    st.drop(99, keep_record=True)
except TypeError:
    st.drop(99)
check((st_dir / "accepted" / f.parent.name / f.name).exists(), "closed PR: its accepted version stays in state/accepted")

# 2
ledger, signed = {}, {}
before = rows(bd(firsts=ledger, signed_map=signed))
who = min((r for r in before.values() if r["whole_proof"]), key=lambda r: r["first_whole_proof_rank"])["who"]
published = bd(firsts=copy.deepcopy(ledger), signed_map=dict(signed))
early = "2026-11-01T00:00:00Z"                        # pretend the published board already had an earlier time
for r in published["leaderboard"]:
    if r["who"] == who: r["finished"] = early
for g in published["signatures"]:
    if g["who"] == who: g["signed"] = early
after = bd(firsts={}, signed_map={}, published=published)   # state AND ledger lost
check(rows(after)[who]["finished"] == early, "state lost: finish time comes back from the published data.json")
if any(g["who"] == who for g in published["signatures"]):
    check(next(g for g in after["signatures"] if g["who"] == who)["signed"] == early,
          "state lost: signing time comes back from the published data.json")

# 3
whole_rec = next(json.loads(p.read_text()) for d in dirs for p in d.glob("*/*.json") if json.loads(p.read_text())["whole_proof"])
idx = list(range(rb.N)); half = len(idx) // 2
for k, part in (("a", idx[:half]), ("b", idx[half:])):
    r = dict(whole_rec); r.pop("axioms", None)
    for key in ("export_sha256", "export_bytes", "export_progress", "sign_statement", "checkers", "final", "display_name"):
        r.pop(key, None)
    r.update(build_id=f"00000000000000{k}{k}", whole_proof=False, axioms=None,
             bitmap_b64=rb.encode_bitmap(rb.bits_from_indices(part)), modules_compiled=len(part))
    (tmp / "open" / "zed").mkdir(exist_ok=True)
    (tmp / "open" / "zed" / f"{r['build_id']}.json").write_text(json.dumps(r))
board = bd()["leaderboard"]
zed = next(i for i, r in enumerate(board) if r["who"] == "zed")
check(board[zed]["modules"] == rb.N and not board[zed]["whole_proof"], "zed's two computers cover every module, none whole")
check(all(r["whole_proof"] for r in board[:zed]) and zed == sum(r["whole_proof"] for r in board),
      f"zed is listed after every whole proof (position {zed + 1})")
shutil.rmtree(tmp / "open" / "zed")

# 4
ledger = {}
h0 = rows(bd(firsts=ledger))[who]["build_hours"]
g = next(p for d in dirs for p in d.glob(f"{who}/*.json") if json.loads(p.read_text())["whole_proof"])
r = json.loads(g.read_text()); r["busy_seconds"] += 7200; g.write_text(json.dumps(r))
check(rows(bd(firsts=ledger))[who]["build_hours"] == h0, f"re-submit with more busy time keeps build_hours {h0}")
sys.exit(1 if fails else 0)
