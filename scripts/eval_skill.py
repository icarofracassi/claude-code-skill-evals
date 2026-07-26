"""
eval_skill.py — Automated eval runner for Claude Code skills.

Reads /tmp/issue_body.txt (the raw GitHub issue body), extracts the skill
content and optional test cases, then runs 4 eval checks:

  1. Structure lint       — no API needed
  2. Trigger precision    — LLM judge
  3. Output quality       — run skill + keyword check
  4. Scope adherence      — run skill on out-of-scope prompt + LLM judge
"""

import json
import os
import re
import sys

import anthropic
import yaml

MODEL = "claude-sonnet-5"
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ── result tracking ───────────────────────────────────────────────────────────

results: list[dict] = []


def record(label: str, status: str, detail: str = "") -> bool:
    """status: PASS | WARN | FAIL"""
    icons = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}
    print(f"{icons.get(status, '  ')} [{status}] {label}")
    if detail:
        print(f"         {detail}")
    results.append({"label": label, "status": status, "detail": detail})
    return status == "PASS"


# ── Claude helpers ────────────────────────────────────────────────────────────


def call_claude(system: str, user: str) -> str:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text.strip()


def call_claude_as_skill(skill_md: str, user: str) -> str:
    """Run the skill by injecting it as the system prompt."""
    return call_claude(
        system=f"You are a Claude Code assistant. Follow this skill exactly:\n\n{skill_md}",
        user=user,
    )


