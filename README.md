# Riemann@home

Build the Lean proof of the Riemann Hypothesis on your own computer, and add your build to a global map.

**Global leaderboard:** https://riemann-at-home.github.io/riemann-at-home/

A proof of the Riemann Hypothesis, written with AI and checked in Lean, was published on 2026-11-20 by Levent Alpöge
(https://alpo.ge). Several people have already built the whole proof and confirmed it checks. Riemann@home lets anyone
do the same and watch it add up: the proof is 175,187 Lean modules, and the page shows how many people have built each
one, who is building right now, and who has built the whole thing.

## Join with an AI assistant

Paste this into Claude, ChatGPT, or another assistant that can run commands:

> I'd like to help build the Lean proof of the Riemann hypothesis through Riemann@home. Please clone
> https://github.com/riemann-at-home/riemann-at-home, read its README, and walk me through the volunteer steps:
> "riemann-at-home setup", then "riemann-at-home build", then "riemann-at-home submit" to send my build record.
> Ask me before installing anything, and show me the build record before submitting it.

## Join by hand

Needs macOS or Linux, Python 3, git, roughly 160 GB free for the whole proof (our estimate from builds so far; nobody has measured a finished build yet) (less is fine: the build stops by itself at 20 GB free, so your
computer always keeps room, and every module you built still counts).

1. **GitHub CLI.** Install `gh` (macOS: `brew install gh`) and log in yourself: `gh auth login`.
   The tool never asks for or handles your password or token.
2. **Setup.** `python3 -I cli/riemann-at-home setup`
   Downloads the official archive from alpo.ge, checks its sha256
   (`9631b4f020199e580ba86178cb56c6e9b09f690c2369a80dc4334aa93f49c7fc`), unpacks it into a fixed folder
   (macOS `/Users/Shared/riemann-at-home/lean`, Linux `/opt/riemann-at-home/lean`), installs the pinned Lean
   (4.33.1) and the Mathlib cache.
3. **Build.** `python3 -I cli/riemann-at-home build --gentle` (or `--full`)
   Runs the official `lake build Main`, unchanged, at the lowest priority. `pause`, `resume`, `stop`, `status`.
   A full build is about two days on a fast Mac; any amount counts.
4. **Post your progress.** `python3 -I cli/riemann-at-home submit`
   Opens one pull request for this computer and keeps it updated about every 10 minutes while you build.
5. **Optional name.** `riemann-at-home name "Your Name"` or `name --anonymous` shows that instead of your GitHub
   username on the page. Your pull request is still public on GitHub under your account.
6. **See your own build.** `python3 -I cli/riemann-at-home page` opens a local page for this computer.
7. **Done or stopping for good.** `python3 -I cli/riemann-at-home finish`

## What this is, and what it isn't

- It is many people independently re-running the same official build, and posting what their computer compiled.
- Results are self-reported, tied to your GitHub account. A bot checks every update (pinned archive and versions,
  progress only grows, plausible speed, a fingerprint of the compiled files) before it counts. It can't prove you
  actually ran it.
- Building the proof doesn't settle the mathematics. Whether the Lean statement means what mathematicians mean by the
  Riemann Hypothesis, and whether Lean itself has a bug, is work for experts.

## How it works

- `cli/riemann-at-home`: the volunteer tool (one Python file, standard library only).
- `submissions/<login>/<build_id>.json`: one record per computer, updated through that computer's pull request.
- `bot/rahbot`: checks pull requests, keeps the leaderboard data (`docs/data.json`) up to date, merges a computer's
  pull request when it finishes the whole proof or runs `finish`.
- `docs/`: the global page, served by GitHub Pages.
- `CONTRACT.md`: the exact record format and every rule the bot applies.

## Why not zero-knowledge proofs?

We tried: running the independent checker nanoda inside the RISC Zero zkVM works, and the result can be verified by
anyone in milliseconds. But proving the whole proof that way would take roughly 26 to 260 GPU-years today, and modules
that import a lot don't fit in the zkVM's memory. Projects like Ix (Argument Computer) are working on making this
practical. Until then, Riemann@home is people re-running the build in the open.
