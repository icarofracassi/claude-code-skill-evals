"""
publish_skill.py — Appends an accepted skill to the ITEMS array in index.html.

Reads /tmp/issue_body.txt (raw GitHub issue body) and env vars:
  ISSUE_NUMBER, ISSUE_URL

Inserts a new JS object before the sentinel comment:
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


def main() -> None:
    body = read_issue()
    issue_number = os.environ.get("ISSUE_NUMBER", "0")
    issue_url = os.environ.get("ISSUE_URL", "")

    skill_raw = extract_section(body, "Skill file content")
    if not skill_raw:
        print("ERROR: Could not extract skill content from issue body.")
        sys.exit(1)

    skill_md = strip_fence(skill_raw) if "```" in skill_raw else skill_raw

    name_raw = extract_section(body, "Skill name")
    skill_name = extract_frontmatter_field(skill_md, "name") or name_raw or f"Skill #{issue_number}"
    description = extract_frontmatter_field(skill_md, "description") or ""
    owner = extract_section(body, "Author / contact") or "unknown"

    skill_url = (
        f"https://github.com/icarofracassi/claude-code-skill-evals/blob/master/"
        f"skills/accepted/skill-{issue_number}.md"
    )

    with open("index.html") as f:
        html = f.read()

    new_id = next_id(html)

    entry = f"""  {{
    id: {new_id},
    name: {js_string(skill_name)},
    type: "Skill",
    tags: ["Community"],
    phase: "Released",
    owner: {js_string(owner)},
    desc: {js_string(description)},
    skillUrl: {js_string(skill_url)},
    issueUrl: {js_string(issue_url)},
    evals: []
  }},"""

    sentinel = "  // ACCEPTED SKILLS - DO NOT EDIT MANUALLY"
    if sentinel not in html:
        print("ERROR: sentinel comment not found in index.html.")
        sys.exit(1)

    # Ensure the item immediately before the sentinel has a trailing comma.
    # Covers both the hardcoded first item (ends with `}`) and previously
    # inserted items (end with `},`).
    html = re.sub(r"\}\s*\n(\s*// ACCEPTED SKILLS)", r"},\n\1", html)

    updated = html.replace(sentinel, sentinel + "\n" + entry, 1)

    with open("index.html", "w") as f:
        f.write(updated)

    # Also save the skill .md file
    os.makedirs("skills/accepted", exist_ok=True)
    with open(f"skills/accepted/skill-{issue_number}.md", "w") as f:
        f.write(skill_md)

    print(f"Published skill #{new_id}: {skill_name}")


if __name__ == "__main__":
    main()
