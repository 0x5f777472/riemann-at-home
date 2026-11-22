"""Tests for the riemann-at-home volunteer CLI.

  python3 -I tests/test_cli.py            fast tests + read-only tests on the real build folder
  RAH_SLOW=1 python3 -I tests/test_cli.py also: setup from parts and from the archive, build start/pause/resume/stop

Nothing here writes to the real build folder or to GitHub.
"""
import base64, getpass, gzip, hashlib, importlib.machinery, importlib.util, json, os, re, shutil, socket
import contextlib, io, subprocess, sys, tempfile, time, unittest, unittest.mock
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
SCRIPT = CLI_DIR / "riemann-at-home"
TMP = CLI_DIR / "tmp"
loader = importlib.machinery.SourceFileLoader("rah", str(SCRIPT))
spec = importlib.util.spec_from_loader("rah", loader)
rah = importlib.util.module_from_spec(spec)
loader.exec_module(rah)

REAL = Path(rah.FIXED_FOLDERS.get(os.uname().sysname, "/nonexistent"))
SLOW = os.environ.get("RAH_SLOW") == "1"
SETUP_FOLDER = TMP / "setup-test/riemann-at-home/lean"   # made by the slow setup test (or by hand)
ARCHIVE = Path.home() / "rh-lean/replay/lean.tar.gz"
PARTS = Path.home() / "rh-lean/replay/parts"


def cli(*args, home, check=True, timeout=600):
    env = {**os.environ, "RAH_HOME": str(home), "RAH_SAMPLE_SECONDS": "2"}
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                       env=env, timeout=timeout)
    if check and r.returncode != 0:
        raise AssertionError(f"exit {r.returncode}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}")
    return r


def personal_strings():
    """Things that must never appear in a build record."""
    out = {getpass.getuser(), str(Path.home()), socket.gethostname().split(".")[0]}
    for k in ("user.email", "user.name"):
        v = subprocess.run(["git", "config", k], capture_output=True, text=True).stdout.strip()
        if v:
            out.add(v)
    return {s for s in out if s and len(s) >= 3}


def assert_private(tc, rec_text):
    for s in personal_strings():
        tc.assertNotIn(s.lower(), rec_text.lower(), f"personal string {s!r} leaked into the record")
    rec = json.loads(rec_text)
    tc.assertNotRegex(rec_text, r"[\w.+-]+@[\w-]+\.[\w.]+", "something email-shaped in the record")
    paths = re.findall(r'"(/[^"]*)"', rec_text)
    tc.assertTrue(all(p in rah.FIXED_FOLDERS.values() for p in paths), f"paths in record: {paths}")
    tc.assertEqual([k for k in rec if k not in rah.OPTIONAL_KEYS], rah.RECORD_KEYS)


def fake_folder(root: Path, n=20, compiled=(0, 3, 7, 8, 9, 15, 19), olean_only=(5,)):
    """A miniature project: n modules, some compiled (olean+trace), one interrupted (olean only)."""
    (root / "src/A/B").mkdir(parents=True)
    (root / "lean-toolchain").write_text(rah.TOOLCHAIN + "\n")
    (root / "lake-manifest.json").write_text(json.dumps({"packages": [{"name": "mathlib", "rev": rah.MATHLIB_REV}]}))
    mods = []
    for i in range(n):
        m = f"A.B.M{i:02d}" if i % 2 else f"A.N{i:02d}"
        mods.append(m)
        (root / "src" / (m.replace(".", "/") + ".lean")).write_text(f"-- {m}\n")
    lib = root / ".lake/build/lib/lean"
    for i in set(compiled) | set(olean_only):
        p = lib / (mods[i].replace(".", "/") + ".olean")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(f"olean of {mods[i]}".encode())
        if i in compiled:
            p.with_suffix(".trace").write_text("{}")
    return sorted(mods, key=lambda m: m.encode())


