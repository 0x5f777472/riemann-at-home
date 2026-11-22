# Riemann@home

Every independent build of the AI proof of the Riemann Hypothesis.

Levent Alpöge's Lean proof of the Riemann Hypothesis has 175,187 modules. Volunteers build it on their own computers with the official tools, and each computer reports its progress through a public GitHub pull request. A bot checks every report and publishes this page.

- Live page: https://riemann-at-home.github.io/riemann-at-home/
- Code and instructions: https://github.com/riemann-at-home/riemann-at-home
- Discuss on Hacker News: https://news.ycombinator.com/item?id=50594006
- Raw data: https://riemann-at-home.github.io/riemann-at-home/data.json (format: CONTRACT.md in the repository)
- Updated: 2026-11-22T05:50:07Z

## Totals

- Builders: 5
- Modules built at least once: 33,160 of 175,187 (18.9%)
- Modules built 3 or more times: 16,473
- Whole proofs finished: 0

## Running now

- titojankowski (github.com/titojankowski): 33,160 modules (18.9%), Apple M5 Max
- derek-blanchette (github.com/derek-blanchette): 32,040 modules (18.3%), AMD Ryzen 9 5950X 16-Core Processor
- rib3ye (github.com/rib3ye): 16,473 modules (9.4%), Apple M2 Max
- gebhardtr (github.com/gebhardtr): 10,941 modules (6.2%), AMD Ryzen 5 5600X 6-Core Processor
- muellerdominikalexander-gif (github.com/muellerdominikalexander-gif): 7,814 modules (4.5%), Intel(R) Core(TM) i9-9880H CPU @ 2.30GHz

## Leaderboard: finished the whole proof

No one has finished yet.

## Also checked independently by

- Andrew Sutherland (MIT): full build, 175,187 modules, 0 errors; leanchecker, nanoda, lean4lean and con-leche all accept (https://math.mit.edu/~drew/grh)
- Simon DeDeo: native kernel replay of the whole proof (3 h 22 min) (https://github.com/leecrossley/riemann-rev)
- shosonoda (RIKEN): lake build, 175,187 of 175,187 modules, 0 failed jobs (https://github.com/shosonoda/lean-rh-alpoge)
- vincitamore: lake build of all 175,187 modules, axiom check, kernel replay (https://github.com/vincitamore/riemann-lean-account)
- starx237: build plus axiom audit of all five main theorems (https://github.com/starx237/RH-Lean-Verification)

As each person reported it publicly.

## Join in

Paste this into an AI assistant that can run commands (Claude, ChatGPT, ...):

```
I'd like to help build the Lean proof of the Riemann Hypothesis through Riemann@home.
Please clone https://github.com/riemann-at-home/riemann-at-home, read its README, and walk me through the volunteer steps:
"riemann-at-home setup", then "riemann-at-home build".
Once the build is running, start my local dashboard with "riemann-at-home page" and open http://localhost:8642 in my browser.
If the whole proof finishes, help me run "riemann-at-home export" and, if it reproduces, "riemann-at-home sign" to sign the joint statement.
Ask me before installing anything, and show me the tool's notice before I agree to post anything publicly.
```

What becomes public: your GitHub username (on the commits and the pull request), your computer's OS, chip and number of cores, and which modules you've built. Nothing is posted until you agree.

## Joint statement

We, the undersigned, each built Levent Alpöge's Lean proof of the Riemann Hypothesis (released November 20, 2026) on our own computers, from the official archive (sha256 `9631b4f0…c7fc`) with the pinned Lean 4.33.1 and Mathlib.

Each signatory:
1. compiled all 175,187 modules (`lake build Main`) without errors,
2. confirmed the final theorem depends only on Lean's three standard axioms (`propext`, `Classical.choice`, `Quot.sound`),
3. exported the compiled proof and reproduced the same raw export file as other independent builders (sha256 `5ea74b91…244e`),
4. where noted, re-checked that export with an independent checker written separately from Lean's own kernel (nanoda, con-leche, lean4checker or lean4lean), named beside that signature.

We do not certify the mathematics. That the statement is Mathlib's Riemann Hypothesis, and that the proved theorem is exactly that statement, was checked by the Lean and Mathlib communities ([their statement](https://leanprover-community.github.io/blog/posts/riemann-hypothesis/)). Each signature is the signer's own report, tied to their GitHub account.

We join the Lean and Mathlib communities in congratulating Levent Alpöge.

Signatures so far: 0.
