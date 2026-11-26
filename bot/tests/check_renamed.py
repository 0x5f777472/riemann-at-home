"""A renamed GitHub account: its old submissions/<old-login>/ folder must count as the new login (one row), and a PR
whose files sit under the old login must still pass the path == author check."""
import json, shutil, sys, tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

rb = SourceFileLoader("rahbot", str(Path(__file__).resolve().parent.parent / "rahbot")).load_module()
src = Path(__file__).resolve().parent / "fixtures" / "sample"
tmp = Path(tempfile.mkdtemp())
main = tmp / "main"
shutil.copytree(src / "main", main)
# bob renamed his account to bob-new and kept building: one build under each login
shutil.copytree(main / "bob", main / "bob-new")
f = next((main / "bob-new").glob("*.json")); rec = json.loads(f.read_text())
rec["build_id"] = "0123456789abcdef"; f.rename(f.with_name("0123456789abcdef.json"))
(main / "bob-new" / "0123456789abcdef.json").write_text(json.dumps(rec))
if hasattr(rb, "RENAMED"):
    rb.RENAMED.clear(); rb.RENAMED["bob"] = "bob-new"
rows = [r["who"] or r["name"] for r in rb.build_data([main])["leaderboard"]]
print("  rows:", rows)
assert "bob" not in rows and rows.count("bob-new") == 1, "a renamed account shows up twice"
pr = {"files": [{"path": "submissions/bob/81b637d8fcd2c6da.json"}], "author": "bob-new", "number": 1}
prob = rb.identity_problem(pr, tmp / "empty-repo", {})[0]
assert not prob or "author" not in prob, f"an old-login PR is refused: {prob}"
shutil.rmtree(tmp)