class Fast(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=TMP, prefix="t-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bitmap_lsb_first_gzip_base64(self):
        bits = [True] + [False] * 8 + [True]          # bit 0 and bit 9
        b64 = rah.encode_bitmap(bits)
        self.assertEqual(gzip.decompress(base64.b64decode(b64)), bytes([0x01, 0x02]))
        self.assertEqual(rah.decode_bitmap(b64, 10), bits)
        self.assertEqual(b64, rah.encode_bitmap(bits), "gzip output must be deterministic (mtime 0)")
        full = rah.encode_bitmap([True] * rah.N_MODULES)
        self.assertEqual(len(gzip.decompress(base64.b64decode(full))), 21899)

    def test_compiled_needs_trace(self):
        mods = fake_folder(self.tmp / "p")
        done = rah.compiled_modules(self.tmp / "p/.lake/build/lib/lean")
        self.assertEqual(len(done), 7)
        self.assertNotIn("A.B.M05", done)               # .olean without .trace = interrupted

    def test_module_order_bytewise(self):
        (self.tmp / "src/a").mkdir(parents=True)
        for n in ("Zeta", "alpha", "a/b", "A_b", "Ä"):
            (self.tmp / "src" / f"{n}.lean").write_text("")
        self.assertEqual(rah.all_modules(self.tmp), ["A_b", "Zeta", "a.b", "alpha", "Ä"])

    def test_busy_seconds_with_pauses_and_crash(self):
        logs = self.tmp / "logs"; logs.mkdir()
        ctx = rah.Ctx(type("A", (), {"folder": str(self.tmp), "logs": str(logs)})())
        t0 = 1_800_000_000
        I = rah.iso
        ctx.status.write_text(
            f"START {I(t0)}\nPAUSE {I(t0 + 100)}\nRESUME {I(t0 + 400)}\nBUILD_EXIT=143 {I(t0 + 1000)}\n"   # 700
            f"RESTART {I(t0 + 5000)}\n"                                                                  # crash
            f"RESTART {I(t0 + 9000)}\nPAUSE {I(t0 + 9500)}\n")                                          # open, paused
        ctx.samples.write_text(f"{I(t0 + 5300)} modules=5\n{I(t0 + 5600)} modules=9\n")
        started, busy = rah.busy_seconds(ctx, running=True, now=t0 + 9900)
        self.assertEqual(started, t0)
        self.assertEqual(busy, 700 + 600 + 500)

    def test_busy_seconds_legacy_run_build_logs(self):
        logs = self.tmp / "logs"; logs.mkdir()
        ctx = rah.Ctx(type("A", (), {"folder": str(self.tmp), "logs": str(logs)})())
        ctx.status.write_text("START 2026-11-21 07:26:31 PST\n")
        ctx.samples.write_text("2026-11-21 07:31:32 oleans=10 System-wide memory free percentage: 73%\n"
                               "2026-11-21 08:36:35 oleans=3469 System-wide memory free percentage: 73%\n")
        t_start = rah.parse_time("2026-11-21 07:26:31 PST")
        end = t_start + 4365
        (logs / "build.log").write_text("x"); os.utime(logs / "build.log", (end, end))
        started, busy = rah.busy_seconds(ctx, running=False, now=end + 99999)
        self.assertEqual((started, busy), (t_start, 4365))
        self.assertEqual(len(rah.samples(ctx)), 2)

    def test_parse_axioms(self):
        out = "'riemannHypothesis' depends on axioms: [propext,\n Classical.choice,\n Quot.sound]\n'x' depends on axioms: [sorryAx]"
        self.assertEqual(rah.parse_axioms(out), rah.EXPECTED_AXIOMS)
        self.assertEqual(rah.parse_axioms("'riemannHypothesis' does not depend on any axioms"), [])
        self.assertIsNone(rah.parse_axioms("error: unknown constant"))

    def test_record_fake_folder_contract_and_privacy(self):
        mods = fake_folder(self.tmp / "p")
        home = self.tmp / "home"
        logs = home / "logs"; logs.mkdir(parents=True)
        (logs / "status.txt").write_text("START 2026-11-21T15:26:31Z\nBUILD_EXIT=0 2026-11-21T16:26:31Z\n")
        r = cli("record", "--folder", self.tmp / "p", "--test-unofficial-folder", home=home)
        out = Path(r.stdout.strip().splitlines()[-1])
        self.assertRegex(out.name, r"^\d{8}T\d{6}Z\.json$")
        text = out.read_text()
        rec = json.loads(text)
        assert_private(self, text)
        self.assertEqual(rec["format"], "rah/build/1")
        self.assertEqual(rec["tool"], "riemann-at-home 1.0.0")
        self.assertEqual(rec["build_folder"], "unofficial")
        self.assertEqual(rec["modules_compiled"], 7)
        self.assertEqual(rec["busy_seconds"], 3600)
        self.assertEqual(rec["started"], "2026-11-21T15:26:31Z")
        self.assertFalse(rec["whole_proof"]); self.assertIsNone(rec["axioms"])
        self.assertEqual(set(rec["machine"]), {"os", "arch", "cpu", "cores"})
        bits = rah.decode_bitmap(rec["bitmap_b64"], len(mods))
        self.assertEqual(sum(bits), 7)
        lib = self.tmp / "p/.lake/build/lib/lean"
        h = hashlib.sha256()
        for m, on in zip(mods, bits):
            if on:
                h.update(hashlib.sha256((lib / (m.replace(".", "/") + ".olean")).read_bytes()).digest())
        self.assertEqual(rec["olean_digest"], h.hexdigest())
        self.assertRegex(rec["build_id"], r"^[0-9a-f]{16}$")
        # a second record reuses the hash cache and gives the same digest, and keeps the build_id
        r2 = cli("record", "--folder", self.tmp / "p", "--test-unofficial-folder", home=home)
        rec2 = json.loads(Path(r2.stdout.strip().splitlines()[-1]).read_text())
        self.assertEqual(rec2["olean_digest"], h.hexdigest())
        self.assertEqual(rec2["build_id"], rec["build_id"])
        self.assertNotEqual(rah.Ctx(type("A", (), {"folder": None, "logs": None})()).build_id(create=False), rec["build_id"])

    def test_record_whole_proof_reads_axioms(self):
        fake_folder(self.tmp / "p", n=4, compiled=(0, 1, 2, 3), olean_only=())
        home = self.tmp / "home"; (home / "logs").mkdir(parents=True)
        (home / "logs/axioms.log").write_text("'riemannHypothesis' depends on axioms: [propext, Classical.choice, Quot.sound]\n")
        r = cli("record", "--folder", self.tmp / "p", "--test-unofficial-folder", home=home)
        rec = json.loads(Path(r.stdout.strip().splitlines()[-1]).read_text())
        self.assertTrue(rec["whole_proof"]); self.assertEqual(rec["axioms"], rah.EXPECTED_AXIOMS)
        self.assertFalse(rec["final"])

    def test_finish_writes_final_record(self):
        fake_folder(self.tmp / "p")
        r = cli("finish", "--folder", self.tmp / "p", "--test-unofficial-folder", home=self.tmp / "h")
        out = Path([l for l in r.stdout.splitlines() if l.endswith(".json")][-1])
        rec = json.loads(out.read_text())
        self.assertTrue(rec["final"]); self.assertEqual(list(rec), rah.RECORD_KEYS)
        self.assertIn("submit it with", r.stdout)

    def test_record_refuses_other_folders_and_toolchains(self):
        fake_folder(self.tmp / "p")
        r = cli("record", "--folder", self.tmp / "p", home=self.tmp / "h", check=False)
        self.assertEqual(r.returncode, 1); self.assertIn("fixed folder", r.stderr)
        (self.tmp / "p/lean-toolchain").write_text("leanprover/lean4:v4.33.0\n")
        r = cli("record", "--folder", self.tmp / "p", "--test-unofficial-folder", home=self.tmp / "h", check=False)
        self.assertEqual(r.returncode, 1); self.assertIn("expected leanprover/lean4:v4.33.1", r.stderr)
        self.assertFalse((self.tmp / "h/records").exists() and any((self.tmp / "h/records").iterdir()))

    def test_prebuilt_folder_speed_and_started(self):
        """Resuming a folder that already had modules: speed counts only modules built while measured, and the
        record's `started` reaches back to the first finished module so the bot's rate check passes."""
        fake_folder(self.tmp / "p", n=40, compiled=tuple(range(30)), olean_only=())
        lib = self.tmp / "p/.lake/build/lib/lean"
        old = time.time() - 30 * 86400              # pre-existing modules finished a month ago
        for f in lib.rglob("*.trace"):
            os.utime(f, (old, old))
        home = self.tmp / "h"; logs = home / "logs"; logs.mkdir(parents=True)
        now = time.time(); I = rah.iso
        logs.joinpath("status.txt").write_text(f"START {I(now - 20)}\n")
        logs.joinpath("samples.txt").write_text(f"{I(now - 20)} modules=30\n")
        logs.joinpath("build.pid").write_text(str(os.getpid()))   # not a supervisor: counts as stopped
        st = cli("status", "--folder", self.tmp / "p", home=home).stdout
        self.assertNotIn("modules/hour", st, st)    # 30 old modules / 20 s must not show up as a speed
        ctx = rah.Ctx(type("A", (), {"folder": str(self.tmp / "p"), "logs": str(logs)})())
        self.assertIsNone(rah.rate_per_hour(ctx))
        # 6 new modules over the next 30 minutes -> 12/hour; old modules still don't count
        logs.joinpath("samples.txt").write_text(f"{I(now - 1800)} modules=30\n{I(now - 900)} modules=33\n{I(now)} modules=36\n")
        logs.joinpath("status.txt").write_text(f"START {I(now - 1800)}\n")
        self.assertAlmostEqual(rah.rate_per_hour(ctx), 12, places=3)
        self.assertEqual(rah.built_by_this_tool(ctx), 6)
        # an earlier session's samples are not mixed into the current one
        logs.joinpath("status.txt").write_text(f"START {I(now - 9000)}\nBUILD_EXIT=143 {I(now - 8000)}\nRESTART {I(now - 1800)}\n")
        logs.joinpath("samples.txt").write_text(f"{I(now - 8900)} modules=2\n{I(now - 8100)} modules=20\n"
                                                f"{I(now - 1800)} modules=30\n{I(now)} modules=36\n")
        self.assertAlmostEqual(rah.rate_per_hour(ctx), 12, places=3)
        self.assertEqual(rah.built_by_this_tool(ctx), 18 + 6)
        # record: started = first finished module (a month ago), so 30 modules / 30 days is a plausible rate
        logs.joinpath("status.txt").write_text(f"START {I(now - 20)}\n")
        r = cli("record", "--folder", self.tmp / "p", "--test-unofficial-folder", home=home)
        rec = json.loads(Path(r.stdout.strip().splitlines()[-1]).read_text())
        span = rah.parse_time(rec["recorded"]) - rah.parse_time(rec["started"])
        self.assertGreater(span, 29 * 86400)
        self.assertLess(rec["modules_compiled"] / (span / 3600), 6000, "bot would flag this honest first record")
        self.assertLessEqual(rec["busy_seconds"], span)

    def test_page_serves_from_own_files(self):
        fake_folder(self.tmp / "p")
        home = self.tmp / "h"; (home / "logs").mkdir(parents=True)
        (home / "logs/build.log").write_text("✔ [1/9] Built A.N00 (24s)\n✔ [2/9] Built A.B.M03 (805ms)\n"
                                             "✔ [3/9] Built A.N08 (1m 3s)\n✔ [4/9] Built A.N08:c.o (1s)\n")
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        env = {**os.environ, "RAH_HOME": str(home)}
        p = subprocess.Popen([sys.executable, "-I", str(SCRIPT), "page", "--folder", str(self.tmp / "p"), "--port", str(port)],
                             env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            import urllib.request, urllib.error
            base = f"http://127.0.0.1:{port}"
            for _ in range(100):
                try:
                    urllib.request.urlopen(base + "/data.json", timeout=1); break
                except OSError:
                    time.sleep(0.1)
            html = urllib.request.urlopen(base + "/").read().decode()
            self.assertIn("Riemann@home", html); self.assertNotIn("rhcheck", html)
            d = json.loads(urllib.request.urlopen(base + "/data.json").read())
            self.assertEqual(d["terrain"]["n"], 20); self.assertEqual(d["terrain"]["local_compiled"], 7)
            self.assertEqual([x[0] for x in d["terrain"]["libraries"]], ["A"])
            live = json.loads(urllib.request.urlopen(base + "/live.json").read())
            self.assertEqual(live["compiled"], 7); self.assertFalse(live["running"])
            times = json.loads(urllib.request.urlopen(base + "/times.json").read())
            self.assertEqual(times, {"A.N00": 24.0, "A.B.M03": 0.8, "A.N08": 63.0})
            req = lambda hdr: urllib.request.Request(base + "/mode", data=b'{"mode": "paused"}', method="POST", headers=hdr)
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req({"Content-Type": "application/json"}))
            self.assertEqual(e.exception.code, 403)                 # no header: refused
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req({"X-Riemann-At-Home": "1", "Host": f"evil.example:{port}"}))
            self.assertEqual(e.exception.code, 403)                 # other host: refused
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req({"X-Riemann-At-Home": "1", "Host": f"localhost:{port}"}))
            self.assertEqual(e.exception.code, 409)                 # no build of ours running
        finally:
            p.terminate(); p.wait(5)

    def test_status_fake(self):
        fake_folder(self.tmp / "p")
        r = cli("status", "--folder", self.tmp / "p", home=self.tmp / "h")
        self.assertIn("7 / 175,187 modules", r.stdout)
        self.assertIn("not started yet", r.stdout)

    def test_build_refuses_when_disk_low(self):
        fake_folder(self.tmp / "p")
        env_cli = lambda *a: subprocess.run([sys.executable, "-I", str(SCRIPT), *map(str, a)], capture_output=True,
                                            text=True, env={**os.environ, "RAH_HOME": str(self.tmp / "h"),
                                                            "RAH_MIN_FREE_GB": "1e9"}, timeout=120)
        r = env_cli("build", "--folder", self.tmp / "p")
        self.assertEqual(r.returncode, 1); self.assertIn("GB free on the build disk", r.stderr)
        self.assertIn("record` and `submit` still work", r.stderr)
        # the background supervisor checks too, and stops before starting lake
        r = env_cli("_run", "--folder", self.tmp / "p", "--logs", self.tmp / "h/logs")
        self.assertEqual(r.returncode, 1)
        st = (self.tmp / "h/logs/status.txt").read_text()
        self.assertIn("DISK_LOW", st); self.assertIn("BUILD_EXIT=disk", st)
        self.assertFalse((self.tmp / "h/logs/build.log").exists())

    def test_submit_needs_gh_logged_in(self):
        repo = self.tmp / "repo"; repo.mkdir(); subprocess.run(["git", "init", "-q", str(repo)], check=True)
        rec = self.tmp / "rec.json"; self._valid_record(rec)
        nogh = self.tmp / "bin"; nogh.mkdir()
        os.symlink(shutil.which("git"), nogh / "git")
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), "submit", "--repo", str(repo), "--record", str(rec),
                            "--login", "x-y", "--dry-run"], capture_output=True, text=True,
                           env={**os.environ, "RAH_HOME": str(self.tmp / "h"), "PATH": str(nogh)})
        self.assertEqual(r.returncode, 1); self.assertIn("`gh` tool is not installed", r.stderr)
        fake = self.tmp / "bin/gh"; fake.write_text("#!/bin/sh\necho 'You are not logged into any GitHub hosts.' >&2; exit 1\n")
        fake.chmod(0o755)
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), "submit", "--repo", str(repo), "--record", str(rec),
                            "--login", "x-y", "--dry-run"], capture_output=True, text=True,
                           env={**os.environ, "RAH_HOME": str(self.tmp / "h"), "PATH": f"{nogh}:/bin:/usr/bin"})
        self.assertEqual(r.returncode, 1); self.assertIn("run `gh auth login` yourself", r.stderr)

    def test_name_display_clear_no_anonymous(self):
        fake_folder(self.tmp / "p")
        home = self.tmp / "h"
        rec_of = lambda: json.loads(Path(cli("record", "--folder", self.tmp / "p", "--test-unofficial-folder",
                                              home=home).stdout.strip().splitlines()[-1]).read_text())
        self.assertNotIn("display_name", rec_of())
        r = cli("name", "Ada L.", home=home)
        self.assertIn(rah.NAME_NOTICE, r.stdout)
        self.assertIn("This is only a label on the Riemann@home page. Your pull request on GitHub always shows your username", r.stdout)
        rec = rec_of(); self.assertEqual(rec["display_name"], "Ada L."); self.assertNotIn("anonymous", rec)
        self.assertEqual(list(rec)[:-1], rah.RECORD_KEYS)
        self.assertNotEqual(cli("name", "--anonymous", home=home, check=False).returncode, 0)   # not offered
        cli("name", "--clear", home=home)
        rec = rec_of(); self.assertNotIn("anonymous", rec); self.assertNotIn("display_name", rec)
        for bad in ("", "x" * 33, "Anonymous #3", "ANONYMOUSLY", "anonymous", "tab\there", "new\nline", "bell\x07", "zero\u200bwidth"):
            r = cli("name", bad, home=home, check=False)
            self.assertEqual(r.returncode, 1, repr(bad)); self.assertNotIn(rah.NAME_NOTICE, r.stdout)
        self.assertEqual(cli("name", "x" * 32, home=home).returncode, 0)
        self.assertEqual(cli("name", "Not anonymous", home=home).returncode, 0)
        self.assertEqual(cli("name", "Éloïse 数学", home=home).returncode, 0)

    def test_validate_optional_name_keys(self):
        rec = self._valid_record(self.tmp / "r.json")
        self.assertEqual(rah.validate_record({**rec, "display_name": "Ada"}), [])
        self.assertTrue(rah.validate_record({**rec, "anonymous": True}))     # not offered: the PR shows the username
        self.assertTrue(rah.validate_record({**rec, "anonymous": False}))
        self.assertTrue(rah.validate_record({**rec, "display_name": "x" * 33}))
        self.assertTrue(rah.validate_record({**rec, "display_name": "Ada", "anonymous": True}))
        rp = self.tmp / "rn.json"; rp.write_text(json.dumps({**rec, "display_name": "Ada"}))
        repo = self.tmp / "repo"; repo.mkdir(); subprocess.run(["git", "init", "-q", str(repo)], check=True)
        r = cli("submit", "--repo", repo, "--record", rp, "--login", "x-y", "--dry-run", "--no-gh-check", home=self.tmp / "h")
        self.assertIn("DRY RUN", r.stdout); self.assertFalse((repo / "submissions").exists())

    def test_pause_without_build(self):
        r = cli("pause", "--folder", self.tmp, home=self.tmp / "h", check=False)
        self.assertEqual(r.returncode, 1); self.assertIn("no build is running", r.stderr)

    def _valid_record(self, path):
        bits = [i % 3 == 0 for i in range(rah.N_MODULES)]
        rec = {"format": rah.FORMAT, "tool": rah.TOOL, "archive_sha256": rah.ARCHIVE_SHA256,
               "toolchain": rah.TOOLCHAIN, "mathlib_rev": rah.MATHLIB_REV, "build_folder": str(REAL),
               "build_id": "0123456789abcdef",
               "machine": {"os": "Darwin 25.4.0", "arch": "arm64", "cpu": "Apple M5 Max", "cores": 18},
               "started": "2026-11-20T15:26:31Z", "recorded": "2026-11-21T09:10:02Z", "busy_seconds": 63000,
               "modules_compiled": sum(bits), "bitmap_b64": rah.encode_bitmap(bits), "olean_digest": "0" * 64,
               "whole_proof": False, "axioms": None, "final": False}
        path.write_text(json.dumps(rec))
        return rec

    def test_submit_dry_run_changes_nothing(self):
        repo = self.tmp / "repo"; repo.mkdir()
        g = ["git", "-C", str(repo)]
        subprocess.run(g + ["init", "-q", "-b", "main"], check=True)
        subprocess.run(g + ["remote", "add", "origin", "https://github.com/example-org/riemann-at-home.git"], check=True)
        subprocess.run(g + ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q",
                            "--allow-empty", "-m", "init"], check=True)
        before = subprocess.run(g + ["log", "--all", "--format=%H %D"], capture_output=True, text=True).stdout
        rec = self.tmp / "rec.json"; self._valid_record(rec)
        r = cli("submit", "--repo", repo, "--record", rec, "--login", "test-volunteer", "--dry-run", "--no-gh-check", home=self.tmp / "h")
        self.assertIn("DRY RUN", r.stdout)
        self.assertIn("as:     submissions/test-volunteer/0123456789abcdef.json on branch rah/0123456789abcdef", r.stdout)
        self.assertIn("gh pr create --repo example-org/riemann-at-home --head '<example-org or test-volunteer>:rah/0123456789abcdef'", r.stdout)
        self.assertIn("HEAD:refs/heads/rah/0123456789abcdef", r.stdout)
        # once the PR is open, later submits only commit + push to the same branch (no new PR)
        (self.tmp / "h").mkdir(exist_ok=True)
        (self.tmp / "h/config.json").write_text(json.dumps({"pr": {"build_id": "0123456789abcdef", "state": "open"}}))
        r = cli("submit", "--repo", repo, "--record", rec, "--login", "test-volunteer", "--dry-run", "--no-gh-check", home=self.tmp / "h")
        self.assertIn("update the open PR", r.stdout)
        self.assertNotIn("gh pr create", r.stdout)
        self.assertIn("checkout -B rah/0123456789abcdef origin/main", r.stdout); self.assertIn("push --force", r.stdout)
        self.assertFalse((repo / "submissions").exists())
        self.assertEqual(subprocess.run(g + ["status", "--porcelain"], capture_output=True, text=True).stdout, "")
        self.assertEqual(subprocess.run(g + ["log", "--all", "--format=%H %D"], capture_output=True, text=True).stdout, before)
        r = cli("submit", "--repo", repo, "--record", rec, "--login", "test-volunteer", "--no-gh-check", home=self.tmp / "h", check=False)
        self.assertEqual(r.returncode, 1); self.assertIn("only for --dry-run", r.stderr)   # never a user's checkout
        self.assertFalse((repo / "submissions").exists())

    def test_validate_matches_bot_rules(self):
        rec = self._valid_record(self.tmp / "r.json")
        self.assertEqual(rah.validate_record(rec), [])
        bad = [("recorded", "2099-01-01T00:00:00Z", "recorded <= now"), ("busy_seconds", 10 ** 6, "busy_seconds"),
               ("tool", "riemann-at-home 1.0.1", "tool"), ("build_folder", "/home/x/lean", "fixed folder"),
               ("olean_digest", "A" * 64, "lowercase"), ("extra", 1, "keys"),
               ("whole_proof", True, "whole_proof"), ("build_id", "XYZ", "build_id"), ("final", None, "final")]
        for k, v, msg in bad:
            d = dict(rec); d[k] = v
            self.assertTrue(any(msg in e for e in rah.validate_record(d)), (k, rah.validate_record(d)))
        d = dict(rec); d["machine"] = {**rec["machine"], "cores": "18"}
        self.assertTrue(rah.validate_record(d))
        raw = bytearray(gzip.decompress(base64.b64decode(rec["bitmap_b64"]))); raw[-1] |= 0x80   # bit past N-1
        d = dict(rec); d["bitmap_b64"] = base64.b64encode(gzip.compress(bytes(raw), mtime=0)).decode()
        self.assertTrue(any("past module" in e for e in rah.validate_record(d)))
        d = dict(rec); d["bitmap_b64"] = rah.encode_bitmap([False] * rah.N_MODULES); d["modules_compiled"] = 0
        self.assertTrue(any("empty" in e for e in rah.validate_record(d)))

    def _repo_with_main(self, files: dict):
        """A local 'upstream' with a main branch holding `files`, and a clone of it (origin/main = that)."""
        up = self.tmp / "upstream"; up.mkdir()
        g = ["git", "-C", str(up)]; idn = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run(g + ["init", "-q", "-b", "main"], check=True)
        for rel, text in files.items():
            (up / rel).parent.mkdir(parents=True, exist_ok=True); (up / rel).write_text(text)
        subprocess.run(g + ["add", "-A"], check=True)
        subprocess.run(g + idn + ["commit", "-q", "--allow-empty", "-m", "main"], check=True)
        clone = self.tmp / "clone"
        subprocess.run(["git", "clone", "-q", str(up), str(clone)], check=True)
        return clone

    def test_submit_one_pr_for_life_nothing_after_merge(self):
        rec = self.tmp / "rec.json"; d = self._valid_record(rec)
        rel = "submissions/test-volunteer/0123456789abcdef.json"
        sub = lambda clone: cli("submit", "--repo", clone, "--record", rec, "--login", "test-volunteer", "--dry-run",
                                "--no-gh-check", home=self.tmp / "h", check=False)
        # nothing on main yet: open the one PR, on branch rah/<build_id> (no follow-up branches exist)
        clone = self._repo_with_main({})
        r = sub(clone)
        self.assertIn("open this build's one PR", r.stdout); self.assertIn("checkout -B rah/0123456789abcdef origin/main", r.stdout)
        self.assertNotRegex(r.stdout, r"rah/0123456789abcdef-\d")
        shutil.rmtree(self.tmp / "upstream"); shutil.rmtree(clone)
        # merged (only happens when whole or final): nothing more is submitted, and the clone is untouched
        for merged in ({**d, "final": True}, {**d, "whole_proof": True, "axioms": rah.EXPECTED_AXIOMS}):
            clone = self._repo_with_main({rel: json.dumps(merged)})
            head = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
            r = sub(clone)
            self.assertEqual(r.returncode, 1); self.assertIn("nothing more is submitted", r.stderr)
            self.assertNotIn("would run", r.stdout)
            self.assertEqual(subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True).stdout, head)
            shutil.rmtree(self.tmp / "upstream"); shutil.rmtree(clone)
        # a final record already sent from this computer (PR still open): also nothing more
        clone = self._repo_with_main({})
        (self.tmp / "h").mkdir(exist_ok=True)
        (self.tmp / "h/config.json").write_text(json.dumps({"pr": {"build_id": "0123456789abcdef", "state": "open",
                                                                   "final_sent": True}}))
        r = sub(clone)
        self.assertEqual(r.returncode, 1); self.assertIn("final record was already sent", r.stderr)

    def test_submit_rejects_bad_record(self):
        repo = self.tmp / "repo"; repo.mkdir(); subprocess.run(["git", "init", "-q", str(repo)], check=True)
        rec = self.tmp / "rec.json"; d = self._valid_record(rec)
        d["modules_compiled"] += 1; rec.write_text(json.dumps(d))
        r = cli("submit", "--repo", repo, "--record", rec, "--login", "x-y", "--dry-run", "--no-gh-check", home=self.tmp / "h", check=False)
        self.assertEqual(r.returncode, 1); self.assertIn("popcount", r.stderr)


