"""Build rahbot test fixtures. Honest records use the real compiled modules of the reference build
(/Users/Shared/riemann-at-home/lean, read-only). Run: python3 -I tests/make_fixtures.py"""
import hashlib, json, os, shutil, subprocess, sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

BOT = Path(__file__).resolve().parent.parent
rb = SourceFileLoader("rahbot", str(BOT / "rahbot")).load_module()
FX = BOT / "tests/fixtures"

mods = rb.modules()
# Freeze the reference first: the reference build may be running (it deletes and rewrites .olean files).
SNAP = FX.parent / "reference.snap"
subprocess.run([sys.executable, "-I", str(BOT / "rahbot"), "reference-snapshot", "--out", str(SNAP)], check=True)
rb.use_snapshot(SNAP)
snap = SNAP.read_bytes()
compiled = [i for i in range(rb.N) if snap[32 * i:32 * i + 32] != bytes(32)]
print(f"reference build: {len(compiled)} compiled modules")
FAKE_DIGEST = hashlib.sha256(b"not a real digest").hexdigest()


def bid(tag):
    """deterministic 16-hex build_id per fake computer"""
    return hashlib.sha256(tag.encode()).hexdigest()[:16]


def record(started, recorded, idx, cpu="Apple M5 Max", digest=None, build="default", **over):
    raw = rb.bits_from_indices(idx)
    if digest == "real":
        digest = rb.reference_digest(raw)
    t0, t1 = rb.parse_ts(started), rb.parse_ts(recorded)
    r = {"format": rb.FORMAT, "tool": "riemann-at-home 1.0.0", "archive_sha256": rb.ARCHIVE_SHA256,
         "toolchain": rb.TOOLCHAIN, "mathlib_rev": rb.MATHLIB_REV, "build_folder": "/Users/Shared/riemann-at-home/lean",
         "machine": {"os": "Darwin 25.4.0", "arch": "arm64", "cpu": cpu, "cores": 18},
         "started": started, "recorded": recorded, "busy_seconds": int((t1 - t0).total_seconds() * 0.9),
         "modules_compiled": len(set(idx)), "bitmap_b64": rb.encode_bitmap(raw), "olean_digest": digest or FAKE_DIGEST,
         "whole_proof": False, "axioms": None, "build_id": bid(build)}
    r.update(over)
    return r


def save(rel, rec):
    p = FX / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, indent=1) + "\n")
    return p


def repo_path(login, rec):
    return f"submissions/{login}/{rec['build_id']}.json"


if FX.exists():
    shutil.copytree(FX, FX.with_name("fixtures.bak"), dirs_exist_ok=True)
    shutil.rmtree(FX)

