"""Crash reports (a Lean segfault the tool restarted): accepted when well formed, rejected otherwise, and gathered
on the page data by module so we can see which module crashes and on whose computers."""
import json, tempfile, shutil, contextlib, io
from importlib.machinery import SourceFileLoader
from pathlib import Path
rb = SourceFileLoader("rahbot", "rahbot").load_module()
idx = json.load(open("tests/fixtures/check/index.json"))
base = json.load(open(idx["real_cli"]["file"])); path = idx["real_cli"]["path"]
crash = {"module": "Formalism.Big.Final", "code": 139, "at": base["recorded"]}
def rejects(rec):
    with contextlib.redirect_stdout(io.StringIO()):
        return rb.check_record(rec, "volunteer", path, None)[0]
assert rejects({**base, "crashes": [crash]}) == [], rejects({**base, "crashes": [crash]})
for bad in ([{**crash, "code": "139"}], [{**crash, "extra": 1}], [{**crash, "module": "two words"}],
            [{**crash, "at": "yesterday"}], [crash] * 21, "Formalism.Big.Final"):
    assert rejects({**base, "crashes": bad}), bad
d = Path(tempfile.mkdtemp())
try:
    for who, n in (("alice", 2), ("bob", 1)):
        r = {**base, "crashes": [crash] * n}
        p = d / "open" / who / f"{r['build_id']}.json"; p.parent.mkdir(parents=True); p.write_text(json.dumps(r))
    with contextlib.redirect_stdout(io.StringIO()): data = rb.build_data([d / "open"])
    assert data["crashes"] == [{"module": "Formalism.Big.Final", "codes": [139], "names": ["alice", "bob"],
                                "times": 3, "last": base["recorded"]}], data["crashes"]
    print("crash reports: checked and gathered by module  ok")
finally:
    shutil.rmtree(d)