STATEMENT = ("Riemann@home: a joint statement from independent builders. We, the undersigned, each built Levent Alpöge's "
    "Lean proof of the Riemann Hypothesis (released November 20, 2026) on our own computers, from the official archive "
    "(sha256 9631b4f0…c7fc) with the pinned Lean 4.33.1 and Mathlib. Each signatory: 1. compiled all 175,187 modules "
    "(lake build Main) without errors, 2. confirmed the final theorem depends only on Lean's three standard axioms "
    "(propext, Classical.choice, Quot.sound), 3. exported the compiled proof and reproduced the same raw export file as "
    "other independent builders (sha256 5ea74b91…244e), 4. where noted, re-checked that export with an independent "
    "checker written separately from Lean's own kernel (nanoda, con-leche, lean4checker or lean4lean), named beside "
    "that signature. We do not certify the mathematics. That the statement is Mathlib's Riemann Hypothesis, and that the "
    "proved theorem is exactly that statement, was checked by the Lean and Mathlib communities "
    "(https://leanprover-community.github.io/blog/posts/riemann-hypothesis/). Each signature is the signer's own report, "
    "tied to their GitHub account. We join the Lean and Mathlib communities in congratulating Levent Alpöge.")
EXPORT_CHUNK = b'{"marker":"EXPORT-BYTES-MUST-NOT-HIT-DISK"}\n'


