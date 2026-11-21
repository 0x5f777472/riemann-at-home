"""Independent checks of an aggregate data.json against the submissions it came from (all assumed valid)."""
import base64, gzip, json, sys
from pathlib import Path

data, subs = json.loads(Path(sys.argv[1]).read_text()), [Path(x) for x in sys.argv[2:]]
N = data["n"]
def bits(r):
    return int.from_bytes(gzip.decompress(base64.b64decode(r["bitmap_b64"])), "little")

people = {}                                   # who -> build_id -> versions sorted by recorded
for sub in subs:
    for f in sub.glob("*/*.json"):                # <login>/<build_id>.json
        r = json.loads(f.read_text())
        people.setdefault(f.parts[-2], {}).setdefault(f.stem, []).append(r)
for builds in people.values():
    for recs in builds.values(): recs.sort(key=lambda r: r["recorded"])

# names: the choice in the person's newest record; "who" only when they kept their login
expect_name = {}
for w, builds in people.items():
    newest = max((recs[-1] for recs in builds.values()), key=lambda r: r["recorded"])
    expect_name[w] = "anon" if newest.get("anonymous") else newest.get("display_name") or w
rows_by = {}
for row in data["leaderboard"]:
    if row["who"] is not None:
        assert row["name"] == row["who"], row
        rows_by[row["who"]] = row
    else:
        w = next(w for w, n in expect_name.items() if n == row["name"] or (n == "anon" and row["name"].startswith("anonymous #")
                                                                           and w not in rows_by))
        rows_by[w] = row
anon_names = [r["name"] for r in data["leaderboard"] if r["name"].startswith("anonymous #")]
assert len(anon_names) == len(set(anon_names)) == sum(n == "anon" for n in expect_name.values()), anon_names
for w, n in expect_name.items():
    assert (rows_by[w]["who"] is None) == (n != w), (w, rows_by[w])
print(f"  names: {sorted(r['name'] for r in data['leaderboard'])}; who hidden for {sum(r['who'] is None for r in data['leaderboard'])}  ok")
board = rows_by
union = {w: 0 for w in people}
for w, builds in people.items():
    for recs in builds.values(): union[w] |= bits(recs[-1])
    row = board[w]
    assert row["modules"] == union[w].bit_count(), (w, row["modules"], union[w].bit_count())
    assert row["computers"] == len(builds), (w, row["computers"])
    largest = max((recs[-1] for recs in builds.values()), key=lambda r: r["modules_compiled"])
    assert row["machine"] == largest["machine"]["cpu"], (w, row["machine"])
    wholes = sorted((recs[-1] for recs in builds.values() if recs[-1]["whole_proof"]), key=lambda r: r["recorded"])
    assert row["whole_proof"] == bool(wholes) and row["finished"] == (wholes[0]["recorded"] if wholes else None), w
    assert row["build_hours"] == (round(wholes[0]["busy_seconds"] / 3600, 1) if wholes else None), w
    print(f"  {w}: {row['modules']:,} modules on {row['computers']} computer(s), machine {row['machine']}  ok")

# terrain counts distinct people, not builds
b = gzip.decompress(base64.b64decode(data["builders_b64"]))
assert len(b) == N
for i in range(N):
    want = min(250, sum(1 for u in union.values() if u >> i & 1))
    assert b[i] == want, (i, b[i], want)
multi = [w for w, bs in people.items() if len(bs) > 1]
assert multi, "fixture should have a person with two computers"
both = [i for i in range(N) if all(bits(recs[-1]) >> i & 1 for recs in people[multi[0]].values())]
print(f"  terrain: all {N:,} modules = distinct people; {multi[0]}'s {len(both):,} modules built on both computers count once  ok")

# running: one entry per non-whole build, modules desc
want = sorted(((w, bid, recs[-1]["modules_compiled"], recs[-1]["recorded"]) for w, bs in people.items()
               for bid, recs in bs.items() if not recs[-1]["whole_proof"] and not recs[-1].get("final")), key=lambda x: (-x[2], x[3]))
name_of = {w: rows_by[w]["name"] for w in people}
want = [(name_of[w], bid if rows_by[w]["who"] else None, m, t) for w, bid, m, t in want]
got = [(e["name"], e.get("build_id"), e["modules"], e["recorded"]) for e in data["running"]]
assert got == want, (got, want)
assert all(set(e) == {"name", "who", "machine", "modules", "recorded"} | ({"build_id"} if e["who"] else set())
           for e in data["running"]), "running keys (build_id only for people shown by login)"
assert {"name", "who"} <= set(data["latest"])
print(f"  running: {len(got)} builds not whole and not final, modules desc  ok")

# order: modules desc; whole proofs by first_whole_proof_rank; then since
rows = data["leaderboard"]
assert rows == sorted(rows, key=lambda x: (-x["modules"], x["first_whole_proof_rank"] or 0, x["since"])), "order"
print("  leaderboard order  ok")

# levels + signatures
REF = "5ea74b912147c5c93cc2b6d70cc727cf908df2f62ac6a20480a3fa02f6be244e"
CHK = {"nanoda", "con-leche", "lean4checker", "lean4lean"}
def lvl(r):
    if not (r["whole_proof"] and r.get("export_sha256") == REF): return 1
    return 3 if any(c["result"] == "accept" and c["name"] in CHK for c in r.get("checkers") or []) else 2
want_sig = []
for w, builds in people.items():
    latest_recs = [recs[-1] for recs in builds.values()]
    assert rows_by[w]["level"] == max(map(lvl, latest_recs)), (w, rows_by[w]["level"])
    if any(r.get("sign_statement") and lvl(r) >= 2 for r in latest_recs):
        want_sig.append(rows_by[w]["name"])
sigs = data["signatures"]
assert sorted(s["name"] for s in sigs) == sorted(want_sig), (sigs, want_sig)
assert [s["signed"] for s in sigs] == sorted(s["signed"] for s in sigs), "signatures ordered by signed"
assert all(s["level"] >= 2 and set(s) == {"who", "name", "signed", "machine", "level", "checkers"} for s in sigs)
print(f"  levels + signatures: {[(s['name'], s['level'], s['signed']) for s in sigs]}  ok")