cset = set(compiled)
extra = [i for i in range(0, rb.N, 7) if i not in cset][:13000 - len(compiled)]
extraB = [i for i in range(3, rb.N, 7) if i not in cset][:3000]          # disjoint from dave's extra
AX = ["propext", "Classical.choice", "Quot.sound"]
EXP = {"export_sha256": rb.REF_EXPORT_SHA256, "export_bytes": rb.REF_EXPORT_BYTES}
NANODA = [{"name": "nanoda", "version": "0.4.1", "result": "accept", "seconds": 5400}]
A, B = "alice-macbook", "alice-macmini"
R = {
    "alice1": record("2026-11-19T08:00:00Z", "2026-11-19T14:00:00Z", compiled[:1500], digest="real", build=A),
    "alice2": record("2026-11-19T08:00:00Z", "2026-11-20T08:00:00Z", compiled, digest="real", build=A),
    "alice3_shrink": record("2026-11-19T08:00:00Z", "2026-11-21T08:00:00Z", compiled[100:], build=A),
    "alice4_shrink": record("2026-11-19T08:00:00Z", "2026-11-21T10:20:00Z", compiled[100:], build=A),
    # alice's second computer: B1 is recorded between A1 and A2 (interleaving builds)
    "aliceB1": record("2026-11-19T10:00:00Z", "2026-11-19T20:00:00Z", compiled[:1000] + extraB[:1500], cpu="Apple M4", build=B),
    "aliceB2": record("2026-11-19T10:00:00Z", "2026-11-21T06:00:00Z", compiled[:1000] + extraB, cpu="Apple M4", build=B),
    "aliceB_shrink": record("2026-11-19T10:00:00Z", "2026-11-21T10:00:00Z", compiled[50:1000] + extraB, cpu="Apple M4", build=B),
    "bob": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, cpu="Apple M4 Pro", digest="real", build="bob"),
    "bob_final": record("2026-11-20T00:00:00Z", "2026-11-21T09:00:00Z", compiled, cpu="Apple M4 Pro", build="bob", final=True),
    "bob_after_final": record("2026-11-20T00:00:00Z", "2026-11-21T10:00:00Z", compiled + extra[:10], cpu="Apple M4 Pro", build="bob"),
    "carol_whole": record("2026-11-18T00:00:00Z", "2026-11-19T22:00:00Z", range(rb.N), cpu="AMD Ryzen 9 7950X",
                          whole_proof=True, axioms=AX, build="carol", **EXP, checkers=NANODA, sign_statement=True),  # Level 3, signs
    "dave_fast": record("2026-11-21T00:00:00Z", "2026-11-21T02:00:00Z", compiled + extra, cpu="Apple M3 Ultra", build="dave"),
    "eve_too_fast": record("2026-11-21T03:00:00Z", "2026-11-21T03:10:00Z", compiled, build="eve"),
    "erin": record("2026-11-21T06:00:00Z", "2026-11-21T10:00:00Z", compiled[:800], cpu="Intel Core i9-13900K", build="erin"),
    "wrong_archive": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, archive_sha256="0" * 64, build="frank"),
    "bad_count": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, modules_compiled=5000, build="grace"),
    "whole_no_axioms": record("2026-11-18T00:00:00Z", "2026-11-19T22:00:00Z", range(rb.N), whole_proof=True, axioms=None, build="heidi"),
    "whole_partial": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, whole_proof=True, axioms=AX, build="ivan"),
    "bad_digest": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="judy"),
    "dn_ok": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="dn1", display_name="Ada L. été 🧮"),
    "dn_own_login": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="dn2", display_name="Alice"),
    "dn_is_login": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="dn3", display_name="BoB"),
    "dn_is_login2": record("2026-11-20T00:00:00Z", "2026-11-20T22:00:00Z", compiled, build="dn3", display_name="BoB"),
    "dn_too_long": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="dn4", display_name="x" * 33),
    "dn_control": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="dn5", display_name="evil‮boc"),
    "dn_and_anon": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="dn6", display_name="Ada", anonymous=True),
    "dn_nfkc": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="dn7", display_name="\uff22\uff4f\uff42"),
    "dn_padded": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="dn9", display_name="  Grace H.  "),
    "dn_blank": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="dn10", display_name="   "),
    "anon_ok": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="dn8", anonymous=True),
    "zed_is_carol": record("2026-11-21T06:00:00Z", "2026-11-21T10:00:00Z", compiled[:500], build="zed", display_name="Carol"),
    "dn_fake_anon": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="dn11", display_name="Anonymous Ada"),
    "level2_sign": record("2026-11-18T00:00:00Z", "2026-11-19T22:00:00Z", range(rb.N), whole_proof=True, axioms=AX,
                          build="lv2", **EXP, sign_statement=True),
    "export_wrong": record("2026-11-18T00:00:00Z", "2026-11-19T22:00:00Z", range(rb.N), whole_proof=True, axioms=AX,
                           build="lv3", export_sha256="ab" * 32, export_bytes=rb.REF_EXPORT_BYTES),
    "export_bytes_wrong": record("2026-11-18T00:00:00Z", "2026-11-19T22:00:00Z", range(rb.N), whole_proof=True, axioms=AX,
                                 build="lv4", export_sha256=rb.REF_EXPORT_SHA256, export_bytes=61_570_595_787),
    "export_not_whole": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="lv5", **EXP),
    "sign_level1": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, build="lv6", sign_statement=True),
    "sign_whole_no_export": record("2026-11-18T00:00:00Z", "2026-11-19T22:00:00Z", range(rb.N), whole_proof=True, axioms=AX,
                                   build="lv7", sign_statement=True),
    "checker_malformed": record("2026-11-18T00:00:00Z", "2026-11-19T22:00:00Z", range(rb.N), whole_proof=True, axioms=AX,
                                build="lv8", **EXP, checkers=[{"name": "nanoda", "result": "ok"}]),
    "checker_rejects": record("2026-11-18T00:00:00Z", "2026-11-19T22:00:00Z", range(rb.N), whole_proof=True, axioms=AX,
                              build="lv9", **EXP, checkers=[{"name": "con-leche", "version": "1.0", "result": "reject", "seconds": 9}]),
    "unknown_tool": record("2026-11-20T00:00:00Z", "2026-11-20T20:00:00Z", compiled, tool="riemann-at-home 9.9.9", build="mallory"),
}
LOGIN = {"level2_sign": "lv", "export_wrong": "lv", "export_bytes_wrong": "lv", "export_not_whole": "lv", "sign_level1": "lv",
         "sign_whole_no_export": "lv", "checker_malformed": "lv", "checker_rejects": "lv", "zed_is_carol": "zed", "anon_ok": "anon", "dn_ok": "ada", "dn_own_login": "alice", "dn_is_login": "x1", "dn_is_login2": "x1",
         "dn_too_long": "x2", "dn_control": "x3", "dn_and_anon": "x4", "dn_nfkc": "x5", "dn_padded": "x6", "dn_blank": "x7", "dn_fake_anon": "x8", "bad_count": "grace", "wrong_archive": "frank", "whole_no_axioms": "heidi", "whole_partial": "ivan",
         "bad_digest": "judy", "unknown_tool": "mallory", "carol_whole": "carol", "dave_fast": "dave", "eve_too_fast": "eve"}