class Levels(unittest.TestCase):
    """export / recheck / sign with stand-in exporter and checkers (nothing real is exported or checked)."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=TMP, prefix="t-"))
        self.folder = self.tmp / "p"
        fake_folder(self.folder, n=4, compiled=(0, 1, 2, 3), olean_only=())
        self.home = self.tmp / "h"; (self.home / "logs").mkdir(parents=True)
        (self.home / "logs/axioms.log").write_text(
            "'riemannHypothesis' depends on axioms: [propext, Classical.choice, Quot.sound]\n")
        self.export = EXPORT_CHUNK * 300_000                    # ~13 MB, streamed in many chunks
        self.sha = hashlib.sha256(self.export).hexdigest()
        ex = self.tmp / "bin/fake-lean4export"; ex.parent.mkdir()
        ex.write_text(f"#!{sys.executable} -I\nimport os, sys\nassert sys.argv[1:] == ['Main'], sys.argv\n"
                      "print('cwd', os.getcwd(), file=sys.stderr)\n"
                      f"chunk = {EXPORT_CHUNK!r}\n"
                      "for _ in range(300_000): sys.stdout.buffer.write(chunk)\n")
        ex.chmod(0o755); self.exporter = ex
        self.old_env = dict(os.environ)
        os.environ["RAH_HOME"] = str(self.home)

    def tearDown(self):
        os.environ.clear(); os.environ.update(self.old_env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def main(self, *args, stdin="", ref=True):
        """Run the CLI in-process; with ref=True the stand-in export counts as the reference."""
        import contextlib, io, builtins
        from unittest import mock
        out, err = io.StringIO(), io.StringIO()
        answers = iter(stdin.splitlines())
        def fake_input(prompt=""):
            print(prompt, end="")
            try:
                return next(answers)
            except StopIteration:
                raise EOFError
        patches = [mock.patch.object(builtins, "input", fake_input)]
        if ref:
            patches += [mock.patch.object(rah, "EXPORT_SHA256", self.sha), mock.patch.object(rah, "EXPORT_BYTES", len(self.export))]
        with contextlib.ExitStack() as st:
            for p in patches:
                st.enter_context(p)
            st.enter_context(contextlib.redirect_stdout(out)); st.enter_context(contextlib.redirect_stderr(err))
            unoff = [] if args[0] == "status" else ["--test-unofficial-folder"]
            code = rah.main([*map(str, args), "--folder", str(self.folder), *unoff])
        return code, out.getvalue(), err.getvalue()

    def latest_record(self):
        return json.loads(sorted((self.home / "records").glob("*.json"))[-1].read_text())

    def assert_export_not_on_disk(self):
        for root, _, files in os.walk(self.tmp):
            for f in files:
                p = Path(root) / f
                if p.stat().st_size >= len(EXPORT_CHUNK) and b"EXPORT-BYTES-MUST-NOT-HIT-DISK" in p.read_bytes() \
                        and p != self.exporter:
                    self.fail(f"export bytes written to {p}")

    def test_statement_text_from_readme(self):
        self.assertEqual(rah.statement_text(), STATEMENT)

    def test_export_refuses_partial_build_and_failed_axioms(self):
        shutil.rmtree(self.folder); fake_folder(self.folder, n=4, compiled=(0, 1), olean_only=())
        code, out, err = self.main("export", "--exporter", self.exporter)
        self.assertEqual(code, 1); self.assertIn("needs the whole build first: 2 / ", err)
        shutil.rmtree(self.folder); fake_folder(self.folder, n=4, compiled=(0, 1, 2, 3), olean_only=())
        (self.home / "logs/axioms.log").write_text("'riemannHypothesis' depends on axioms: [propext, sorryAx]\n")
        code, out, err = self.main("export", "--exporter", self.exporter)
        self.assertEqual(code, 1); self.assertIn("passing axiom check", err)

    def test_export_mismatch_is_unverified_and_not_recorded(self):
        code, out, err = self.main("export", "--exporter", self.exporter, ref=False)
        self.assertEqual(code, 1)
        self.assertIn(f"export sha256 {self.sha}", out); self.assertIn(f"export bytes  {len(self.export):,}", out)
        self.assertIn("unverified: the reference hash has not yet been reproduced by this tool", out)
        self.assertIn(f"cwd {self.folder}", (self.home / "logs/export.log").read_text())   # ran in the build folder
        self.assert_export_not_on_disk()
        code, _, _ = self.main("record", ref=False)
        rec = self.latest_record()
        self.assertNotIn("export_sha256", rec); self.assertEqual(rah.validate_levels(rec), [])
        code, out, err = self.main("sign", stdin="y\n", ref=False)
        self.assertEqual(code, 1); self.assertIn("signing needs Level 2", err)
        self.assertNotIn("sign_statement", self.latest_record())

    def test_export_match_recheck_sign(self):
        code, out, err = self.main("export", "--exporter", self.exporter)
        self.assertEqual(code, 0, err); self.assertIn("Level 2: matches the reference", out)
        self.assertNotIn("unverified", out)
        self.assert_export_not_on_disk()
        rec = self.latest_record()
        self.assertEqual((rec["export_sha256"], rec["export_bytes"]), (self.sha, len(self.export)))
        from unittest import mock
        with mock.patch.object(rah, "EXPORT_SHA256", self.sha):
            self.assertEqual(rah.validate_levels(rec), []); self.assertEqual(rah.record_level(rec), 2)
        # Level 3: memory is checked first, before anything else
        os.environ["RAH_TEST_RAM_GB"] = "64"
        code, out, err = self.main("recheck", "--nanoda", "--checker", "/nonexistent")
        self.assertEqual(code, 1); self.assertIn("nanoda needs about 100 GB of memory; this computer has 64 GB", err)
        os.environ["RAH_TEST_RAM_GB"] = "40"
        code, out, err = self.main("recheck", "--con-leche", "--checker", "/nonexistent")
        self.assertEqual(code, 1); self.assertIn("con-leche needs about 50 GB", err)
        os.environ["RAH_TEST_RAM_GB"] = "128"
        chk = self.tmp / "bin/fake-nanoda"
        chk.write_text(f"#!{sys.executable} -I\nimport hashlib, sys\n"
                       "if sys.argv[1:] == ['--version']: print('nanoda 0.9-test'); sys.exit(0)\n"
                       f"ok = hashlib.sha256(sys.stdin.buffer.read()).hexdigest() == {self.sha!r}\n"
                       "print('checked', sys.argv[1:], ok); sys.exit(0 if ok else 3)\n")
        chk.chmod(0o755)
        code, out, err = self.main("recheck", "--nanoda", "--checker", chk, "--checker-args=--stdin",
                                   "--exporter", self.exporter)
        self.assertEqual(code, 0, err + out); self.assertIn("nanoda: ACCEPT", out)
        self.assertIn("checked ['--stdin'] True", (self.home / "logs/recheck-nanoda.log").read_text())
        self.assert_export_not_on_disk()
        rec = self.latest_record()
        self.assertEqual([(c["name"], c["version"], c["result"]) for c in rec["checkers"]], [("nanoda", "nanoda 0.9-test", "accept")])
        self.assertIsInstance(rec["checkers"][0]["seconds"], int)
        with mock.patch.object(rah, "EXPORT_SHA256", self.sha):
            self.assertEqual(rah.validate_levels(rec), []); self.assertEqual(rah.record_level(rec), 3)
        # a checker that refuses is recorded as reject (exit 1); con-leche runs at 50+ GB
        bad = self.tmp / "bin/fake-con-leche"; bad.write_text("#!/bin/sh\ncat >/dev/null; echo nope; exit 2\n"); bad.chmod(0o755)
        os.environ["RAH_TEST_RAM_GB"] = "64"
        code, out, err = self.main("recheck", "--con-leche", "--checker", bad, "--checker-version", "1.0",
                                   "--exporter", self.exporter)
        self.assertEqual(code, 1); self.assertIn("con-leche: REJECT", out)
        self.assertEqual({c["name"]: c["result"] for c in self.latest_record()["checkers"]}, {"nanoda": "accept", "con-leche": "reject"})
        # sign: shows the statement from the README, asks, and only "y" signs
        code, out, err = self.main("sign", stdin="n\n")
        self.assertEqual(code, 1); self.assertIn("not signed", out)
        self.assertIn(" ".join(STATEMENT.split()[:12]), " ".join(out.split()))
        self.assertEqual(" ".join(out.split()).count(" ".join(STATEMENT.split())), 1)
        self.assertNotIn("sign_statement", self.latest_record())
        code, out, err = self.main("sign")                        # no answer (EOF) = no
        self.assertEqual(code, 1)
        code, out, err = self.main("sign", stdin="y\n")
        self.assertEqual(code, 0, err); self.assertIn("Sign this statement? [y/N]", out)
        rec = self.latest_record(); self.assertIs(rec["sign_statement"], True)
        with mock.patch.object(rah, "EXPORT_SHA256", self.sha):
            self.assertEqual(rah.validate_levels(rec), [])
        code, out, err = self.main("status")
        self.assertIn("level     3: export reproduces the reference, re-checked by nanoda, joint statement signed", out)
        # a changed build (different olean digest) does not inherit the levels
        (self.folder / ".lake/build/lib/lean/A/N00.olean").write_bytes(b"different")
        self.main("record")
        self.assertFalse(set(rah.LEVEL_KEYS) & set(self.latest_record()))

    def test_validate_level_fields(self):
        base = Fast._valid_record(None, self.tmp / "r.json")
        whole = {**base, "whole_proof": True, "axioms": list(reversed(rah.EXPECTED_AXIOMS))}
        l2 = {**whole, "export_sha256": rah.EXPORT_SHA256, "export_bytes": rah.EXPORT_BYTES}
        l3 = {**l2, "checkers": [{"name": "nanoda", "version": "0.9", "result": "accept", "seconds": 3600}],
              "sign_statement": True, "display_name": "Ada"}
        for ok, lvl in ((base, 1), (whole, 1), (l2, 2), (l3, 3), ({**l2, "sign_statement": True}, 2)):
            self.assertEqual(rah.validate_record(ok), [], ok.keys()); self.assertEqual(rah.record_level(ok), lvl)
        shuffled = dict(reversed(list(l3.items())))                # keys are a set: order does not matter
        self.assertEqual(rah.validate_record(shuffled), [])
        bad = [({**l2, "export_sha256": "0" * 64}, "export does not reproduce the reference"),
               ({**base, "export_sha256": rah.EXPORT_SHA256, "export_bytes": 1}, "need a whole proof"),
               ({**whole, "export_sha256": rah.EXPORT_SHA256}, "go together"),
               ({**l2, "export_bytes": "61570595788"}, "export_bytes"),
               ({**whole, "checkers": l3["checkers"]}, "Level 2"),
               ({**l2, "checkers": []}, "non-empty"),
               ({**l2, "checkers": [{"name": "nanoda", "result": "accept", "seconds": 1}]}, "checkers must be"),
               ({**l2, "checkers": [{**l3["checkers"][0], "result": "maybe"}]}, "checkers must be"),
               ({**l2, "checkers": l3["checkers"] * 2}, "one entry per checker"),
               ({**whole, "sign_statement": True}, "sign_statement needs Level 2"),
               ({**l2, "sign_statement": False}, "must be true"),
               ({**l3, "anonymous": True}, "at most one")]
        for rec, msg in bad:
            errs = rah.validate_record(rec)
            self.assertTrue(any(msg in e for e in errs), (msg, errs))

    def test_record_started_stays_put(self):
        """`started` (first finished module for a pre-built folder) is kept across this build's records."""
        lib = self.folder / ".lake/build/lib/lean"
        old = time.time() - 7200
        for f in lib.rglob("*.trace"):
            os.utime(f, (old, old))
        self.main("record"); first = self.latest_record()
        self.assertEqual(first["started"], rah.iso(old))
        now = time.time()
        for f in lib.rglob("*.trace"):                              # rebuilt later: earliest trace moves forward
            os.utime(f, (now, now))
        time.sleep(1.1); self.main("record")
        self.assertEqual(self.latest_record()["started"], first["started"])


