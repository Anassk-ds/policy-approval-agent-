from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass
from typing import Optional

ACTIONS = {"approve", "reject", "escalate"}
OPERATORS = {"<", "<=", ">", ">=", "=="}

@dataclass
class Condition:
    department: Optional[str] = None
    amount_operator: Optional[str] = None
    amount_threshold: Optional[float] = None
    category: Optional[str] = None
    receipt_required: Optional[bool] = None

@dataclass
class Rule:
    id: str
    raw_text: str
    action: str
    condition: Condition
    priority: int
    notes: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    def describe(self) -> str:
        parts = [self.action.upper()]
        c = self.condition
        if c.department:
            parts.append(f"for {c.department}")
        if c.category:
            parts.append(f"category={c.category}")
        if c.amount_operator and c.amount_threshold is not None:
            parts.append(f"amount {c.amount_operator} ${c.amount_threshold:,.2f}")
        if c.receipt_required is True:
            parts.append("receipt required")
        if c.receipt_required is False:
            parts.append("receipt not required")
        return " ".join(parts)

class RuleParseError(Exception):
    pass

def _id() -> str:
    return f"R-{uuid.uuid4().hex[:6].upper()}"

SYSTEM_PROMPT = """Convert plain-English expense approval policies into strict JSON. Return only a JSON array.
Each item: {raw_text, action, department, amount_operator, amount_threshold, category, receipt_required, notes}.
action must be approve, reject, or escalate. Operators: <, <=, >, >=, ==. Split compound policies into separate rules.
Receipt phrases: 'without a receipt' => receipt_required true; 'with receipt' => true.
Preserve order. Do not invent conditions. If ambiguous, leave the uncertain field null and explain in notes."""

def parse_rules_llm(text: str) -> list[Rule]:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    resp = client.messages.create(model=model, max_tokens=3000, system=SYSTEM_PROMPT, messages=[{"role":"user","content":text}])
    raw = "".join(x.text for x in resp.content if getattr(x, "type", None) == "text").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuleParseError(f"LLM returned invalid JSON: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise RuleParseError("The policy parser returned no rules.")
    rules=[]
    for i, item in enumerate(data):
        action=str(item.get("action", "")).lower()
        if action not in ACTIONS: raise RuleParseError(f"Invalid action: {action}")
        op=item.get("amount_operator")
        if op not in OPERATORS and op is not None: raise RuleParseError(f"Invalid operator: {op}")
        rules.append(Rule(_id(), item.get("raw_text") or "", action, Condition(
            department=item.get("department"), amount_operator=op,
            amount_threshold=item.get("amount_threshold"), category=item.get("category"),
            receipt_required=item.get("receipt_required")), i, item.get("notes") or None))
    return rules

ACTION_RE = re.compile(r"\b(auto-approve|approve|reject|deny|escalate)\b", re.I)
AMOUNT_RE = re.compile(r"\b(under|below|less than|over|above|more than|at least|at most|up to|equal to)\s*\$?\s*([\d,]+(?:\.\d+)?)", re.I)
DEPT_RE = re.compile(r"\bfor\s+([A-Za-z][A-Za-z &/-]*?)(?=\s+(?:under|below|over|above|with|without|in|on)\b|[.,;]|$)", re.I)
CATEGORY_RE = re.compile(r"\b(?:in|for)\s+(?:the\s+)?(travel|meals?|software|advertising|office|training|equipment|accommodation|transport)\b", re.I)

OP_MAP={"under":"<","below":"<","less than":"<","over":">","above":">","more than":">","at least":">=","at most":"<=","up to":"<=","equal to":"=="}

def _split(text: str) -> list[str]:
    lines=[x.strip() for x in re.split(r"[\n]+", text) if x.strip()]
    out=[]
    for line in lines:
        pieces=re.split(r"[,;]\s*(?=(?:auto-approve|approve|reject|deny|escalate)\b)", line, flags=re.I)
        out.extend(p.strip().rstrip(".") for p in pieces if p.strip())
    return out

def parse_rules_fallback(text: str) -> list[Rule]:
    rules=[]
    for i, clause in enumerate(_split(text)):
        m=ACTION_RE.search(clause)
        if not m: continue
        action_raw=m.group(1).lower()
        action="approve" if action_raw in {"approve","auto-approve"} else ("reject" if action_raw in {"reject","deny"} else "escalate")
        am=AMOUNT_RE.search(clause)
        op=OP_MAP.get(am.group(1).lower()) if am else None
        threshold=float(am.group(2).replace(",", "")) if am else None
        dm=DEPT_RE.search(clause)
        dept=dm.group(1).strip().title() if dm else None
        cm=CATEGORY_RE.search(clause)
        category=cm.group(1).title() if cm else None
        low=clause.lower()
        receipt_required=False if "without a receipt" in low or "without receipt" in low else (True if "with a receipt" in low or "with receipt" in low else None)
        notes=[]
        if not am: notes.append("No amount threshold detected.")
        if "any expense" in low or "all expenses" in low: notes.append("Broad rule applies unless a later condition limits it.")
        rules.append(Rule(_id(), clause, action, Condition(dept,op,threshold,category,receipt_required), i, " ".join(notes) or None))
    if not rules: raise RuleParseError("No recognizable policy rules found. Use actions such as approve, reject, or escalate.")
    return rules

def parse_rules(text: str) -> tuple[list[Rule], str]:
    if not text.strip(): raise RuleParseError("Policy text cannot be empty.")
    if os.getenv("ANTHROPIC_API_KEY"):
        try: return parse_rules_llm(text), "llm"
        except Exception as exc: return parse_rules_fallback(text), f"fallback ({type(exc).__name__})"
    return parse_rules_fallback(text), "local"
