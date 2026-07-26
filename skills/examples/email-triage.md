---
name: email-triage
description: >
  Triage an incoming support email or ticket by classifying its urgency,
  extracting key entities, and suggesting a next action.
  Use this skill when the user pastes an email or ticket body and wants to know
  what to do with it, how urgent it is, or how to categorize it.
  Trigger on: "triage this", "how urgent is this", "what should I do with this email",
  "classify this ticket", "prioritize this".
  Do NOT trigger on: requests to write a reply, requests to resolve the underlying issue,
  or general questions about email tools.
---

# Email Triage

Classify the incoming email or ticket and produce a structured triage note.

---

## Step 1 — Extract signals

Read the message. Identify:

- **Subject line** (if present)
- **Reported issue** — one sentence summary
- **Sender type** — customer, colleague, automated system, unknown
- **Urgency signals** — words like "urgent", "broken", "production down", "ASAP", "critical"
- **Sentiment** — frustrated, neutral, calm, confused

---

## Step 2 — Classify urgency

Assign one of:

| Level | Criteria |
|-------|----------|
| **P1 — Critical** | Production system down, data loss, security incident, deadline today |
| **P2 — High** | Core workflow blocked, no workaround available |
| **P3 — Medium** | Issue exists but workaround available; not blocking |
| **P4 — Low** | How-to question, feature request, informational |

---

## Step 3 — Output

Produce a triage note in this format:

```
URGENCY:   P? — [Level name]
SUMMARY:   [One sentence: who is affected and what is broken/needed]
SENTIMENT: [Frustrated | Neutral | Calm | Confused]
ACTION:    [Suggested next step — e.g. "Escalate to on-call", "Reply with workaround", "Route to billing team"]
```

Do not write a reply. Do not attempt to resolve the issue. Output the triage note only.