FAKE_GH = r"""#!PYTHON -I
# A stand-in for GitHub's `gh`: a local bare repo is "upstream", PRs live in a JSON file. No network.
import json, os, subprocess, sys
a = sys.argv[1:]
E = os.environ
with open(E["FAKE_GH_LOG"], "a") as f:
    f.write(json.dumps(a) + "\n")
if E.get("FAKE_GH_FAIL"):
    print("error connecting to api.github.com", file=sys.stderr); sys.exit(1)
state = json.load(open(E["FAKE_GH_STATE"])) if os.path.exists(E["FAKE_GH_STATE"]) else {"prs": []}
save = lambda: json.dump(state, open(E["FAKE_GH_STATE"], "w"))
if a[:2] == ["auth", "status"]:
    sys.exit(0)
if a[:2] == ["api", "user"]:
    print(E["FAKE_GH_LOGIN"]); sys.exit(0)
if a[0] == "api" and a[1].startswith("repos/"):
    print(E.get("FAKE_GH_PUSH", "true")); sys.exit(0)
if a[:2] == ["repo", "clone"]:
    assert a[2] == E["FAKE_GH_UPSTREAM_NAME"], a
    sys.exit(subprocess.run(["git", "clone", "-q", E["FAKE_UPSTREAM"], a[3]]).returncode)
if a[:2] == ["repo", "fork"]:
    if not os.path.exists(E["FAKE_FORK"]):
        subprocess.run(["git", "clone", "-q", "--bare", E["FAKE_UPSTREAM"], E["FAKE_FORK"]], check=True)
    sys.exit(subprocess.run(["git", "remote", "add", "fork", E["FAKE_FORK"]]).returncode)
if a[:2] == ["pr", "list"]:
    head = a[a.index("--head") + 1]
    print(json.dumps([{k: p[k] for k in ("number", "url", "state")} for p in state["prs"]
                      if p["head"].split(":")[1] == head])); sys.exit(0)
if a[:2] == ["pr", "create"]:
    g = lambda k: a[a.index(k) + 1]
    n = len(state["prs"]) + 1
    url = f"https://github.com/{g('--repo')}/pull/{n}"
    state["prs"].append({"number": n, "url": url, "state": "OPEN", "head": g("--head"), "title": g("--title"),
                         "body": g("--body"), "repo": g("--repo")})
    save(); print(url); sys.exit(0)
print("fake gh: unexpected", a, file=sys.stderr); sys.exit(2)
"""