login_of = lambda k: LOGIN.get(k) or k.split("_")[0].rstrip("0123456789").removesuffix("B")

# check tests: versions/<name>.json + index.json name -> {file, path}
index = {}
for k, r in R.items():
    index[k] = {"file": str(save(f"check/versions/{k}.json", r).relative_to(BOT)), "path": repo_path(login_of(k), r)}
index["build_A"], index["build_B"] = bid(A), bid(B)
# a real record written by the volunteer CLI (copy of v1/cli/tmp/sample-real-record.json), and a sorryAx whole proof
real = json.loads((BOT / "tests/real-cli-record.json").read_text())
index["real_cli"] = {"file": str(save("check/versions/real_cli.json", real).relative_to(BOT)), "path": repo_path("volunteer", real)}
for k, r in {"whole_sorry": record("2026-11-18T00:00:00Z", "2026-11-19T22:00:00Z", range(rb.N), whole_proof=True,
                                   axioms=AX + ["sorryAx"], build="sorry"),
             "whole_dup_axioms": record("2026-11-18T00:00:00Z", "2026-11-19T22:00:00Z", range(rb.N), whole_proof=True,
                                        axioms=["Quot.sound", "propext", "Classical.choice", "propext"], build="dup"),
             "whole_reordered": record("2026-11-18T00:00:00Z", "2026-11-19T22:00:00Z", range(rb.N), whole_proof=True,
                                       axioms=["Quot.sound", "propext", "Classical.choice"], build="reorder"),
             "regzipped": None}.items():
    if k == "regzipped":          # same bits, different gzip bytes (level 1, other mtime) + keys in another order
        import gzip as _gz, base64 as _b64
        r = dict(reversed(list(R["alice2"].items())))
        raw = _gz.decompress(_b64.b64decode(r["bitmap_b64"]))
        r["bitmap_b64"] = _b64.b64encode(_gz.compress(raw, compresslevel=1, mtime=12345)).decode()
        r["recorded"] = "2026-11-20T09:00:00Z"
        assert r["bitmap_b64"] != R["alice2"]["bitmap_b64"]
    index[k] = {"file": str(save(f"check/versions/{k}.json", r).relative_to(BOT)), "path": repo_path(k.split("_")[0], r)}
(FX / "check/index.json").write_text(json.dumps(index, indent=1) + "\n")

# sample: merged builds (main) + accepted versions of open PRs (open) -> sample-data.json; 5 fake people
for k in ["carol_whole", "bob_final"]:
    save(f"sample/main/{login_of(k)}/{R[k]['build_id']}.json", R[k])
