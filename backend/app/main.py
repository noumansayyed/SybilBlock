from pathlib import Path
from datetime import datetime, timezone
import sqlite3, json, os
import joblib, pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

BASE=Path(__file__).resolve().parents[1]
ENV_FILE = BASE / ".env"
load_dotenv(ENV_FILE, override=True)

print("ENV FILE:", ENV_FILE)
print("ENV EXISTS:", ENV_FILE.exists())
print("BLOCKCHAIN_ENABLED:", repr(os.getenv("BLOCKCHAIN_ENABLED")))
print("RPC_URL:", repr(os.getenv("RPC_URL")))
print("CONTRACT_ADDRESS:", repr(os.getenv("CONTRACT_ADDRESS")))

MODEL_PATH=BASE/"models/sybil_model.joblib"
DB=BASE/"sybilblock.db"
app=FastAPI(title="SybilBlock API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_methods=["*"],allow_headers=["*"])
bundle=None

class Input(BaseModel):
    account_id: str=Field(min_length=2,max_length=80,pattern=r"^[a-zA-Z0-9_.-]+$")
    account_age_days:int=Field(ge=0,le=20000)
    posts_per_day:float=Field(ge=0,le=10000)
    followers_count:int=Field(ge=0)
    following_count:int=Field(ge=0)
    account_activity_hours:float=Field(ge=0,le=24)
    duplicate_content_ratio:float=Field(ge=0,le=1)
    interaction_rate:float=Field(ge=0,le=1)
    shared_device_count:int=Field(ge=1)
    registration_burst_count:int=Field(ge=0)

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS analyses(
        id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT, probability REAL, score INTEGER,
        category TEXT, version TEXT, analyzed_at TEXT, tx_hash TEXT, chain_status TEXT, features TEXT)""")

@app.on_event("startup")
def startup():
    global bundle
    init_db()
    if MODEL_PATH.exists(): bundle=joblib.load(MODEL_PATH)

def category(score):
    return "High risk" if score<30 else "Medium risk" if score<60 else "Elevated trust" if score<80 else "High trust"

def chain_write(account_id,score,version):
    if os.getenv("BLOCKCHAIN_ENABLED","false").lower()!="true":
        return {"status":"demo-only","tx_hash":None,"message":"Blockchain disabled; saved locally."}
    try:
        from web3 import Web3
        rpc=os.getenv("RPC_URL","http://127.0.0.1:8545"); address=os.getenv("CONTRACT_ADDRESS",""); key=os.getenv("PRIVATE_KEY","")
        if not address or not key: return {"status":"failed","tx_hash":None,"message":"Missing contract address or local key."}
        w=Web3(Web3.HTTPProvider(rpc,request_kwargs={"timeout":4}))
        if not w.is_connected(): return {"status":"failed","tx_hash":None,"message":"Local blockchain not reachable."}
        abi=[
        {"inputs":[{"internalType":"bytes32","name":"accountId","type":"bytes32"},{"internalType":"uint8","name":"score","type":"uint8"},{"internalType":"string","name":"modelVersion","type":"string"}],"name":"updateTrustScore","outputs":[],"stateMutability":"nonpayable","type":"function"},
        {"inputs":[{"internalType":"bytes32","name":"accountId","type":"bytes32"}],"name":"getAccountRecord","outputs":[{"internalType":"uint8","name":"trustScore","type":"uint8"},{"internalType":"uint64","name":"updatedAt","type":"uint64"},{"internalType":"string","name":"modelVersion","type":"string"},{"internalType":"bool","name":"exists","type":"bool"}],"stateMutability":"view","type":"function"}]
        acct=w.eth.account.from_key(key); contract=w.eth.contract(address=Web3.to_checksum_address(address),abi=abi)
        tx=contract.functions.updateTrustScore(Web3.keccak(text=account_id),score,version).build_transaction({"from":acct.address,"nonce":w.eth.get_transaction_count(acct.address),"chainId":w.eth.chain_id,"gas":250000,"gasPrice":w.eth.gas_price})
        signed=acct.sign_transaction(tx); raw=getattr(signed,"raw_transaction",None) or signed.rawTransaction
        txh=w.eth.send_raw_transaction(raw); receipt=w.eth.wait_for_transaction_receipt(txh,timeout=15)
        return {"status":"confirmed" if receipt.status==1 else "failed","tx_hash":txh.hex(),"message":"Score recorded on local chain." if receipt.status==1 else "Transaction reverted."}
    except Exception as e: return {"status":"failed","tx_hash":None,"message":"Blockchain write failed: "+type(e).__name__}

@app.get("/api/health")
def health(): return {"status":"ok","model_loaded":bundle is not None}

@app.post("/api/analyze")
def analyze(x:Input):
    if bundle is None: raise HTTPException(503,"Model missing. Run python train_model.py in backend.")
    data=x.model_dump(); account=data.pop("account_id"); feats=bundle["features"]
    row=pd.DataFrame([[data[k] for k in feats]],columns=feats)
    p=float(bundle["model"].predict_proba(row)[0][1]); score=max(0,min(100,round((1-p)*100)))
    version=bundle.get("version","rf-v1"); now=datetime.now(timezone.utc).isoformat(); ch=chain_write(account,score,version)
    with db() as c:
        cur=c.execute("INSERT INTO analyses(account_id,probability,score,category,version,analyzed_at,tx_hash,chain_status,features) VALUES(?,?,?,?,?,?,?,?,?)",
        (account,p,score,category(score),version,now,ch["tx_hash"],ch["status"],json.dumps(data)))
        rid=cur.lastrowid
    importance=sorted([{"feature":k,"importance":round(float(v),4)} for k,v in zip(feats,bundle["model"].feature_importances_)],key=lambda x:x["importance"],reverse=True)[:5]
    return {"id":rid,"account_id":account,"sybil_probability":round(p,4),"trust_score":score,"risk_category":category(score),"model_version":version,"analyzed_at":now,"blockchain_status":ch["status"],"blockchain_message":ch["message"],"transaction_hash":ch["tx_hash"],"feature_importance":importance}

@app.get("/api/accounts")
def accounts(limit:int=100):
    with db() as c: rows=c.execute("SELECT id,account_id,probability AS sybil_probability,score AS trust_score,category AS risk_category,version AS model_version,analyzed_at,tx_hash,chain_status AS blockchain_status FROM analyses ORDER BY id DESC LIMIT ?",(max(1,min(limit,500)),)).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/dashboard/stats")
def stats():
    with db() as c:
        total=c.execute("SELECT COUNT(*) n FROM analyses").fetchone()["n"]
        high=c.execute("SELECT COUNT(*) n FROM analyses WHERE score<30").fetchone()["n"]
        avg=c.execute("SELECT AVG(score) n FROM analyses").fetchone()["n"]
        recent=c.execute("SELECT id,account_id,score AS trust_score,category AS risk_category,analyzed_at,chain_status AS blockchain_status FROM analyses ORDER BY id DESC LIMIT 5").fetchall()
    return {"total_analyzed":total,"high_risk":high,"average_trust_score":round(avg,1) if avg is not None else None,"recent":[dict(r) for r in recent]}

@app.get("/api/accounts/{account_id}/history")
def history(account_id:str):
    with db() as c: rows=c.execute("SELECT id,account_id,probability AS sybil_probability,score AS trust_score,category AS risk_category,version AS model_version,analyzed_at,tx_hash,chain_status AS blockchain_status FROM analyses WHERE account_id=? ORDER BY id DESC",(account_id,)).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/accounts/{account_id}/verify")
def verify(account_id:str):
    if os.getenv("BLOCKCHAIN_ENABLED","false").lower()!="true":
        return {"status":"demo-only","record":None,"matches_latest_local_score":None,"message":"Enable Hardhat and configure backend/.env to verify on-chain."}
    try:
        from web3 import Web3
        w=Web3(Web3.HTTPProvider(os.getenv("RPC_URL","http://127.0.0.1:8545"),request_kwargs={"timeout":4}))
        abi=[{"inputs":[{"internalType":"bytes32","name":"accountId","type":"bytes32"}],"name":"getAccountRecord","outputs":[{"internalType":"uint8","name":"trustScore","type":"uint8"},{"internalType":"uint64","name":"updatedAt","type":"uint64"},{"internalType":"string","name":"modelVersion","type":"string"},{"internalType":"bool","name":"exists","type":"bool"}],"stateMutability":"view","type":"function"}]
        con=w.eth.contract(address=Web3.to_checksum_address(os.getenv("CONTRACT_ADDRESS","")),abi=abi)
        score,ts,version,exists=con.functions.getAccountRecord(Web3.keccak(text=account_id)).call()
        if not exists:return {"status":"not-found","record":None,"matches_latest_local_score":None,"message":"No on-chain record."}
        with db() as c: local=c.execute("SELECT score FROM analyses WHERE account_id=? ORDER BY id DESC LIMIT 1",(account_id,)).fetchone()
        return {"status":"verified","record":{"trust_score":score,"updated_at":ts,"model_version":version},"matches_latest_local_score":bool(local and local["score"]==score),"message":"Read directly from local contract."}
    except Exception as e:return {"status":"failed","record":None,"matches_latest_local_score":None,"message":"Verification failed: "+type(e).__name__}