class RealSubmit(unittest.TestCase):
    """The real submit path against a local bare repo as upstream and a fake `gh` (no network, no GitHub)."""
    BID = "0123456789abcdef"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=TMP, prefix="t-"))
        self.up = self.tmp / "upstream.git"
        seed = self.tmp / "seed"; seed.mkdir()
        self.git(seed, "init", "-q", "-b", "main")
        (seed / "README.md").write_text("upstream\n"); (seed / "submissions/someone").mkdir(parents=True)
        (seed / "submissions/someone/aaaaaaaaaaaaaaaa.json").write_text("{}\n")
        self.git(seed, "add", "-A"); self.git(seed, "commit", "-q", "-m", "init")
        subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(self.up)], check=True)
        self.seed = seed; self.git(seed, "remote", "add", "origin", str(self.up))
        bindir = self.tmp / "bin"; bindir.mkdir()
        (bindir / "gh").write_text(FAKE_GH.replace("PYTHON", sys.executable)); (bindir / "gh").chmod(0o755)
        self.home = self.tmp / "h"; self.home.mkdir()
        self.env = {**os.environ, "RAH_HOME": str(self.home), "PATH": f"{bindir}:{os.environ['PATH']}",
                    "FAKE_GH_LOG": str(self.tmp / "gh.log"), "FAKE_GH_STATE": str(self.tmp / "gh.json"),
                    "FAKE_GH_LOGIN": "test-volunteer", "FAKE_UPSTREAM": str(self.up),
                    "FAKE_GH_UPSTREAM_NAME": "riemann-at-home/riemann-at-home", "FAKE_FORK": str(self.tmp / "fork.git"),
                    "GIT_CONFIG_GLOBAL": str(self.tmp / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1"}
        (self.tmp / "gitconfig").write_text("")
        (self.home / "config.json").write_text(json.dumps({"consent": {"agreed": "2026-11-21T00:00:00Z"}}))   # said yes
        self.rec_path = self.tmp / "rec.json"
        self.rec = Fast._valid_record(None, self.rec_path)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, repo, *args):
        idn = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        return subprocess.run(["git", "-C", str(repo), *idn, *args], check=True, capture_output=True, text=True).stdout

    def submit(self, *extra, check=True, **env):
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), "submit", "--record", str(self.rec_path), *extra],
                           capture_output=True, text=True, env={**self.env, **env}, timeout=120)
        if check and r.returncode != 0:
            raise AssertionError(f"exit {r.returncode}\n{r.stdout}\n{r.stderr}")
        return r

    def gh_calls(self):
        p = self.tmp / "gh.log"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def prs(self):
        return json.loads((self.tmp / "gh.json").read_text())["prs"]

    def branch_commits(self, bare, branch=f"rah/{BID}"):
        return self.git(bare, "log", "--format=%an <%ae>|%s", f"main..{branch}").splitlines()

    def changed_files(self, bare, branch=f"rah/{BID}"):
        return self.git(bare, "diff", "--name-only", f"main...{branch}").split()

    def test_push_access_first_update_unchanged_and_main_moves(self):
        r = self.submit()
        self.assertIn("opened https://github.com/riemann-at-home/riemann-at-home/pull/1", r.stdout)
        rel = f"submissions/test-volunteer/{self.BID}.json"
        self.assertTrue((self.home / "repo/.git").exists(), "the tool's own clone")
        self.assertEqual(self.changed_files(self.up), [rel])                     # never touches anything else
        self.assertEqual(self.branch_commits(self.up),
                         [f"test-volunteer <test-volunteer@users.noreply.github.com>|update: {self.rec['modules_compiled']} modules"])
        self.assertEqual(json.loads(self.git(self.up, "show", f"rah/{self.BID}:{rel}")), self.rec)
        [pr] = self.prs()
        self.assertEqual(pr["head"], f"riemann-at-home:rah/{self.BID}")         # pushed to upstream directly
        self.assertEqual(pr["title"], f"Riemann@home build {self.BID} (test-volunteer)")
        self.assertIn("modules compiled: 58,396 / 175,187", pr["body"]); self.assertIn("Apple M5 Max", pr["body"])
        st = json.loads((self.home / "config.json").read_text())["pr"]
        self.assertEqual((st["number"], st["url"], st["state"], st["final_sent"]),
                         (1, "https://github.com/riemann-at-home/riemann-at-home/pull/1", "open", False))
        self.assertFalse((self.tmp / "fork.git").exists())
        # same record again: nothing to do (no commit, no push, no PR)
        before = self.git(self.up, "rev-parse", f"rah/{self.BID}")
        r = self.submit()
        self.assertIn("nothing new since the last push", r.stdout)
        self.assertEqual(self.git(self.up, "rev-parse", f"rah/{self.BID}"), before)
        # upstream main moves on (another merge), and the build grows: reset onto main, one commit, force-push
        (self.seed / "data.json").write_text("{}\n"); self.git(self.seed, "add", "-A")
        self.git(self.seed, "commit", "-q", "-m", "bot: data.json"); self.git(self.seed, "push", "-q", "origin", "main")
        bits = [i % 2 == 0 for i in range(rah.N_MODULES)]
        rec2 = {**self.rec, "bitmap_b64": rah.encode_bitmap(bits), "modules_compiled": sum(bits),
                "recorded": "2026-11-21T10:10:02Z"}
        self.rec_path.write_text(json.dumps(rec2))
        r = self.submit()
        self.assertIn("updated https://github.com/riemann-at-home/riemann-at-home/pull/1", r.stdout)
        self.assertEqual(self.branch_commits(self.up), [f"test-volunteer <test-volunteer@users.noreply.github.com>|update: {sum(bits)} modules"])
        self.assertEqual(self.changed_files(self.up), [rel])
        self.assertEqual(self.git(self.up, "merge-base", "main", f"rah/{self.BID}"), self.git(self.up, "rev-parse", "main"))
        self.assertEqual(len(self.prs()), 1, "one PR for the build's whole life")
        self.assertEqual(sum(1 for c in self.gh_calls() if c[:2] == ["pr", "create"]), 1)

    def test_times_only_change_pushed_at_most_every_5_min(self):
        self.submit()
        head = lambda: self.git(self.up, "rev-parse", f"rah/{self.BID}")
        first = head()
        self.rec_path.write_text(json.dumps({**self.rec, "recorded": "2026-11-21T09:20:02Z"}))   # only times changed
        r = self.submit(); self.assertIn("only times changed", r.stdout); self.assertEqual(head(), first)
        cfg = json.loads((self.home / "config.json").read_text()); cfg["pr"]["pushed_at"] -= 301
        (self.home / "config.json").write_text(json.dumps(cfg))
        r = self.submit(); self.assertIn("updated", r.stdout); self.assertNotEqual(head(), first)
        second = head()
        bits = [i % 7 == 0 for i in range(rah.N_MODULES)]                        # modules changed: push right away
        self.rec_path.write_text(json.dumps({**self.rec, "bitmap_b64": rah.encode_bitmap(bits), "modules_compiled": sum(bits)}))
        r = self.submit(); self.assertIn("updated", r.stdout); self.assertNotEqual(head(), second)

    def test_interval_setting_and_companion_for_older_build(self):
        cli_ = lambda *a: subprocess.run([sys.executable, "-I", str(SCRIPT), *a], capture_output=True, text=True,
                                         env=self.env, timeout=60)
        r = cli_("submit", "--interval", "10"); self.assertEqual(r.returncode, 1); self.assertIn("at least 30", r.stderr)
        cli_("submit", "--interval", "30")
        ctx = rah.Ctx(type("A", (), {"folder": None, "logs": None})())
        os.environ["RAH_HOME"] = str(self.home)
        try:
            ctx = rah.Ctx(type("A", (), {"folder": None, "logs": None})())
            self.assertEqual(rah.autosubmit_interval(ctx), 30)
            ctx.set_conf(submit={"interval": 5}); self.assertEqual(rah.autosubmit_interval(ctx), 30)    # minimum
            ctx.set_conf(submit={}); self.assertEqual(rah.autosubmit_interval(ctx), rah.AUTOSUBMIT_SECONDS)
        finally:
            del os.environ["RAH_HOME"]
        # a running build from an older version (no supervisor.features): enable-auto starts the interval companion
        logs = self.home / "logs"; logs.mkdir(exist_ok=True)
        sup = subprocess.Popen(["sh", "-c", f"echo $$ > {logs}/build.pid; sleep 120; true", "sh", "_run"])
        try:
            for _ in range(50):
                if (logs / "build.pid").exists() and (logs / "build.pid").read_text().strip():
                    break
                time.sleep(0.1)
            r = cli_("submit", "--enable-auto", "--interval", "30")
            self.assertIn("every 30 s", r.stdout)
            pid = int((logs / "autosubmit-loop.pid").read_text())
            self.assertTrue(rah.pid_alive(pid, "_autosubmit_loop"))
            cli_("submit", "--enable-auto")                                 # no second companion
            self.assertEqual(int((logs / "autosubmit-loop.pid").read_text()), pid)
            os.kill(pid, 15)
            # a current supervisor marks itself: no companion (it rereads the interval itself)
            (logs / "autosubmit-loop.pid").unlink()
            (logs / "supervisor.features").write_text(f"{sup.pid} autosubmit-v2\n")
            cli_("submit", "--enable-auto")
            self.assertFalse((logs / "autosubmit-loop.pid").exists())
        finally:
            sup.kill(); sup.wait()

    def test_no_push_access_uses_fork(self):
        r = self.submit(FAKE_GH_PUSH="false")
        fork = self.tmp / "fork.git"
        self.assertTrue(fork.exists())
        self.assertEqual(self.changed_files(fork), [f"submissions/test-volunteer/{self.BID}.json"])
        self.assertNotIn(f"rah/{self.BID}", self.git(self.up, "branch", "--list"))   # nothing pushed upstream
        self.assertEqual(self.prs()[0]["head"], f"test-volunteer:rah/{self.BID}")
        self.assertEqual(self.prs()[0]["repo"], "riemann-at-home/riemann-at-home")

    def test_commit_identity_only_noreply_email(self):
        (self.tmp / "gitconfig").write_text("[user]\n\tname = Ada Builder\n\temail = ada@example.com\n")
        self.submit()
        self.assertEqual(self.branch_commits(self.up)[0].split("|")[0], "Ada Builder <test-volunteer@users.noreply.github.com>")
        log = self.git(self.up, "log", "--format=%ae %ce", f"rah/{self.BID}", "-1")
        self.assertNotIn("example.com", log)
        (self.tmp / "gitconfig").write_text("[user]\n\tname = Ada Builder\n\temail = 123+ada@users.noreply.github.com\n")
        bits = [i % 5 == 0 for i in range(rah.N_MODULES)]
        self.rec_path.write_text(json.dumps({**self.rec, "bitmap_b64": rah.encode_bitmap(bits), "modules_compiled": sum(bits)}))
        self.submit()
        self.assertEqual(self.branch_commits(self.up)[0].split("|")[0], "Ada Builder <123+ada@users.noreply.github.com>")

    def test_final_then_nothing_more(self):
        self.rec_path.write_text(json.dumps({**self.rec, "final": True}))
        self.submit()
        self.assertTrue(json.loads((self.home / "config.json").read_text())["pr"]["final_sent"])
        r = self.submit(check=False)
        self.assertEqual(r.returncode, 1); self.assertIn("final record was already sent", r.stderr)

    def test_repo_flag_is_dry_run_only(self):
        r = self.submit("--repo", str(self.seed), check=False)
        self.assertEqual(r.returncode, 1); self.assertIn("only for --dry-run", r.stderr)
        self.assertFalse(self.gh_calls())

    def test_autosubmit_off_on_errors_never_fail(self):
        fake_folder(self.tmp / "p")
        run = lambda **env: subprocess.run([sys.executable, "-I", str(SCRIPT), "_autosubmit", "--folder", str(self.tmp / "p"),
                                            "--test-unofficial-folder"], capture_output=True, text=True,
                                           env={**self.env, **env}, timeout=120)
        r = run()
        self.assertEqual(r.returncode, 0); self.assertIn("auto-submit is off", r.stdout)
        self.assertFalse(self.gh_calls())
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), "submit", "--enable-auto"], capture_output=True,
                           text=True, env=self.env, timeout=60)
        self.assertIn("auto-submit on", r.stdout)
        self.assertEqual(json.loads((self.home / "config.json").read_text())["submit"],
                         {"auto": True, "upstream": "riemann-at-home/riemann-at-home"})
        # on: tries for real. Unofficial test records are refused by the record check, network errors are logged;
        # either way exit 0 so the build goes on
        r = run()
        self.assertEqual(r.returncode, 0); self.assertIn("auto-submit: ", r.stdout); self.assertIn("not a valid", r.stdout)
        r = run(FAKE_GH_FAIL="1")
        self.assertEqual(r.returncode, 0); self.assertIn("auto-submit: ", r.stdout)
        r = run(PATH="/usr/bin:/bin:/usr/sbin:/sbin")                         # gh missing
        self.assertEqual(r.returncode, 0); self.assertIn("auto-submit: ", r.stdout)
        # the real path through the same entry point, with a valid record as the latest
        recs = self.home / "records"; shutil.copy(self.rec_path, recs / "29991231T000000Z.json")
        ns = subprocess.run([sys.executable, "-I", "-c", f"""
import importlib.machinery, importlib.util, argparse, sys
l = importlib.machinery.SourceFileLoader("rah", {str(SCRIPT)!r}); s = importlib.util.spec_from_loader("rah", l)
rah = importlib.util.module_from_spec(s); l.exec_module(rah)
rah.make_record = lambda ctx, a: (_ for _ in ()).throw(rah.Fail("skip"))   # keep the valid latest record
a = argparse.Namespace(cmd="record", folder=None, logs=None, test_unofficial_folder=True)
sys.exit(rah.cmd_autosubmit(rah.Ctx(a), a))
"""], capture_output=True, text=True, env=self.env, timeout=120)
        self.assertEqual(ns.returncode, 0, ns.stderr); self.assertIn("opened https://github.com/", ns.stdout)
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), "submit", "--disable-auto"], capture_output=True,
                           text=True, env=self.env, timeout=60)
        self.assertFalse(json.loads((self.home / "config.json").read_text())["submit"]["auto"])

    def test_older_supervisor_record_call_submits_when_enabled(self):
        """A build started before `_autosubmit` existed runs `record` every 10 min; with auto on, that submits."""
        fake_folder(self.tmp / "p")
        logs = self.home / "logs"; logs.mkdir()
        (self.home / "config.json").write_text(json.dumps({"submit": {"auto": True, "upstream": "riemann-at-home/riemann-at-home"}}))
        cmd = shlex_join([sys.executable, "-I", str(SCRIPT), "record", "--folder", str(self.tmp / "p"), "--logs", str(logs),
                          "--test-unofficial-folder"])
        # a stand-in supervisor: a shell whose command line contains " _run" and whose pid is in build.pid
        r = subprocess.run(["sh", "-c", f"echo $$ > {logs}/build.pid; {cmd}; true", "sh", "_run"], capture_output=True,
                           text=True, env=self.env, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("auto-submit: ", r.stdout)                              # it tried (test record: refused)
        r = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, env=self.env, timeout=120)
        self.assertNotIn("auto-submit", r.stdout)                             # a manual `record` never submits


