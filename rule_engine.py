from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Optional
from rule_parser import Rule

@dataclass
class Claim:
    id: str
    employee: str
    department: str
    amount: float
    category: Optional[str] = None
    receipt: bool = True
    description: Optional[str] = None

@dataclass
class Decision:
    claim_id: str
    action: str
    matched_rule_id: Optional[str]
    matched_rule_text: Optional[str]
    matched_conditions: list[str]
    rationale: str
    confidence: float
    requires_human: bool
    trace: list[dict]
    def to_dict(self): return asdict(self)

OPS={"<":lambda a,b:a<b,"<=":lambda a,b:a<=b,">":lambda a,b:a>b,">=":lambda a,b:a>=b,"==":lambda a,b:a==b}

def check(rule: Rule, claim: Claim):
    c=rule.condition; conditions=[]
    if c.department:
        ok=c.department.strip().lower()==claim.department.strip().lower(); conditions.append(f"Department '{claim.department}' {'matches' if ok else 'does not match'} '{c.department}'")
        if not ok:return False,conditions
    if c.category:
        ok=bool(claim.category) and c.category.strip().lower()==claim.category.strip().lower(); conditions.append(f"Category '{claim.category}' {'matches' if ok else 'does not match'} '{c.category}'")
        if not ok:return False,conditions
    if c.amount_operator and c.amount_threshold is not None:
        ok=OPS[c.amount_operator](claim.amount,c.amount_threshold); conditions.append(f"Amount ${claim.amount:,.2f} {c.amount_operator} ${c.amount_threshold:,.2f}: {'true' if ok else 'false'}")
        if not ok:return False,conditions
    if c.receipt_required is not None:
        ok=claim.receipt == c.receipt_required; conditions.append(f"Receipt present: {'yes' if claim.receipt else 'no'}; required: {'yes' if c.receipt_required else 'no'}")
        if not ok:return False,conditions
    return True,conditions

def evaluate_claim(claim: Claim, rules: list[Rule]) -> Decision:
    ordered=sorted(rules,key=lambda r:r.priority)
    trace=[]
    for rule in ordered:
        ok,conds=check(rule,claim)
        trace.append({"rule_id":rule.id,"rule":rule.raw_text,"matched":ok,"conditions":conds,"action":rule.action})
        if ok:
            human=rule.action=="escalate"
            conf=0.98 if rule.condition.department or rule.condition.amount_threshold is not None else 0.90
            return Decision(claim.id,rule.action,rule.id,rule.raw_text,conds,
                f"Decision {rule.action.upper()} because rule {rule.id} matched: {rule.describe()}. The evaluation used the claim's actual fields and did not ask the LLM to make the business decision.",conf,human,trace)
    return Decision(claim.id,"escalate",None,None,[],"No configured rule matched this claim. PolicyPilot uses a safe default of ESCALATE so an uncovered expense is sent to human review instead of being silently approved.",0.65,True,trace)

def evaluate_batch(claims,rules): return [evaluate_claim(c,rules) for c in claims]
