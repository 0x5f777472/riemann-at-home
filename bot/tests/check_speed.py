"""Speed limit: a real 24-core build (PR #18, 2026-11-23) went 2,100-2,200 modules per 10 minutes, about 545/h per
core, and was rejected every other update. Honest bursts like that must pass; a record claiming far more must not."""
import json, contextlib, io
from datetime import timedelta
from importlib.machinery import SourceFileLoader
rb = SourceFileLoader("rahbot", "rahbot").load_module()
idx = json.load(open("tests/fixtures/check/index.json"))
prev = json.load(open(idx["real_cli"]["file"])); path = idx["real_cli"]["path"]
have = set(rb.indices(rb.decode_bitmap(prev["bitmap_b64"])))
spare = [i for i in range(len(rb.modules())) if i not in have]
def rejects(new, minutes, cores):
    raw = rb.bits_from_indices(sorted(have | set(spare[:new])))
    t = rb.parse_ts(prev["recorded"]) + timedelta(minutes=minutes)
    rec = {**prev, "bitmap_b64": rb.encode_bitmap(raw), "modules_compiled": rb.popcount(raw),
           "recorded": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "machine": {**prev["machine"], "cores": cores}}
    with contextlib.redirect_stdout(io.StringIO()):
        return [r for r in rb.check_record(rec, "volunteer", path, prev, now=t + timedelta(minutes=1))[0]]
assert rejects(2204, 10, 24) == [], rejects(2204, 10, 24)          # PR #18's fastest honest burst
assert rejects(2000, 10, 1) == [], rejects(2000, 10, 1)            # small machine, a burst of tiny modules
assert any("speed implausible" in r for r in rejects(6000, 10, 24)), "36,000/h on 24 cores must be rejected"
assert any("speed implausible" in r for r in rejects(12914, 10, 18)), "the fixture cheat must still be rejected"
print("speed limit: honest fast bursts pass, impossible ones don't  ok")
