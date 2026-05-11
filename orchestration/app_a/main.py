"""
app_a/main.py  (v2)
────────────────────
App A — Documentation Application.

What changed from v1:
  ① Prompt ownership  → PromptLibrary owns all prompts. Users never set templates.
  ② Batch processing  → POST /batch/analyze accepts N tables at once.
  ③ Single stream     → GET /stream/{session_id}: one SSE connection per user,
                         all batches, all tables flow through it.

Run:
    uvicorn app_a.main:app --port 8000 --reload
"""
from __future__ import annotations

import asyncio
import logging
import sys
import pathlib
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from shared.contracts import BatchAnalyzeRequest
from app_a.batch import (
    _session_queues,
    get_or_create_session_queue,
    list_batches_for_session,
    get_batch,
    orchestrator,
)
from app_a.prompt_library import PromptLibrary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ─────────────────────────────────────────────────────────────────
# SSE generator — one per session, lives forever
# ─────────────────────────────────────────────────────────────────

async def _session_stream(session_id: str) -> AsyncGenerator[str, None]:
    """
    Drains the session queue and yields SSE frames.
    Sends keepalive comments every 15 s so proxies don't kill the connection.
    The stream is intentionally long-lived — it doesn't close when a batch ends.
    """
    queue = get_or_create_session_queue(session_id)
    while True:
        try:
            frame = await asyncio.wait_for(queue.get(), timeout=15.0)
            if frame is None:
                yield ": session-closed\n\n"
                break
            yield frame
        except asyncio.TimeoutError:
            yield ": keepalive\n\n"


# ─────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Documentation App (App A) v2",
    version="2.0.0",
    description="Batch doc analysis. Many tables in, one stream out.",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Main endpoints ──────────────────────────────────────────────────────────

@app.post("/batch/analyze", status_code=202, summary="Submit N tables for analysis")
async def batch_analyze(request: BatchAnalyzeRequest) -> dict:
    """
    User submits tables + context + preset.
    App A builds the prompt (user never touches NodeConfig or prompt_template).
    Processing starts immediately; results stream to GET /stream/{session_id}.
    """
    if request.preset not in PromptLibrary.available_presets():
        raise HTTPException(
            status_code=422,
            detail=f"Unknown preset '{request.preset}'. Available: {PromptLibrary.available_presets()}",
        )

    batch = await orchestrator.submit_batch(
        session_id=request.session_id,
        user_id=request.user_id,
        tables=request.tables,
        document_context=request.document_context,
        preset=request.preset,
        concurrency=request.concurrency,
    )

    return {
        "batch_id":    batch.batch_id,
        "session_id":  batch.session_id,
        "total":       len(batch.table_jobs),
        "preset":      batch.preset,
        "concurrency": request.concurrency,
        "stream_url":  f"/stream/{batch.session_id}",  # same URL regardless of batch count
        "status_url":  f"/batch/{batch.batch_id}",
        "tables": [
            {"index": tj.table_index, "title": tj.table_title, "job_id": tj.job_id}
            for tj in batch.table_jobs
        ],
    }