def parse_json_response(raw: str) -> dict:
    """Extract JSON from a response that may have surrounding prose."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"No JSON found in response: {raw[:200]}")


# ── issue parsing ─────────────────────────────────────────────────────────────


def read_issue() -> str:
    with open("/tmp/issue_body.txt") as f:
        return f.read()


def extract_section(body: str, label: str) -> str:
    """Pull content under a GitHub issue form heading."""
    pattern = rf"### {re.escape(label)}\s*\n+(.*?)(?=\n### |\Z)"
    m = re.search(pattern, body, re.DOTALL)
    return m.group(1).strip() if m else ""


def strip_code_fence(text: str, lang: str = "") -> str:
    pattern = rf"```{lang}\s*\n?(.*?)```"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def extract_frontmatter_field(skill_md: str, field: str) -> str:
    pattern = rf"^{field}:\s*[>|]?\s*\n?(.*?)(?=\n\w[\w_]*:|---)"
    m = re.search(pattern, skill_md, re.DOTALL | re.MULTILINE)
    if not m:
        return ""
    # collapse multiline YAML block scalars
    return re.sub(r"\s+", " ", m.group(1)).strip()


# ── eval 1: structure lint ────────────────────────────────────────────────────


def eval_structure(skill_md: str) -> None:
    print()
    print("=" * 60)
    print("EVAL 1 — Structure / Lint")
    print("=" * 60)

    record("Starts with YAML frontmatter (---)", "PASS" if skill_md.startswith("---") else "FAIL")

    has_name = bool(re.search(r"^name:\s*\S+", skill_md, re.MULTILINE))
    record("`name` field present in frontmatter", "PASS" if has_name else "FAIL")

    has_desc = bool(re.search(r"^description:", skill_md, re.MULTILINE))
    record("`description` field present in frontmatter", "PASS" if has_desc else "FAIL")

    trigger_keywords = ["trigger", "use when", "use this when", "whenever", "invoke"]
    has_trigger = any(kw in skill_md.lower() for kw in trigger_keywords)
    record(
        "Description includes trigger conditions",
        "PASS" if has_trigger else "WARN",
        "Add phrases like 'Use when…' or 'Trigger on:' so Claude routes correctly" if not has_trigger else "",
    )

    placeholder_count = skill_md.count("⚠️ PLACEHOLDER") + skill_md.count("TODO")
    record(
        f"No unresolved placeholders ({placeholder_count} found)",
        "PASS" if placeholder_count == 0 else "WARN",
        "Resolve or remove ⚠️ PLACEHOLDER / TODO blocks before publishing" if placeholder_count else "",
    )

    word_count = len(skill_md.split())
    record(
        f"Skill length reasonable ({word_count} words)",
        "PASS" if 30 <= word_count <= 3000 else "WARN",
        "Very short skills may be too vague; very long ones may exceed context" if not (30 <= word_count <= 3000) else "",
    )


# ── eval 2: trigger precision ─────────────────────────────────────────────────


def eval_trigger_precision(description: str) -> None:
    print()
    print("=" * 60)
    print("EVAL 2 — Trigger Precision (LLM judge)")
    print("=" * 60)

    if not description:
        record("Trigger precision", "WARN", "Could not parse description from frontmatter — skipped")
        return

    raw = call_claude(
        system=(
            "You are a Claude Code skill quality reviewer. "
            "Evaluate whether this skill description is specific enough for a skill router to "
            "reliably invoke it for the right prompts and ignore unrelated ones. "
            "Consider: Does it say WHEN to trigger? Does it say what NOT to trigger on? "
            "Is the domain clear? "
            'Reply with JSON only: {"verdict": "PASS"|"WARN"|"FAIL", "reason": "one sentence"}'
        ),
        user=f"Skill description:\n\n{description}",
    )
    try:
        j = parse_json_response(raw)
        status = j.get("verdict", "WARN")
        record("Description is specific enough to route correctly", status, j.get("reason", ""))
    except (ValueError, KeyError):
        record("Trigger precision (parse error)", "WARN", raw[:200])


# ── eval 3: output quality ────────────────────────────────────────────────────


def eval_output_quality(skill_md: str, test_cases: list[dict]) -> None:
    print()
    print("=" * 60)
    print("EVAL 3 — Output Quality (user-provided test cases)")
    print("=" * 60)

    in_scope = [tc for tc in test_cases if tc.get("should_trigger", True)]
    if not in_scope:
        record("Output quality", "WARN", "No in-scope test cases provided — skipped")
        return

    for i, tc in enumerate(in_scope):
        prompt = tc.get("prompt", "")
        keywords = tc.get("expected_keywords", [])
        if not prompt:
            continue

        label_prefix = f"Case {i + 1}: \"{prompt[:50]}{'…' if len(prompt) > 50 else ''}\""

        if not keywords:
            record(f"{label_prefix} — has expected_keywords", "WARN", "No expected_keywords — skipping keyword check")
            continue

        output = call_claude_as_skill(skill_md, prompt)
        hits = [kw for kw in keywords if kw.lower() in output.lower()]
        missed = [kw for kw in keywords if kw.lower() not in output.lower()]
        status = "PASS" if not missed else ("WARN" if len(hits) >= len(keywords) // 2 else "FAIL")
        record(
            f"{label_prefix} — keywords ({len(hits)}/{len(keywords)})",
            status,
            f"Missing: {missed}" if missed else "",
        )


# ── eval 4: scope adherence ───────────────────────────────────────────────────


def eval_scope_adherence(skill_md: str, test_cases: list[dict]) -> None:
    print()
    print("=" * 60)
    print("EVAL 4 — Scope Adherence (out-of-scope prompts)")
    print("=" * 60)

    out_of_scope = [tc for tc in test_cases if tc.get("should_trigger") is False]
    if not out_of_scope:
        record("Scope adherence", "WARN", "No out-of-scope test cases provided — skipped")
        return

    for i, tc in enumerate(out_of_scope):
        prompt = tc.get("prompt", "")
        if not prompt:
            continue

        label_prefix = f"Out-of-scope {i + 1}: \"{prompt[:50]}{'…' if len(prompt) > 50 else ''}\""
        output = call_claude_as_skill(skill_md, prompt)

        raw = call_claude(
            system=(
                "You are evaluating whether an AI assistant correctly declined, redirected, "
                "or flagged an out-of-scope request rather than attempting to answer it incorrectly. "
                'Reply with JSON only: {"handled_correctly": true|false, "reason": "one sentence"}'
            ),
            user=(
                f"Out-of-scope prompt:\n{prompt}\n\n"
                f"Assistant response:\n{output}"
            ),
        )
        try:
            j = parse_json_response(raw)
            passed = j.get("handled_correctly", False)
            record(label_prefix, "PASS" if passed else "FAIL", j.get("reason", ""))
        except (ValueError, KeyError):
            record(f"{label_prefix} (parse error)", "WARN", raw[:200])


# ── summary ───────────────────────────────────────────────────────────────────


def print_summary() -> None:
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"  ✅ PASS: {counts['PASS']}   ⚠️  WARN: {counts['WARN']}   ❌ FAIL: {counts['FAIL']}")
    if counts["FAIL"] > 0:
        print()
        print("Failed checks:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  • {r['label']}")
                if r["detail"]:
                    print(f"    {r['detail']}")


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    body = read_issue()
    skill_raw = extract_section(body, "Skill file content")
    test_cases_raw = extract_section(body, "Test cases (YAML, optional)")

    # Strip markdown code fences if the submitter wrapped the content
    skill_md = strip_code_fence(skill_raw, "markdown") if "```" in skill_raw else skill_raw

    if not skill_md:
        print("❌ Could not extract skill content from issue body.")
        print("   Make sure the issue was created with the Submit a Skill template.")
        sys.exit(1)

    description = extract_frontmatter_field(skill_md, "description")

    test_cases: list[dict] = []
    if test_cases_raw:
        clean = strip_code_fence(test_cases_raw, "yaml") if "```" in test_cases_raw else test_cases_raw
        try:
            parsed = yaml.safe_load(clean)
            if isinstance(parsed, list):
                test_cases = parsed
        except yaml.YAMLError as e:
            print(f"⚠️  Could not parse test cases YAML: {e}")

    eval_structure(skill_md)
    eval_trigger_precision(description)

    if test_cases:
        eval_output_quality(skill_md, test_cases)
        eval_scope_adherence(skill_md, test_cases)
    else:
        print()
        print("ℹ️  No test cases provided — Evals 3 and 4 skipped.")
        print("   Add a 'Test cases (YAML)' block in the issue to get output quality scores.")

    print_summary()


if __name__ == "__main__":
    main()
