#!/usr/bin/env python3
"""
build_fixer_agent.py -- Week 3 Lab.

Reads the build log, asks Claude to identify the failing test and propose a
minimal fix, then opens a GitHub PR with the proposed change (never merges).

This version adds a --dry-run / offline fallback on top of the version in
the course notes, so the lab can be demonstrated end-to-end without an
Anthropic key or GitHub token (e.g. inside a network-restricted sandbox, or
before you've wired up secrets). With real credentials configured, it behaves
exactly like the notes' version: real Claude call, real PR, human required to
merge.
"""
import argparse
import json
import os
import re


SYSTEM_PROMPT = """You are a build-fixer agent. Your only job is to identify
the root cause of a failing Python test and propose the minimal fix to the
source file. Change exactly one file: the source file under test, never the
test file. fixed_file_content must be the complete corrected file. Do not add
tests or make stylistic changes unrelated to the bug."""

FIX_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause": {"type": "string"},
        "fix_description": {"type": "string"},
        "fixed_file_path": {"type": "string"},
        "fixed_file_content": {"type": "string"},
    },
    "required": ["root_cause", "fix_description", "fixed_file_path", "fixed_file_content"],
    "additionalProperties": False,
}


def offline_fallback_fix(build_log: str, source_path: str, source_code: str):
    """Deterministic stand-in for the Claude call, used only when no
    ANTHROPIC_API_KEY is configured (e.g. this sandbox has no network route
    to the Anthropic API). It handles exactly the bug shape used in this lab
    (a wrong operator in a one-line function) so the rest of the pipeline --
    PR body, approval gate, guardrail checks -- can be exercised for real.
    This is clearly logged as a fallback, never silently passed off as a
    live model call.
    """
    print("(No ANTHROPIC_API_KEY / no network route to the API -- using an "
          "offline rule-based fallback so the rest of the pipeline can still "
          "be demonstrated. This is NOT a live Claude call.)")

    match = re.search(r"AssertionError", build_log)
    failing_test_match = re.search(r"tests/(test_\w+\.py)::?(\w+)?", build_log)
    if not match:
        raise RuntimeError("Offline fallback only handles AssertionError-style failures.")

    # Extremely narrow, honest heuristic: this lab's known bug is
    # `return a - b` inside `def add(a, b):`. Detect that literal shape.
    if "def add(a, b):" in source_code and "return a - b" in source_code:
        fixed = source_code.replace(
            "def add(a, b):\n    # Bug: subtraction instead of addition\n    return a - b",
            "def add(a, b):\n    return a + b",
        )
        if fixed == source_code:
            # formatting differed slightly; do a narrower replace
            fixed = re.sub(
                r"(def add\(a, b\):\n(?:.*\n)?)\s*return a - b",
                lambda m: m.group(1) + "    return a + b",
                source_code,
                count=1,
            )
        return {
            "root_cause": "add(a, b) is implemented as `return a - b` instead of `return a + b`, so test_add fails on any non-zero b.",
            "fix_description": "Change the operator in add() from subtraction to addition.",
            "fixed_file_path": source_path,
            "fixed_file_content": fixed,
        }

    raise RuntimeError(
        "Offline fallback does not recognize this bug shape. Configure "
        "ANTHROPIC_API_KEY to let the real model reason about arbitrary bugs."
    )


def call_claude(build_log: str, source_path: str, source_code: str):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return offline_fallback_fix(build_log, source_path, source_code)

    try:
        import anthropic
    except ImportError:
        print("(anthropic package not installed -- falling back to offline mode.)")
        return offline_fallback_fix(build_log, source_path, source_code)

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=os.environ.get("MODEL", "claude-opus-4-8"),
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": FIX_SCHEMA}},
        messages=[{
            "role": "user",
            "content": (
                f"Build log:\n```\n{build_log}\n```\n\n"
                f"Source file ({source_path}):\n```python\n{source_code}\n```"
            ),
        }],
    )
    return json.loads(next(b.text for b in response.content if b.type == "text"))


def open_pull_request(fix: dict, dry_run: bool):
    gh_token = os.environ.get("GH_TOKEN")
    repo_name = os.environ.get("REPO")
    if dry_run or not gh_token or not repo_name:
        with open("agent_pr_preview.md", "w") as f:
            f.write("# [DRY RUN] Agent-Proposed Fix\n\n")
            f.write(f"**Root cause:** {fix['root_cause']}\n\n")
            f.write(f"**Change:** {fix['fix_description']}\n\n")
            f.write("---\n*This PR was opened by the build-fixer agent. "
                    "A human must review and approve before merging.*\n\n")
            f.write("**Checklist before approving:**\n")
            f.write("- [ ] The proposed fix matches the described root cause\n")
            f.write("- [ ] No unrelated changes are included\n")
            f.write("- [ ] The fix does not touch infrastructure or deployment files\n\n")
            f.write(f"### Full corrected `{fix['fixed_file_path']}`\n\n")
            f.write("```python\n" + fix["fixed_file_content"] + "\n```\n")
        print("(No GH_TOKEN/REPO configured or --dry-run passed: wrote "
              "agent_pr_preview.md instead of opening a real PR.)")
        return None

    from github import Github

    gh = Github(gh_token)
    repo = gh.get_repo(repo_name)
    base = os.environ.get("BASE_BRANCH", "main")
    branch_name = f"bot/fix-build-{os.environ.get('GITHUB_RUN_ID', 'local')}"

    ref = repo.get_git_ref(f"heads/{base}")
    repo.create_git_ref(f"refs/heads/{branch_name}", ref.object.sha)

    contents = repo.get_contents(fix["fixed_file_path"], ref=base)
    repo.update_file(
        fix["fixed_file_path"],
        f"[bot] fix: {fix['root_cause'][:72]}",
        fix["fixed_file_content"],
        contents.sha,
        branch=branch_name,
    )

    pr = repo.create_pull(
        title=f"[Bot Fix] {fix['root_cause'][:60]}",
        body=(
            f"## Agent-Proposed Fix\n\n"
            f"**Root cause:** {fix['root_cause']}\n\n"
            f"**Change:** {fix['fix_description']}\n\n"
            f"---\n*This PR was opened by the build-fixer agent. "
            f"A human must review and approve before merging.*\n\n"
            f"**Checklist before approving:**\n"
            f"- [ ] The proposed fix matches the described root cause\n"
            f"- [ ] No unrelated changes are included\n"
            f"- [ ] The fix does not touch infrastructure or deployment files\n"
        ),
        head=branch_name,
        base=base,
    )
    print(f"Opened PR #{pr.number}: {pr.html_url}")
    return pr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="build_log.txt")
    ap.add_argument("--source", default="src/calculator.py")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true",
                     help="Also write the fix to disk locally, to prove it turns the suite green.")
    args = ap.parse_args()

    with open(args.log) as f:
        build_log = f.read()
    with open(args.source) as f:
        source_code = f.read()

    fix = call_claude(build_log, args.source, source_code)
    print(f"Agent identified root cause: {fix['root_cause']}")
    print(f"Proposed fix: {fix['fix_description']}")

    open_pull_request(fix, args.dry_run)

    if args.apply:
        with open(fix["fixed_file_path"], "w") as f:
            f.write(fix["fixed_file_content"])
        print(f"[--apply] wrote fix to {fix['fixed_file_path']}")

    with open("build_fixer_result.json", "w") as f:
        json.dump(fix, f, indent=2)


if __name__ == "__main__":
    main()
