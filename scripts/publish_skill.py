"""
publish_skill.py — Appends an accepted skill to the ITEMS array in index.html.

Reads /tmp/issue_body.txt and /tmp/issue_comments.json (fetched by the workflow).
Inserts a new JS object before the sentinel:
  // ACCEPTED SKILLS - DO NOT EDIT MANUALLY
  ...
  // END ACCEPTED SKILLS
"""

import json
import os
import re
import sys


def read_issue() -> str:
    with open("/tmp/issue_body.txt") as f:
        return f.read()


def read_comments() -> list[dict]:
    try:
        with open("/tmp/issue_comments.json") as f:
            return json.load(f)
    except Exception:
        return []


def extract_section(body: str, label: str) -> str:
    pattern = rf"### {re.escape(label)}\s*\n+(.*?)(?=\n### |\Z)"
    m = re.search(pattern, body, re.DOTALL)
    return m.group(1).strip() if m else ""


def strip_fence(text: str) -> str:
    m = re.search(r"```[a-z]*\n?(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def extract_frontmatter_field(skill_md: str, field: str) -> str:
    pattern = rf"^{field}:\s*[>|]?\s*\n?(.*?)(?=\n\w[\w_]*:|\n---)"
    m = re.search(pattern, skill_md, re.DOTALL | re.MULTILINE)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip().strip('"').strip("'")


def next_id(html: str) -> int:
    ids = [int(x) for x in re.findall(r"\bid:\s*(\d+)", html)]
    return max(ids, default=0) + 1


def js_string(s: str) -> str:
    return json.dumps(s)


def parse_evals_from_comments(comments: list[dict]) -> list[dict]:
    """
    Parse eval results from the lint comment posted by the workflow.
    Looks for lines like:  ✅ [PASS] Label text  or  ⚠️ [WARN] ...  or  ❌ [FAIL] ...
    Returns a list of {status, label, detail} dicts.
    """
    evals = []
    for comment in comments:
        body = comment.get("body", "")
        if "EVAL 1" not in body and "Skill Eval Results" not in body:
            continue
        for line in body.splitlines():
            m = re.match(r"[✅⚠❌].?\s*\[(PASS|WARN|FAIL)\]\s*(.+)", line)
            if m:
                status = m.group(1).lower()
                label = m.group(2).strip().rstrip(".")
                evals.append({"status": status, "label": label, "detail": ""})
        if evals:
            break
    return evals


def main() -> None:
    body = read_issue()
    comments = read_comments()
    issue_number = os.environ.get("ISSUE_NUMBER", "0")
    issue_url = os.environ.get("ISSUE_URL", "")

    skill_raw = extract_section(body, "Skill file content")
    if not skill_raw:
        print("ERROR: Could not extract skill content from issue body.")
        sys.exit(1)

    skill_md = strip_fence(skill_raw) if "```" in skill_raw else skill_raw

    name_raw = extract_section(body, "Skill name")
    skill_name = (
        extract_frontmatter_field(skill_md, "name")
        or re.sub(r"\s+", "-", name_raw.strip().lower())
        or f"skill-{issue_number}"
    )
    description = extract_frontmatter_field(skill_md, "description") or ""
    owner = extract_section(body, "Author / contact") or "unknown"

    # Derive trigger line from description (first sentence after trigger keyword)
    trigger = ""
    m = re.search(r"[Tt]rigger\s+on[:\s]+(.+?)(?:\.|$)", description)
    if m:
        trigger = m.group(1).strip()

    skill_url = (
        f"https://github.com/icarofracassi/claude-code-skill-evals/blob/master/"
        f"skills/accepted/skill-{issue_number}.md"
    )

    evals = parse_evals_from_comments(comments)

    with open("index.html") as f:
        html = f.read()

    new_id = next_id(html)

    evals_js = json.dumps(evals, indent=4)
    # indent to match surrounding code
    evals_js = evals_js.replace("\n", "\n    ")

    entry = (
        f"  {{\n"
        f"    id: {new_id},\n"
        f"    name: {js_string(skill_name)},\n"
        f"    type: \"Skill\",\n"
        f"    cat: \"community\",\n"
        f"    owner: {js_string(owner)},\n"
        f"    desc: {js_string(description)},\n"
        f"    trigger: {js_string(trigger)},\n"
        f"    skillUrl: {js_string(skill_url)},\n"
        f"    issueUrl: {js_string(issue_url)},\n"
        f"    evals: {evals_js}\n"
        f"  }},"
    )

    sentinel = "  // ACCEPTED SKILLS - DO NOT EDIT MANUALLY"
    if sentinel not in html:
        print("ERROR: sentinel comment not found in index.html.")
        sys.exit(1)

    # Ensure item before sentinel has a trailing comma
    html = re.sub(r"\}\s*\n(\s*// ACCEPTED SKILLS)", r"},\n\1", html)

    updated = html.replace(sentinel, sentinel + "\n" + entry, 1)

    with open("index.html", "w") as f:
        f.write(updated)

    # Save the skill .md file
    os.makedirs("skills/accepted", exist_ok=True)
    with open(f"skills/accepted/skill-{issue_number}.md", "w") as f:
        f.write(skill_md)

    print(f"Published skill #{new_id}: {skill_name} ({len(evals)} eval results parsed)")


if __name__ == "__main__":
    main()
