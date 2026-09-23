from .retrieval import retrieve
def answer(session,repo_id:int,question:str)->dict:
    chunks=retrieve(session,repo_id,question);citations=[{"path":c.path,"start_line":c.start_line,"end_line":c.end_line,"symbol":c.symbol} for c in chunks]
    if not chunks:return {"answer":"No relevant code was found in the current index.","citations":[],"mode":"retrieval-only"}
    evidence="\n\n".join(f"{c.path}:{c.start_line}-{c.end_line} ({c.symbol})\n{c.content[:900]}" for c in chunks)
    return {"answer":f"Retrieved {len(chunks)} repository-level code regions. The strongest evidence is in {chunks[0].path}::{chunks[0].symbol}. Configure an LLM provider to synthesize a deeper explanation or patch plan.\n\nEvidence preview:\n{evidence[:1600]}","citations":citations,"mode":"retrieval-only"}
def plan(session,repo_id:int,request:str)->dict:
    chunks=retrieve(session,repo_id,request,12);files=list(dict.fromkeys(c.path for c in chunks));return {"request":request,"steps":[{"order":i+1,"file":f,"action":"inspect and modify","reason":"retrieved by symbol, lexical, and dependency relevance"} for i,f in enumerate(files)],"citations":[{"path":c.path,"start_line":c.start_line,"end_line":c.end_line} for c in chunks],"diff":"","status":"proposal"}