f = record("2026-11-17T00:00:00Z", "2026-11-20T06:00:00Z", range(rb.N), whole_proof=True, axioms=AX,
           busy_seconds=230000, build="frank-epyc", **EXP, sign_statement=True)   # 2nd whole proof (Level 2, signs):
                                                     # started before carol, finished after
f["machine"] = {"os": "Linux 6.8.0", "arch": "x86_64", "cpu": "AMD EPYC 9654", "cores": 96}
save(f"sample/main/frank/{f['build_id']}.json", f)
# display names: alice's newest record names her; dave and a later joiner (extra/) show their logins
save(f"sample/open/alice/{R['alice2']['build_id']}.json", R["alice2"])
save(f"sample/open/alice/{R['aliceB2']['build_id']}.json", {**R["aliceB2"], "display_name": "Alice L."})
save(f"sample/open/dave/{R['dave_fast']['build_id']}.json", R["dave_fast"])
save(f"sample/extra/erin/{R['erin']['build_id']}.json", {**R["erin"], "started": "2026-11-16T00:00:00Z",
                                                         "busy_seconds": 3600})

# poll: rounds of open PRs (one PR per build, head = current version of the file)
for k, r in R.items():
    save(f"poll/versions/{k}.json", r)
def pr(number, author, k, login=None, extra_files=(), head=None, modified=False):
    rp = repo_path(login or author, R[k])
    files = [{"path": rp, "changeType": "MODIFIED" if modified else "ADDED"}] + [{"path": x, "changeType": "MODIFIED"} for x in extra_files]
    return {"number": number, "author": author, "branch": f"rah/{R[k]['build_id']}", "head": head or f"{number}-{k}",
            "files": files, "content_file": f"versions/{k}.json"}
OPEN5 = [pr(1, "alice", "alice4_shrink"), pr(2, "alice", "aliceB_shrink"), pr(6, "eve", "eve_too_fast"),
         pr(7, "dave", "dave_fast"), pr(10, "erin", "erin")]
rounds = [
    {"now": "2026-11-20T00:00:00Z", "prs": [
        pr(1, "alice", "alice1"), pr(2, "alice", "aliceB1"), pr(3, "carol", "carol_whole"),
        pr(4, "mallory", "bob", login="bob"),                       # files under bob's folder: close
        pr(5, "dave", "dave_fast", extra_files=["data.json"]),      # touches data.json too: close
        pr(9, "alice", "alice1", head="9-dup")]},                   # 2nd PR for build A: close
    {"now": "2026-11-20T09:00:00Z", "prs": [pr(1, "alice", "alice2"), pr(2, "alice", "aliceB1")]},
    {"now": "2026-11-21T10:30:00Z", "prs": [
        pr(1, "alice", "alice3_shrink"), pr(2, "alice", "aliceB2"), pr(6, "eve", "eve_too_fast"),
        pr(7, "dave", "dave_fast"), pr(8, "bob", "bob_final")]},
    {"now": "2026-11-21T10:35:00Z", "prs": [
        pr(1, "alice", "alice4_shrink"), pr(2, "alice", "aliceB_shrink"), pr(6, "eve", "eve_too_fast"),
        pr(7, "dave", "dave_fast"), pr(10, "erin", "erin"),
        pr(11, "zed", "zed_is_carol")]},                            # display_name = carol's login: reject
    {"now": "2026-11-21T10:45:00Z", "prs": [
        pr(1, "alice", "alice4_shrink"), pr(2, "alice", "aliceB_shrink"), pr(6, "eve", "eve_too_fast"),
        pr(7, "dave", "dave_fast"), pr(10, "erin", "erin")]},
    # a week later: nothing merges by time (abandoned PRs stay open); a 2nd PR for bob's merged final build is closed
    {"now": "2026-11-28T10:32:00Z", "prs": OPEN5 + [pr(12, "bob", "bob_after_final", modified=True)]},
    # run with --lose-state: the bot restores its newest backup (the shrunken head stays rejected)
    {"now": "2026-11-28T10:45:00Z", "prs": OPEN5},
    # run with --lose-state --lose-backups: no backup either, so heads are re-checked as first versions
    {"now": "2026-11-28T11:00:00Z", "prs": OPEN5},
]
(FX / "poll/rounds.json").write_text(json.dumps(rounds, indent=1) + "\n")
print("fixtures written to", FX)
