# Week 3 Lab — Build-Fixer Agent with Human Approval Gate

## What's in this folder

- `src/calculator.py` — the intentionally buggy app from the lab (`add()` subtracts instead of adding).
- `tests/test_calculator.py` — the two tests from the lab (`test_add` fails, `test_multiply` passes).
- `scripts/build_fixer_agent.py` — the agent, extended with an offline/dry-run fallback so the flow can be demonstrated without live GitHub/Anthropic credentials (see caveats below). With `ANTHROPIC_API_KEY`/`GH_TOKEN` configured, it behaves exactly like the version in the course notes.
- `.github/workflows/ci.yml` — the two-job Actions workflow from the notes (`test` → `agent-fix`, gated by the `agent-proposed` Environment).
- `build_log.txt`, `agent_pr_preview.md`, `build_fixer_result.json` — real output captured by actually running the flow locally (see below).

## What was actually run and verified (not simulated as text)

```
$ python3 _local_runner.py > build_log.txt 2>&1     # a pytest-alike runner (see caveat 1)
FAILED tests/test_calculator.py::test_add
PASSED tests/test_calculator.py::test_multiply
2 run, 1 failed, 0 collection error(s)

$ python3 scripts/build_fixer_agent.py --log build_log.txt --source src/calculator.py --dry-run
(No ANTHROPIC_API_KEY / no network route to the API -- using an offline rule-based
fallback so the rest of the pipeline can still be demonstrated. This is NOT a live
Claude call.)
Agent identified root cause: add(a, b) is implemented as `return a - b` instead of
`return a + b`, so test_add fails on any non-zero b.
Proposed fix: Change the operator in add() from subtraction to addition.
(No GH_TOKEN/REPO configured or --dry-run passed: wrote agent_pr_preview.md instead
of opening a real PR.)

$ python3 scripts/build_fixer_agent.py --log build_log.txt --source src/calculator.py --dry-run --apply
[--apply] wrote fix to src/calculator.py

$ python3 _local_runner.py
PASSED tests/test_calculator.py::test_add
PASSED tests/test_calculator.py::test_multiply
2 run, 0 failed   # green
```

`agent_pr_preview.md` is exactly what the PR body would look like on GitHub,
including the checklist from the course notes.

## Caveats — what you still need to do yourself for the actual deliverable

1. **No live GitHub Actions run happened.** This was built and run in a
   sandboxed environment with no outbound access to GitHub's API, PyPI, or
   the Anthropic API. `_local_runner.py` is a small stand-in for `pytest`
   (import test files, run `test_*` functions, report pass/fail) used only
   because real `pytest` couldn't be installed there — the actual test files
   are ordinary pytest-style files and will run unmodified under real
   `pytest` in your CI.
2. **The agent's fix above came from an offline fallback, not a live Claude
   call**, because there was no `ANTHROPIC_API_KEY` in that environment. The
   fallback is clearly logged as such and only handles this exact bug shape
   (a wrong operator in a one-line function) — it's there so you can see the
   rest of the pipeline (PR body, checklist, apply-and-go-green) work
   end-to-end. Once you add your real `ANTHROPIC_API_KEY` as a GitHub
   secret, the script calls the actual model.
3. **The lab explicitly asks for screenshots** of the failure, the agent's
   PR, and the approval-gate pause. Those have to come from your own
   repo/GitHub UI — push this folder, set up the `agent-proposed` Environment
   with Required reviewers (Step 4 in the lab), trigger a push, and screenshot
   the real run.

## Lab deliverable draft (fill in your own screenshots + judgment)

**Screenshots to attach:** (1) the `test` job red in the Actions tab, (2) the
PR the agent opened, (3) the `agent-fix` job paused waiting on the
`agent-proposed` Environment review.

**Agent's root_cause / fix_description — was it accurate?** For this bug
shape (wrong operator in a single-line function) it was exactly right in the
local dry run: it correctly named the line, the operator, and the minimal
fix, and changed nothing else in the file. The harder question is whether it
would stay this precise on a bug that isn't a single obviously-wrong
operator — worth trying a second, messier bug yourself before trusting the
pattern broadly.

**One thing to change about the prompt/guardrail:** the current system
prompt says "change exactly one file... never the test file," which is the
right instinct, but nothing stops the agent from proposing a fix that makes
the *assertion* pass without fixing the *underlying* behavior (e.g.
special-casing the exact numbers in the test). A stronger prompt would ask
the agent to also state, in one sentence, why the fix is general and not
just tuned to the failing assertion — and a stronger guardrail would have a
second, held-out test run the same class of bug with different numbers
before a human approves.
