# PolicyPilot — Policy-Driven Approval Agent

PolicyPilot is an assessment-ready implementation of **Supervity FDE Assessment — Problem 4: Policy-Driven Approval Agent**.

## Problem

The system accepts plain-English business rules such as:

> Auto-approve expenses under $500 for Sales.

> Escalate expenses above $2,000.

It applies those configurable rules to a batch of expense claims and returns **APPROVE**, **REJECT**, or **ESCALATE** with a traceable rationale.

## Architecture

```text
Plain-English Policy
        |
        v
+---------------------+
| Policy Parser       |  <-- optional LLM / local fallback
+---------------------+
        |
        v
Structured Rules
        |
        v
+---------------------+
| Deterministic Rule  |
| Engine              |
+---------------------+
        |
        +----> Decision
        +----> Rule ID
        +----> Condition trace
        +----> Rationale
        +----> Confidence / human review
```

### Key design tradeoff

The LLM is used for **translation**, not final business judgment. Once a policy is converted to structured rules, the deterministic Python rule engine evaluates every claim. This makes decisions reproducible, inspectable, and auditable while still allowing a non-technical user to write policies in natural language.

## Features

- Plain-English policy configuration
- Optional Anthropic LLM policy parser
- Deterministic local parser fallback
- Structured rule preview
- Configurable rule priority
- Batch expense claim evaluation
- Approve / Reject / Escalate outcomes
- Safe default escalation when no rule matches
- Rule-by-rule audit trace
- Human-review indicator
- Confidence score
- Responsive dashboard
- Mock data included
- FastAPI REST API

## Setup

### 1. Create a virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\\Scripts\\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Optional AI configuration

Copy `.env.example` to `.env` and set:

```text
ANTHROPIC_API_KEY=your_key
ANTHROPIC_MODEL=claude-sonnet-4-6
```

If the key is absent, the application uses its local deterministic policy parser, so the demo remains runnable without an external API.

### 4. Run

```bash
uvicorn app:app --reload
```

Open `http://localhost:8000`.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/state` | Complete current state |
| POST | `/api/rules/parse` | Parse plain-English rules |
| POST | `/api/rules/sample` | Load sample rules |
| POST | `/api/rules/reorder` | Change rule priority |
| GET | `/api/claims` | Read claims |
| POST | `/api/claims/load` | Load a claim batch |
| POST | `/api/evaluate` | Run the deterministic engine |
| GET | `/api/decisions/{claim_id}` | Read one decision trace |

## Example policy

```text
Auto-approve expenses under $500 for Sales.
Reject any expense without a receipt.
Escalate expenses above $2,000.
Auto-approve expenses up to $250 for Marketing.
```

## Assumptions

1. Rules are evaluated in priority order; the first matching rule wins.
2. A claim with no matching rule is escalated rather than automatically approved.
3. Claims use mock/synthetic data only.
4. A receipt requirement is represented as a boolean claim field.
5. The local parser is intentionally scoped to common policy language. The optional LLM parser handles broader natural-language phrasing.
6. The demo stores state in memory. A production deployment would use persistent storage and authentication.

## Edge cases demonstrated

- No matching rule → ESCALATE
- Missing receipt → can trigger REJECT
- Conflicting broad and specific rules → priority order makes precedence explicit
- Ambiguous/unsupported policy language → parser notes or validation error
- LLM/API unavailable → local fallback parser keeps the demo usable

## 5-minute demo plan

### 0:00–2:00 — Architecture

Explain the separation between policy interpretation and deterministic execution.

### 2:00–4:00 — Live walkthrough

1. Show the dashboard and sample claims.
2. Enter/edit a plain-English policy.
3. Parse the policy and show structured rules.
4. Run the approval engine.
5. Show approve, reject, and escalate outcomes.
6. Inspect one claim and show its audit trace.

### 4:00–5:00 — Tradeoff

Explain why the LLM does not directly approve expenses. The LLM translates natural language into a structured policy; deterministic code evaluates claims. This improves reproducibility, traceability, latency, and auditability.

## Assessment alignment

The project directly addresses the brief's Problem 4 requirements:

- Plain-English rules are configuration, not hardcoded decision logic.
- Rules are applied to a batch of sample claims.
- Each claim receives a decision and rationale.
- The UI exposes how policies can be edited.
- The system demonstrates priority and edge-case handling.

## Project structure

```text
policypilot/
├── app.py
├── rule_parser.py
├── rule_engine.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── sample_data/
│   ├── rules.txt
│   └── claims.json
└── static/
    └── index.html
```

## Production improvements

For a production system, add authentication/RBAC, persistent storage, immutable audit logs, rule versioning, approval workflows, observability, automated tests, rate limiting, and a human review queue.
