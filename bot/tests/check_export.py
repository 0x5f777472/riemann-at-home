"""Export progress on the page data: an exporting whole build is listed in running with its progress; once done,
`matches` comes from the bot's own Level 2 check, never from the record."""
import json, tempfile, shutil, contextlib, io
from importlib.machinery import SourceFileLoader
from pathlib import Path
rb = SourceFileLoader("rahbot", "rahbot").load_module()
idx = json.load(open("tests/fixtures/check/index.json"))
d = Path(tempfile.mkdtemp())
try:
    r = json.load(open(idx["carol_exporting"]["file"]))
    p = d / "open" / "carol" / f"{r['build_id']}.json"; p.parent.mkdir(parents=True); p.write_text(json.dumps(r))
    with contextlib.redirect_stdout(io.StringIO()): data = rb.build_data([d / "open"])
    run = [e for e in data["running"] if e["who"] == "carol"]; row = [x for x in data["leaderboard"] if x["who"] == "carol"][0]
    assert run and run[0]["export"]["bytes"] == 22_800_000_000 and not run[0]["export"]["done"], run
    assert row["export"]["left_seconds"] == 6000 and "matches" not in row["export"], row
    r["export_progress"] = {**r["export_progress"], "done": True, "bytes": rb.REF_EXPORT_BYTES, "left_seconds": None}
    p.write_text(json.dumps(r))
    with contextlib.redirect_stdout(io.StringIO()): data = rb.build_data([d / "open"])
    row = [x for x in data["leaderboard"] if x["who"] == "carol"][0]
    assert not [e for e in data["running"] if e["who"] == "carol"], "a finished export leaves Running now"
    assert row["export"]["matches"] is True and row["export"]["left_seconds"] is None, row
    print("export view ok:", row["export"])
finally:
    shutil.rmtree(d)
