# Riemann@home

Every independent build of the AI proof of the Riemann Hypothesis.

Levent Alpöge's Lean proof of the Riemann Hypothesis has 175,187 modules. Volunteers build it on their own computers with the official tools, and each computer reports its progress through a public GitHub pull request. A bot checks every report and publishes this page.

- Live page: https://riemann-at-home.github.io/riemann-at-home/
- Code and instructions: https://github.com/riemann-at-home/riemann-at-home
- Discuss on Hacker News: https://news.ycombinator.com/item?id=50594006
- Raw data: https://riemann-at-home.github.io/riemann-at-home/data.json (format: CONTRACT.md in the repository)
- Updated: 2026-11-25T22:45:44Z

## Totals

- Builders: 18
- Modules built at least once: 175,187 of 175,187 (100.0%)
- Modules built 3 or more times: 175,187
- Whole proofs finished: 11

## Leaderboard

### Validated: built the whole proof and reproduced the export

1. derek-blanchette (github.com/derek-blanchette): all 175,187 modules, built in 18.7 h, AMD Ryzen 9 5950X 16-Core Processor, export reproduced, signed the joint statement
2. jasonhansel (github.com/jasonhansel): all 175,187 modules, built in 11.4 h, Intel(R) Xeon(R) Platinum 8375C CPU @ 2.90GHz, export reproduced, signed the joint statement
3. ericpruitt (github.com/ericpruitt): all 175,187 modules, built in 9.0 h, AMD Ryzen Threadripper PRO 9975WX 32-Cores, export reproduced, signed the joint statement
4. Fornax96 (github.com/Fornax96): all 175,187 modules, built in 15.9 h, AMD Ryzen 9 7900X3D 12-Core Processor, export reproduced, signed the joint statement
5. rib3ye (github.com/rib3ye): all 175,187 modules, built in 48.6 h, Apple M2 Max, export reproduced, signed the joint statement
6. xangma (github.com/xangma): all 175,187 modules, built in 16.4 h, AMD Ryzen Threadripper PRO 3995WX 64-Cores, export reproduced, signed the joint statement
7. gebhardtr (github.com/gebhardtr): all 175,187 modules, built in 60.4 h, AMD RYZEN AI MAX+ 395 w/ Radeon 8060S, export reproduced, signed the joint statement
8. Andrea Shepard: all 175,187 modules, built in 13.9 h, AMD Ryzen Threadripper PRO 3975WX 32-Cores, export reproduced, signed the joint statement

### Whole proof built

- titojankowski (github.com/titojankowski): all 175,187 modules, built in 64.3 h, Apple M5 Max
- Ununhexium: all 175,187 modules, built in 57.5 h, AMD Ryzen 7 5700G with Radeon Graphics
- sanzgiri (github.com/sanzgiri): all 175,187 modules, built in 41.0 h, Apple M4 Max, exporting now

### Building now

- Genbox (github.com/Genbox): 175,182 modules (100.0%), 12th Gen Intel(R) Core(TM) i7-12700K
- muellerdominikalexander-gif (github.com/muellerdominikalexander-gif): 173,524 modules (99.1%), Intel(R) Core(TM) i9-9880H CPU @ 2.30GHz
- milhouse1337 (github.com/milhouse1337): 150,747 modules (86.0%), Apple M3 Ultra
- tgragnato (github.com/tgragnato): 52,978 modules (30.2%), Intel(R) Celeron(R) J6413 @ 1.80GHz
- framiere (github.com/framiere): 21,921 modules (12.5%), Apple M4 Pro
- Aerlinger (github.com/Aerlinger): 3,793 modules (2.2%), Apple M5 Pro
- luvchurchill (github.com/luvchurchill): 1 modules (0.0%), Intel(R) Core(TM) i5-9400F CPU @ 2.90GHz

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
If the whole proof finishes, help me run "riemann-at-home export".
Ask me before installing anything. During setup, show me the tool's notice about what it posts to GitHub and ask me once; if I agree, it posts my progress on its own from then on, so don't ask me again for each update. Also ask me then whether I want to sign the joint statement if my build finishes and my export matches.
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

Signatures so far: 8.
- derek-blanchette, signed 2026-11-23
- jasonhansel, signed 2026-11-23
- ericpruitt, signed 2026-11-23
- Fornax96, signed 2026-11-25
- rib3ye, signed 2026-11-25
- gebhardtr, signed 2026-11-25
- xangma, signed 2026-11-25
- Andrea Shepard, signed 2026-11-25

## I’m totally confused what this website is 😭

The [Riemann Hypothesis](https://en.wikipedia.org/wiki/Riemann_hypothesis) is one of math’s most famous unsolved problems: a 160-year-old guess about where prime numbers fall, with a [$1 million prize](https://www.claymath.org/millennium/riemann-hypothesis/) for proving it. On November 20, 2026, [Levent Alpöge published a proof](https://alpo.ge/remark.pdf), written with help from AI in [Lean](https://lean-lang.org/), a language where a computer checks every step. The proof is so big (175,187 files) that checking it takes about two days on a fast computer, and many people independently running that check is one of the four reasons the Lean and Mathlib communities give in [their statement certifying the proof](https://leanprover-community.github.io/blog/posts/riemann-hypothesis/). This site tracks everyone who runs that check on their own machine, because the more people who independently get the same result, the more we can trust it.