def shlex_join(parts):
    import shlex
    return shlex.join(map(str, parts))


@unittest.skipUnless(REAL.exists(), "no real build folder on this machine")
class RealFolderReadOnly(unittest.TestCase):
    """Reads the real build folder; never writes to it."""
    home = TMP / "real-home"

    def test_record_real_folder(self):
        shutil.rmtree(self.home, ignore_errors=True)
        legacy = Path.home() / "rh-lean/logs/shared-build"
        args = ["record"] + (["--logs", legacy] if legacy.exists() else [])
        r = cli(*args, home=self.home, timeout=3600)
        out = Path(r.stdout.strip().splitlines()[-1])
        text = out.read_text()
        assert_private(self, text)
        rec = json.loads(text)
        self.assertEqual(rec["build_folder"], str(REAL))
        bits = rah.decode_bitmap(rec["bitmap_b64"], rah.N_MODULES)
        self.assertEqual(sum(bits), rec["modules_compiled"])
        self.assertGreater(rec["modules_compiled"], 3000)
        self.assertEqual(rah.validate_record(rec), [])
        shutil.copy(out, TMP / "sample-real-record.json")

    def test_status_real_folder(self):
        r = cli("status", home=self.home)
        self.assertRegex(r.stdout, r"compiled  [\d,]+ / 175,187 modules")

    def test_build_refuses_while_outside_build_runs(self):
        ctx = rah.Ctx(type("A", (), {"folder": None, "logs": None})())
        if not rah.outside_build(ctx):
            self.skipTest("no outside build running right now")
        r = cli("build", home=TMP / "refuse-home", check=False)
        self.assertEqual(r.returncode, 1); self.assertIn("another build is already running", r.stderr)

    def test_page_once(self):
        home = TMP / "page-home"; shutil.rmtree(home, ignore_errors=True)
        r = cli("page", "--once", home=home, timeout=600)
        self.assertIn("http://localhost:8642/", r.stdout)
        d = json.loads((home / "page/data.json").read_text())
        self.assertEqual(d["terrain"]["n"], rah.N_MODULES)
        self.assertGreater(d["terrain"]["local_compiled"], 3000)
        self.assertEqual(len((home / "page/modules.txt").read_text().splitlines()), rah.N_MODULES)
        html = (home / "page/index.html").read_text()
        self.assertIn("https://riemann-at-home.github.io/riemann-at-home/", html)