@app.get("/stream/{session_id}", summary="One SSE stream for all batches in this session")
async def session_stream(session_id: str) -> StreamingResponse:
    """
    Connect ONCE per session. All events from all tables across all batches
    arrive here tagged with batch_id + table_index. Never reconnect.
    """
    return StreamingResponse(
        _session_stream(session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ── Status endpoints ────────────────────────────────────────────────────────

@app.get("/batch/{batch_id}", summary="Batch status + per-table progress")
async def get_batch_status(batch_id: str) -> dict:
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return {
        "batch_id":     batch.batch_id,
        "session_id":   batch.session_id,
        "preset":       batch.preset,
        "created_at":   batch.created_at.isoformat(),
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        "progress":     batch.progress().model_dump(),
        "tables": [
            {
                "index":      tj.table_index,
                "title":      tj.table_title,
                "job_id":     tj.job_id,
                "status":     tj.status,
                "error":      tj.error,
                "has_result": tj.result is not None,
            }
            for tj in batch.table_jobs
        ],
    }


@app.get("/batch/{batch_id}/results", summary="Completed results for all tables in a batch")
async def get_batch_results(batch_id: str) -> dict:
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return {
        "batch_id": batch_id,
        "results": [
            {
                "table_index": tj.table_index,
                "table_title": tj.table_title,
                "status":      tj.status,
                "output":      tj.result.final_output if tj.result else None,
                "error":       tj.error,
            }
            for tj in batch.table_jobs
        ],
    }


@app.get("/session/{session_id}/batches", summary="All batches submitted in this session")
async def get_session_batches(session_id: str) -> dict:
    batches = list_batches_for_session(session_id)
    return {
        "session_id":  session_id,
        "batch_count": len(batches),
        "batches": [
            {
                "batch_id":   b.batch_id,
                "total":      len(b.table_jobs),
                "progress":   b.progress().model_dump(),
                "created_at": b.created_at.isoformat(),
            }
            for b in batches
        ],
    }


@app.get("/presets", summary="Available pipeline presets")
async def list_presets() -> dict:
    return {"presets": PromptLibrary.available_presets()}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "active_sessions": len(_session_queues)}


# ─────────────────────────────────────────────────────────────────
# Test UI
# ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DocPipeline v2</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Courier New',monospace;background:#0d0d0d;color:#ccc;padding:24px}
  h1{color:#fff;margin-bottom:2px}
  .sub{color:#444;font-size:11px;margin-bottom:20px}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
  label{font-size:10px;color:#444;letter-spacing:1px;text-transform:uppercase;display:block;margin-bottom:3px}
  input,select,textarea{width:100%;background:#111;color:#0f0;border:1px solid #222;
    padding:7px 10px;font-family:monospace;font-size:12px;border-radius:4px}
  textarea{resize:vertical}
  button{background:#0f0;color:#000;border:none;padding:9px 20px;font-weight:bold;
    cursor:pointer;border-radius:4px;font-size:12px;margin-right:6px}
  button.sec{background:#111;color:#0f0;border:1px solid #222}
  button:disabled{background:#222;color:#444;cursor:default}
  #pb-wrap{background:#1a1a1a;border-radius:3px;height:4px;margin:12px 0}
  #pb{height:4px;background:#0f0;border-radius:3px;width:0%;transition:width .3s}
  #stats{font-size:10px;color:#444;margin-bottom:8px}
  #grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));
    gap:6px;max-height:200px;overflow-y:auto;margin-bottom:12px}
  .card{background:#111;border:1px solid #1f1f1f;border-radius:5px;padding:8px;font-size:10px}
  .card .t{color:#ccc;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-bottom:2px}
  .card .s{color:#444}
  .card.run{border-color:#4af}.card.run .s{color:#4af}
  .card.ok {border-color:#0f0}.card.ok  .s{color:#0f0}
  .card.err{border-color:#f44}.card.err .s{color:#f44}
  #log{background:#111;border:1px solid #1f1f1f;padding:10px;height:240px;
    overflow-y:auto;font-size:11px;line-height:1.65;border-radius:4px;white-space:pre-wrap}
  .tok{color:#0f0}.inf{color:#4af}.wrn{color:#fa4}.er{color:#f44}.dn{color:#f4f;font-weight:bold}
</style>
</head>
<body>
<h1>📄 DocPipeline v2</h1>
<p class="sub">Submit many tables — subscribe to one stream.</p>

<div class="row">
  <div><label>Session ID</label><input id="sid" placeholder="auto-generated"/></div>
  <div><label>User ID</label><input id="uid" value="user-001"/></div>
</div>
<div class="row">
  <div>
    <label>Preset</label>
    <select id="preset">
      <option value="default">default — commentary → validation</option>
      <option value="commentary_only">commentary_only</option>
      <option value="full_with_summary">full_with_summary</option>
    </select>
  </div>
  <div><label>Concurrency</label><input id="conc" type="number" value="3" min="1" max="20"/></div>
</div>
<div style="margin-bottom:10px">
  <label>Document Context</label>
  <input id="ctx" value="Annual financial report, FY 2026, India operations"/>
</div>
<div style="margin-bottom:12px">
  <label>Tables (JSON array)</label>
  <textarea id="json" rows="8">[
  {"title":"Revenue by Region Q1 2026","columns":["Region","Revenue (₹ Cr)","YoY Growth"],"rows":[["North",56.8,"+34.9%"],["South",41.2,"+6.5%"],["West",49.1,"-4.5%"]]},
  {"title":"Cost Breakdown Q1 2026","columns":["Category","Amount (₹ Cr)","vs Budget"],"rows":[["COGS",28.4,"+2%"],["Marketing",8.1,"-5%"],["Operations",12.7,"+8%"]]},
  {"title":"Headcount by Department","columns":["Department","FTEs","Open Roles"],"rows":[["Engineering",142,18],["Sales",89,12],["Operations",211,5]]}
]</textarea>
</div>

<div style="margin-bottom:12px">
  <button class="sec" onclick="connect()">🔌 Connect Stream</button>
  <button id="run" onclick="submit()" disabled>▶ Submit Batch</button>
</div>

<div id="pb-wrap"><div id="pb"></div></div>
<div id="stats">Not connected</div>
<div id="grid"></div>
<div id="log"></div>

<script>
let es=null,sid=null,cards={};

function w(cls,txt){
  const l=document.getElementById('log');
  // Append to last span of same class, else new span
  if(l.lastChild&&l.lastChild.className===cls&&cls==='tok'){
    l.lastChild.textContent+=txt;
  } else {
    const s=document.createElement('span');
    s.className=cls;s.textContent=txt;l.appendChild(s);
  }
  l.scrollTop=l.scrollHeight;
}

function connect(){
  if(es){w('inf','Already connected\\n');return;}
  sid=document.getElementById('sid').value.trim()||('sess-'+Math.random().toString(36).slice(2,10));
  document.getElementById('sid').value=sid;
  es=new EventSource('/stream/'+sid);
  w('inf','✓ Connected to /stream/'+sid+'\\n');
  document.getElementById('stats').textContent='Connected — waiting for batch...';
  document.getElementById('run').disabled=false;

  const h=ev=>e=>{
    let d;try{d=JSON.parse(e.data)}catch{return}
    const idx=d.table_index,p=d.batch_progress;
    // Progress bar
    if(p){
      const pct=Math.round((p.completed+p.failed)/p.total*100);
      document.getElementById('pb').style.width=pct+'%';
      document.getElementById('stats').textContent=
        `${p.batch_id} — ${p.completed+p.failed}/${p.total} done `+
        `(${p.running} running, ${p.failed} failed)`;
    }
    // Card update
    if(idx!==undefined&&cards[idx]){
      const c=cards[idx],s=c.querySelector('.s');
      if(ev==='node.started'){c.className='card run';s.textContent='⏳ running'}
      if(ev==='pipeline.completed'){c.className='card ok';s.textContent='✓ done'}
      if(ev==='pipeline.error'){c.className='card err';s.textContent='✗ failed'}
    }
    // Log
    if(ev==='node.token'){w('tok',d.payload.token)}
    else if(ev==='node.started'){w('inf','\\n▶ ['+(idx!==undefined?idx+':'+d.table_title:'')+'] '+d.node_id+'\\n')}
    else if(ev==='node.completed'){w('wrn','  ✓ '+d.node_id+' done\\n')}
    else if(ev==='pipeline.completed'){w('wrn','  🏁 table '+(idx!==undefined?idx:'')+' done\\n\\n')}
    else if(ev==='pipeline.error'){w('er','  ✗ '+(d.error||JSON.stringify(d.payload))+'\\n')}
  };

  ['node.started','node.token','node.completed','pipeline.completed','pipeline.error']
    .forEach(t=>es.addEventListener(t,h(t)));

  es.addEventListener('batch.completed',e=>{
    const d=JSON.parse(e.data),p=d.batch_progress;
    w('dn','\\n🏁 BATCH DONE — '+p.completed+'/'+p.total+' ok, '+p.failed+' failed\\n');
    document.getElementById('run').disabled=false;
    document.getElementById('run').textContent='▶ Submit Batch';
  });
}

async function submit(){
  if(!sid){connect();return;}
  let tables;
  try{tables=JSON.parse(document.getElementById('json').value)}
  catch(e){w('er','Bad JSON: '+e+'\\n');return;}

  document.getElementById('run').disabled=true;
  document.getElementById('run').textContent='⏳ Submitting…';
  document.getElementById('log').innerHTML='';
  document.getElementById('grid').innerHTML='';
  cards={};
  document.getElementById('pb').style.width='0%';

  const r=await fetch('/batch/analyze',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      session_id:sid,user_id:document.getElementById('uid').value,
      tables,document_context:document.getElementById('ctx').value,
      preset:document.getElementById('preset').value,
      concurrency:parseInt(document.getElementById('conc').value)
    })
  });
  if(!r.ok){w('er','Submit failed: '+await r.text()+'\\n');document.getElementById('run').disabled=false;return;}
  const b=await r.json();
  w('inf','✓ Batch '+b.batch_id+' — '+b.total+' tables, concurrency='+b.concurrency+'\\n\\n');

  const g=document.getElementById('grid');
  b.tables.forEach(t=>{
    const c=document.createElement('div');c.className='card';
    c.innerHTML='<div class="t">'+(t.index+1)+'. '+t.title+'</div><div class="s">⏳ pending</div>';
    g.appendChild(c);cards[t.index]=c;
  });
}
</script>
</body>
</html>"""
