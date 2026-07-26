# Claude Code Skill Evals

A GitHub Actions pipeline that automatically evaluates [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills when they are submitted via GitHub Issues.

## What is a Claude Code skill?

A Claude Code skill is a Markdown file that acts as a reusable prompt template. It lives in `~/.claude/skills/` and is invoked with a slash command (e.g. `/my-skill`). Skills define:

- **When to trigger** — natural-language routing conditions in the frontmatter `description`
- **What to do** — step-by-step instructions, output format, tone rules

This repo provides a structured submission + review workflow so teams can collaborate on skills and validate them before publishing.

---

## How it works

```
1. Contributor opens an issue using the "Submit a Skill" template
2. GitHub Actions fires on the "status: eval-pending" label
3. eval_skill.py runs 4 automated checks against the Claude API
4. Results are posted as a comment on the issue
5. Reviewer approves or requests changes
```

---

## Eval checks

| # | Eval | What it verifies |
|---|------|-----------------|
| 1 | **Structure lint** | Frontmatter has `name`, `description`, trigger language; no unresolved placeholders |
| 2 | **Trigger precision** | Claude judges whether the description is specific enough to route correctly |
| 3 | **Output quality** | Skill is run on user-provided test prompts; output is checked for expected keywords |
| 4 | **Scope adherence** | Out-of-scope prompts are correctly declined or redirected |

---

## Setup

### 1. Fork or clone this repo

### 2. Add your Anthropic API key

In **Settings → Secrets and variables → Actions**, add:

```
ANTHROPIC_API_KEY = sk-ant-...
```

### 3. Submit a skill

Open an issue using the **Submit a Skill** template. Paste your skill's `.md` content and optionally provide YAML test cases. The label `status: eval-pending` is applied automatically and triggers the workflow.

---

## Skill file format

```markdown
---
name: my-skill-name
description: >
  One or two sentences describing what this skill does and when to invoke it.
  Include trigger phrases and what NOT to trigger on.
---

# My Skill

Detailed instructions here…
```

See [`skills/examples/`](skills/examples/) for working examples.

---

## Local development

Install dependencies:

```bash
pip install anthropic pyyaml
```

Set your API key and run the eval script directly:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# write your issue body to /tmp/issue_body.txt first, then:
python scripts/eval_skill.py
```

---

## Repository structure

```
.github/
  ISSUE_TEMPLATE/
    submit-skill.yml       # Issue template for skill submissions
  workflows/
    eval-skill.yml         # Workflow: runs evals on labeled issues
scripts/
  eval_skill.py            # Core eval logic
skills/
  examples/
    email-triage.md        # Example skill: email triage assistant
```
