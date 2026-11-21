# Riemann@home v1 contract: the formats every piece agrees on

Workstreams A (volunteer CLI), B (bot), C (global page) all read/write these. Change only by updating this file.

## Constants

- archive: `lean.tar.gz` from https://alpo.ge (parts 01–14), sha256 `9631b4f020199e580ba86178cb56c6e9b09f690c2369a80dc4334aa93f49c7fc`
- toolchain `leanprover/lean4:v4.33.1`, Mathlib `0df444a360eaa60ab8c11dca51a86af692955474`
- build folder (fixed): macOS `/Users/Shared/riemann-at-home/lean`, Linux `/opt/riemann-at-home/lean` (pending M0)
- module list: all `src/**/*.lean` of the archive, as dotted names, sorted byte-wise; N = 175,187.
  Module index i = position in that list (0-based). Published once as `modules.txt` (same list for everyone).

## Build record — `submissions/<github-login>/<UTC time YYYYMMDDTHHMMSSZ>.json`

```json
{
  "format": "rah/build/1",
  "tool": "riemann-at-home 1.0.0",
  "archive_sha256": "9631b4f0…",
  "toolchain": "leanprover/lean4:v4.33.1",
  "mathlib_rev": "0df444a3…",
  "build_folder": "/Users/Shared/riemann-at-home/lean",
  "machine": {"os": "Darwin 25.4.0", "arch": "arm64", "cpu": "Apple M5 Max", "cores": 18},
  "started": "2026-11-21T15:26:31Z",
  "recorded": "2026-11-22T09:10:02Z",
  "busy_seconds": 63000,
  "modules_compiled": 3565,
  "bitmap_b64": "<N bits, bit i = module i compiled, LSB-first per byte, gzip then base64>",
  "olean_digest": "<sha256 over, for each compiled module in index order: sha256(.olean bytes) as 32 raw bytes>",
  "whole_proof": false,
  "axioms": null
}
```

- `whole_proof` true only when all N compiled AND the axiom check ran; then `axioms` is the list printed for
  `riemannHypothesis` (expected `["propext", "Classical.choice", "Quot.sound"]`).
- No name/email inside: the identity is the PR author (GitHub login), which must equal `<github-login>` in the path.
- A person may submit many records; each supersedes their previous one (bitmap must be a superset).

## Bot acceptance rules (B)