@unittest.skipUnless(SLOW, "set RAH_SLOW=1")
class Slow(unittest.TestCase):
    def test_1_setup_from_parts_verifies_sha(self):
        if not PARTS.exists():
            self.skipTest("no local parts")
        home = TMP / "parts-home"; folder = TMP / "parts-test/riemann-at-home/lean"
        shutil.rmtree(home, ignore_errors=True); shutil.rmtree(TMP / "parts-test", ignore_errors=True)
        # corrupt parts: refused, nothing unpacked
        bad = TMP / "bad-parts"; bad.mkdir(exist_ok=True)
        for i in range(1, 15):
            (bad / f"part{i:02d}").write_bytes(b"not the archive")
        r = cli("setup", "--folder", folder, "--skip-cache", "--parts-url", f"file://{bad}/part{{nn}}", home=home, check=False)
        self.assertEqual(r.returncode, 1); self.assertIn("expected 9631b4f0", r.stderr)
        self.assertFalse(folder.exists())
        shutil.rmtree(home / "download"); shutil.rmtree(bad)
        # the real parts, through the same download path (file:// instead of https://alpo.ge)
        r = cli("setup", "--folder", folder, "--skip-cache", "--parts-url", f"file://{PARTS}/part{{nn}}", home=home,
                timeout=1800)
        self.assertIn("sha256 9631b4f0", r.stdout)
        self.assertEqual(len(rah.all_modules(folder)), rah.N_MODULES)
        self.assertEqual(rah.sha256_file(home / "download/lean.tar.gz"), rah.ARCHIVE_SHA256)
        shutil.rmtree(TMP / "parts-test"); shutil.rmtree(home)

    def test_2_setup_archive_idempotent(self):
        home = TMP / "home"
        if not SETUP_FOLDER.exists():
            cli("setup", "--archive", ARCHIVE, "--folder", SETUP_FOLDER, home=home, timeout=7200)
        t = time.time()
        r = cli("setup", "--archive", ARCHIVE, "--folder", SETUP_FOLDER, home=home)
        self.assertIn("already here", r.stdout); self.assertIn("already installed", r.stdout)
        self.assertIn("Mathlib compiled cache already here", r.stdout)
        self.assertLess(time.time() - t, 30)
        self.assertEqual(len(rah.all_modules(SETUP_FOLDER)), rah.N_MODULES)

    def test_3_build_start_pause_resume_stop(self):
        home = TMP / "build-home"; shutil.rmtree(home, ignore_errors=True)
        target = "Formalism.MeanHeightDescent.BadRowsNumeric"
        repo = TMP / "autosubmit-repo"; shutil.rmtree(repo, ignore_errors=True); repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        os.environ["RAH_AUTOSUBMIT_SECONDS"] = "20"          # inherited by the supervisor via cli()
        r = cli("build", "--folder", SETUP_FOLDER, "--gentle", "--target", target, "--submit-repo", repo,
                "--test-unofficial-folder", home=home)
        del os.environ["RAH_AUTOSUBMIT_SECONDS"]
        self.assertIn("in the background", r.stdout)
        ctx = rah.Ctx(type("A", (), {"folder": str(SETUP_FOLDER), "logs": str(home / "logs")})())
        pgid = rah.read_pid(ctx.pgid_file)
        for _ in range(120):
            if rah.build_pids(ctx, ("lean",)):
                break
            time.sleep(1)
        self.assertTrue(rah.build_pids(ctx, ("lake",)), "lake did not start")
        lake = rah.build_pids(ctx, ("lake",))[0]
        ni = subprocess.run(["ps", "-o", "nice=", "-p", str(lake)], capture_output=True, text=True).stdout.strip()
        self.assertEqual(ni, "19")
        self.assertIn("running, gentle", cli("status", "--folder", SETUP_FOLDER, home=home).stdout)
        r2 = cli("build", "--folder", SETUP_FOLDER, home=home)
        self.assertIn("already running", r2.stdout)
        cli("pause", "--folder", SETUP_FOLDER, home=home)
        time.sleep(1)
        states = {s for _, g, s, _ in rah.ps_table() if g == pgid}
        self.assertTrue(states and all(s.startswith("T") for s in states), states)
        self.assertIn("PAUSED", cli("status", "--folder", SETUP_FOLDER, home=home).stdout)
        cli("resume", "--folder", SETUP_FOLDER, home=home)
        time.sleep(1)
        states = {s for _, g, s, _ in rah.ps_table() if g == pgid}
        self.assertFalse(any(s.startswith("T") for s in states), states)
        cli("build", "--full", "--folder", SETUP_FOLDER, home=home)
        self.assertIn("running, full", cli("status", "--folder", SETUP_FOLDER, home=home).stdout)
        time.sleep(5)
        cli("stop", "--folder", SETUP_FOLDER, home=home)
        time.sleep(1)
        self.assertFalse([1 for _, g, _, _ in rah.ps_table() if g == pgid], "build processes left behind")
        st = cli("status", "--folder", SETUP_FOLDER, home=home).stdout
        self.assertIn("not running", st)
        status = (home / "logs/status.txt").read_text()
        for k in ("START", "PAUSE", "RESUME", "MODE_FULL", "STOP_REQUESTED", "BUILD_EXIT="):
            self.assertIn(k, status)
        self.assertTrue((home / "logs/build.log").exists())   # lake prints only when a module finishes
        self.assertFalse((home / "logs/build.pid").exists())
        log = (home / "logs/autosubmit.log").read_text()
        self.assertIn("--- autosubmit (progress)", log)
        self.assertFalse((repo / "submissions").exists(), "autosubmit must stay a dry run")
        _, busy = rah.busy_seconds(ctx, running=False)
        self.assertGreater(busy, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class Consent(unittest.TestCase):
    """Nothing is posted until the person agrees; the notice says what becomes public."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); self.home = self.tmp / "h"; self.home.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_notice_says_what_is_public(self):
        n = rah.consent_notice("octocat")
        for part in ("your GitHub account (octocat)", "carry that username", "your name is connected",
                     "OS, chip and number of cores", "GitHub always shows your username", "Nothing is posted until you agree"):
            self.assertIn(part, n)
        self.assertNotIn("anonymous", n.lower())
        self.assertIn("the one `gh` is logged into", rah.consent_notice())

    def test_no_submit_or_auto_without_agreeing(self):
        rp = self.tmp / "r.json"; rp.write_text(json.dumps(Fast._valid_record(None, rp)))
        r = cli("submit", "--record", rp, "--login", "x-y", "--no-gh-check", home=self.home, check=False)
        self.assertEqual(r.returncode, 1); self.assertIn("Nothing is posted until you agree", r.stderr)
        self.assertIn("riemann-at-home submit --agree", r.stderr)
        r = cli("submit", "--enable-auto", home=self.home, check=False)
        self.assertEqual(r.returncode, 1); self.assertIn("Nothing is posted until you agree", r.stderr)

    def test_ask_consent_without_terminal_only_prints(self):
        ctx = rah.Ctx(type("A", (), {"folder": None, "logs": str(self.tmp / "logs")})())
        os.environ["RAH_HOME"] = str(self.home)
        try:
            ctx = rah.Ctx(type("A", (), {"folder": None, "logs": str(self.tmp / "logs")})())
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), unittest.mock.patch("sys.stdin", io.StringIO("y\n")):
                rah.ask_consent(ctx)
        finally:
            del os.environ["RAH_HOME"]
        self.assertIn("riemann-at-home submit --agree", buf.getvalue())
        self.assertFalse(rah.has_consent(ctx))           # an assistant can't answer for the person
