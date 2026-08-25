from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from rule_parser import parse_rules, RuleParseError
from rule_engine import Claim, evaluate_batch

BASE=Path(__file__).parent; DATA=BASE/'sample_data'
app=FastAPI(title='PolicyPilot API',version='1.0.0',description='Policy-driven expense approval agent')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
STATE={'rules':[],'claims':[],'policy_text':'','parser':'','decisions':[]}

def sample_claims(): return [Claim(**x) for x in json.loads((DATA/'claims.json').read_text())]
def sample_text(): return (DATA/'rules.txt').read_text().strip()

class RulesIn(BaseModel): rules_text:str=Field(min_length=1)
class ClaimIn(BaseModel):
    id:str; employee:str; department:str; amount:float=Field(ge=0); category:Optional[str]=None; receipt:bool=True; description:Optional[str]=None
class ClaimsIn(BaseModel): claims:list[ClaimIn]
class RuleOrderIn(BaseModel): priorities:dict[str,int]

@app.on_event('startup')
def startup():
    STATE['claims']=sample_claims(); STATE['policy_text']=sample_text()
    try: STATE['rules'],STATE['parser']=parse_rules(STATE['policy_text'])
    except RuleParseError: pass

@app.get('/api/health')
def health(): return {'status':'ok','service':'PolicyPilot','version':'1.0.0'}
@app.get('/api/state')
def state():
    decisions=evaluate_batch(STATE['claims'],STATE['rules']) if STATE['rules'] else []
    counts={k:sum(d.action==k for d in decisions) for k in ['approve','reject','escalate']}
    return {'policy_text':STATE['policy_text'],'parser':STATE['parser'],'rules':[r.to_dict() for r in STATE['rules']], 'claims':[c.__dict__ for c in STATE['claims']], 'decisions':[d.to_dict() for d in decisions], 'summary':{'total':len(decisions),**counts}}
@app.post('/api/rules/parse')
def parse(payload:RulesIn):
    try: rules,parser=parse_rules(payload.rules_text)
    except RuleParseError as e: raise HTTPException(422,str(e))
    STATE.update(rules=rules,policy_text=payload.rules_text,parser=parser,decisions=[])
    return {'rules':[r.to_dict() for r in rules],'parser':parser}
@app.post('/api/rules/reorder')
def reorder(payload:RuleOrderIn):
    missing=[r.id for r in STATE['rules'] if r.id not in payload.priorities]
    if missing: raise HTTPException(400,f'Missing priorities for: {missing}')
    for r in STATE['rules']: r.priority=payload.priorities[r.id]
    STATE['rules'].sort(key=lambda r:r.priority)
    return {'rules':[r.to_dict() for r in STATE['rules']]}
@app.post('/api/rules/sample')
def sample_rules():
    try: rules,parser=parse_rules(sample_text())
    except RuleParseError as e: raise HTTPException(500,str(e))
    STATE.update(rules=rules,policy_text=sample_text(),parser=parser)
    return {'rules':[r.to_dict() for r in rules],'policy_text':sample_text(),'parser':parser}
@app.post('/api/claims/load')
def load_claims(payload:Optional[ClaimsIn]=None):
    STATE['claims']=sample_claims() if payload is None or not payload.claims else [Claim(**c.model_dump()) for c in payload.claims]
    STATE['decisions']=[]
    return {'claims':[c.__dict__ for c in STATE['claims']]}
@app.get('/api/claims')
def claims(): return {'claims':[c.__dict__ for c in STATE['claims']]}
@app.post('/api/evaluate')
def evaluate():
    if not STATE['rules']: raise HTTPException(400,'No rules configured.')
    if not STATE['claims']: raise HTTPException(400,'No claims loaded.')
    ds=evaluate_batch(STATE['claims'],STATE['rules']); STATE['decisions']=ds
    return {'decisions':[d.to_dict() for d in ds]}
@app.get('/api/decisions/{claim_id}')
def decision(claim_id:str):
    ds=STATE['decisions'] or (evaluate_batch(STATE['claims'],STATE['rules']) if STATE['rules'] else [])
    for d in ds:
        if d.claim_id==claim_id:return d.to_dict()
    raise HTTPException(404,'Decision not found')
app.mount('/static',StaticFiles(directory=str(BASE/'static')),name='static')
@app.get('/')
def index(): return FileResponse(BASE/'static'/'index.html')