Reject with a PR comment if any fails: format/tool known · constants match · path login == PR author · bitmap ⊇ the
person's last accepted bitmap · `modules_compiled` == popcount(bitmap) · speed plausible: new modules ÷ elapsed hours
since last accepted record ≤ 12,000/h (flag, don't reject, between 6,000 and 12,000) · `olean_digest` == reference digest
for that bitmap (reference = the project's own build; skipped until M0 confirms cross-machine identity).
Accept → merge, regenerate `data.json`, commit.

## data.json (C reads; B writes)

```json
{
  "generated": "…Z",
  "n": 175187,
  "libraries": [["BuildAid", 0], ["CompanionTheory", 5], …],
  "builders_b64": "<N bytes gzip+base64: per module, number of distinct people whose accepted build compiled it (cap 250)>",
  "summary": {"people": 0, "whole_proofs": 0, "modules_built_once": 0, "modules_built_3x": 0},
  "leaderboard": [{"who": "login", "modules": 0, "whole_proof": false, "build_hours": null, "machine": "Apple M5 Max",
                   "since": "2026-11-21T15:26:31Z", "finished": null, "first_whole_proof_rank": null}],
  "latest": {"who": "login", "modules": 0, "recorded": "…Z", "machine": "Apple M5 Max"},
  "validated": [{"who": "Andrew Sutherland (MIT)", "what": "…", "url": "https://math.mit.edu/~drew/grh"}]
}
```

Leaderboard order: modules compiled (desc); among whole proofs, `first_whole_proof_rank` (who finished first);
otherwise earliest `since`. `since` = full UTC timestamp of the person's first accepted record.
`build_hours` = `busy_seconds` / 3600 of the record that completed the whole proof (null until then).
`finished` = `recorded` (UTC) of that same record (null until then).
`libraries` = top-level folders only, with their first module index. `modules.txt` is published next to index.html
by whoever publishes data.json (the bot), unchanged from the reference list.

## Additional rules (from building the bot, 2026-11-21)

- A submission PR adds exactly one new file under `submissions/<login>/` and touches nothing else. Rejected PRs are
  closed with a comment listing the reasons; the volunteer resubmits as a new PR.
- Unknown fields are rejected. `machine` = {os, arch, cpu: strings; cores: integer}. Record ≤ 256 KB.
- `recorded` > `started`, not in the future (10 min skew allowed), and after the person's last accepted record.
  `busy_seconds` ≤ `recorded − started`. Bitmap non-empty, no bits past module N−1.
- `build_folder` is one of the two fixed folders. `tool` is an exact known release string ("riemann-at-home 1.0.0").
- `olean_digest` = lowercase hex sha256 over the concatenation of the 32-byte raw sha256 of each compiled module's
  `.olean`, in module-index order.
- Speed: new modules ÷ wall-clock hours since the previous accepted record (first record: since `started`).
- The digest reference is a frozen hash table (`rahbot reference-snapshot`), not the live build folder, which changes
  while a build runs. Kept by the bot; can be published.

## Several computers per person (2026-11-21)

- `setup` creates a random `build_id` (16 hex chars) per computer and keeps it; every record carries `"build_id"`.
- Path: `submissions/<github-login>/<build_id>/<UTC time>.json`.
- Bot rules that said "the person's last accepted record" now mean "this build's last accepted record"
  (bitmap superset, recorded-after, speed). Different builds of one person are independent.
- Leaderboard per person: `modules` = union of all their builds' bitmaps; `whole_proof` if any build is whole
  (`build_hours`/`finished` from the first whole build); new field `computers` = number of builds.
  `machine` = the machine of their largest build.
- Terrain (`builders_b64`) still counts distinct PEOPLE per module, not builds.

## Running now + staleness (2026-11-21)

- data.json gets `"running"`: one entry per BUILD that is not whole:
  `{"who": "login", "build_id": "…", "machine": "…", "modules": 0, "recorded": "…Z"}`, sorted by modules desc.
- The page shows a running entry only if `recorded` is within the last 1 h (was 24 h) (checked in the browser against the
  current time, so stale builds vanish even if the bot is idle). Stale builds still count in the terrain and in the
  person's leaderboard modules.
- (Superseded) Updates are pushed to the build's single PR every ~10 minutes; see "One PR per computer".

## One PR per computer, updated in place (2026-11-21) — supersedes per-record PRs and the 6-hour auto-submit

- Each build (computer) opens ONE pull request when it starts: branch `rah/<build_id>` in the volunteer's fork, adding
  `submissions/<login>/<build_id>.json` (one file per build, overwritten on each update; no timestamp in the name).
- While building, the tool commits the updated record to that same branch every ~10 minutes (quiet: no new PR).
- The bot polls every ~10 minutes, reading all open PRs' head records in batches (GraphQL), checks each (rules apply
  between successive versions of the same build's record), and includes accepted open-PR records in data.json
  (`running`, leaderboard, terrain) WITHOUT merging. It republishes data.json at most ~6×/hour (GitHub Pages limit).
- The bot merges the PR when the record is whole_proof, or when the volunteer runs `riemann-at-home finish`
  (marks the record `"final": true`), or after 7 days without updates (merge the last accepted version).
- A version that fails checks is not used; the bot comments once on the PR with the reason and keeps the last
  accepted version until a newer one passes. It only closes a PR for identity/path violations.
- Staleness: Running Now hides builds whose `recorded` is older than 1 h (page-side).

## Clarifications from building the CLI (2026-11-21)

- A module counts as compiled only when both its `.olean` and its `.trace` exist (Lake writes the trace last; an
  `.olean` without `.trace` is an interrupted build and gets rebuilt). CLI, bot reference snapshot and page all use this.
- Compare bitmaps by decompressing and comparing bits, never by the base64 text (gzip output differs by implementation).
- Records are checked as a SET of keys, not key order. `build_id` and `final` are part of the schema.
- `whole_proof` is only a claim: the bot itself verifies `axioms` == ["propext", "Classical.choice", "Quot.sound"]
  (in any order) and rejects anything else, including `sorryAx`.
- `busy_seconds` = wall time while the build was running, minus pauses.
- `modules.txt` is sorted by UTF-8 bytes (identical to code-point order for these names).

## Display names (2026-11-21)

- Records may carry optional `"display_name"`: plain text, 1–32 chars, no control chars; or `"anonymous": true`.
- The page shows display_name (or "anonymous #<n>", n = stable small number per person) instead of the login, and no
  GitHub profile link. data.json leaderboard/running/latest entries carry `"name"` (what to show) and keep `"who"`
  (login) only when the person did not choose a display name or anonymity; otherwise `"who": null`.
- Bot rejects a display_name equal (case-insensitive) to another participant's GitHub login.
- The CLI explains when setting it: "This hides your username on the Riemann@home page. Your pull request is still
  public on GitHub under your account."
- `running` excludes builds marked `"final": true`.
- display_name validation (CLI and bot identical): trim ends, 1–32 chars, reject Unicode categories Cc, Cf, Zl, Zp.
  Impersonation check compares NFKC-normalised, casefolded text against every other participant's login.
- Decisions: display names are validated when a record version is accepted; an accepted name is not re-judged later
  (a newcomer can't knock an existing name off the board). Display names may not start with "anonymous"
  (case-insensitive), in CLI and bot. `running` entries of display-name/anonymous people omit `build_id`.

## Resuming after a merge (2026-11-21)

- A build whose PR was merged (whole, final, or 7 days stale) may continue: the same build_id opens a FOLLOW-UP PR that
  modifies its existing `submissions/<login>/<build_id>.json` on main. Checked against the merged version (bitmap grows,
  recorded later, speed over the whole gap). Not an identity violation. Only one open PR per build at a time.
- After `"final": true` is merged, further versions are still rejected (final means final); a stale-merged build is not final.
- The CLI detects that its PR was merged and opens the follow-up PR automatically on the next update.

## No stale merge (2026-11-21) — supersedes the 7-day merge and "Resuming after a merge"

- The bot merges a build's PR only when its accepted version is whole_proof or `"final": true`. No time-based merge.
  Abandoned PRs simply stay open. Follow-up PRs are therefore not needed: a build has one PR for its whole life.
- If the bot's state is lost, it rebuilds by re-reading every open PR's head and re-checking it from scratch
  (no previous version → checked as a first version).

## Levels and the joint statement (2026-11-21)

Modelled on the Lean and Mathlib communities' joint statement
(https://leanprover-community.github.io/blog/posts/riemann-hypothesis/): their check 2 is "reproducing the same raw
proof export file"; their check 4 is re-checking that export with independent checkers. Checks 1 and 3 (statement =
Mathlib's RiemannHypothesis; proved theorem is exactly that statement) are theirs; we cite them, we don't redo them.

- **Level 1 · Build**: any compiled modules (as now). `whole_proof` as now.
- **Level 2 · Export reproduced**: whole_proof AND `export_sha256` equals the reference export.
  Reference (Andrew Sutherland, https://math.mit.edu/~drew/grh): `solution.ndjson`, 61,570,595,788 bytes,
  sha256 `5ea74b912147c5c93cc2b6d70cc727cf908df2f62ac6a20480a3fa02f6be244e`, made with lean4export v4.33.0.
  The CLI streams the exporter's output straight into sha256 and a byte counter (no 61 GB file on disk).
  The exact exporter invocation must reproduce that hash; until a full build has confirmed it, treat it as unverified.
- **Level 3 · Independent re-check**: Level 2 AND at least one independent checker accepted the export
  (nanoda, con-leche, lean4checker, lean4lean). Needs a large-memory machine (nanoda ~100 GB RAM, con-leche ~50 GB).
- New optional record fields: `"export_sha256"`, `"export_bytes"` (int), `"checkers"`:
  `[{"name": "nanoda", "version": "…", "result": "accept", "seconds": 0}]`, `"sign_statement": true`.
- `sign_statement` is accepted only at Level 2 or 3. The bot rejects an `export_sha256` that isn't the reference
  (reason: "export does not reproduce the reference").
- data.json gets `"signatures"`: `[{"who": login|null, "name": "…", "signed": "…Z", "machine": "…", "level": 2|3,
  "checkers": ["nanoda"]}]`, ordered by `signed` (time the signing version was accepted). Leaderboard entries get
  `"level"` (1–3).
- Page: a "Joint statement" tab beside the leaderboard view: statement text (owner-approved wording, kept in the page),
  then the signatures list (avatar, name, date, machine, level badges). Empty state: "No signatures yet."
