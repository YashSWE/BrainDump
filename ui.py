import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from auth import current_user_id, resolve_token, get_user_id
from storage import (
    init_db,
    list_memories, delete_memory as db_delete,
    list_goals,
    list_events,
    list_financial_facts,
    list_skills,
    list_relationships,
    list_delegated_tasks,
    list_followups, get_followup, save_followup,
    get_profile,
    search_memories, vec_delete_memory as vec_delete,
)
from followup_engine import generate_followups
from datetime import datetime, timezone


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="BrainDump UI", lifespan=lifespan)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    token = request.headers.get("X-Token", "") or request.query_params.get("token", "")
    user_id = resolve_token(token)
    if user_id is None:
        return Response("Unauthorized — include X-Token header", status_code=401, media_type="text/plain")
    ctx_token = current_user_id.set(user_id)
    try:
        response = await call_next(request)
    finally:
        current_user_id.reset(ctx_token)
    return response


app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount MCP server at /mcp (works for both local and cloud)
from server import mcp
app.mount("/mcp", mcp.streamable_http_app())


@app.get("/")
def index():
    return FileResponse("static/index.html")


# ── Memories ──────────────────────────────────────────────────────────────────

@app.get("/api/memories")
def get_memories(category: Optional[str] = None, type: Optional[str] = None, limit: int = 500):
    uid = get_user_id()
    memories = list_memories(category=category, type=type, limit=limit, user_id=uid)
    return [m.model_dump(mode="json") for m in memories]


@app.get("/api/memories/search")
def search(q: str, n: int = 20):
    uid = get_user_id()
    return search_memories(q, n, user_id=uid)


@app.delete("/api/memories/{memory_id}")
def forget(memory_id: str):
    ok = db_delete(memory_id)
    vec_delete(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}


# ── Goals ─────────────────────────────────────────────────────────────────────

@app.get("/api/goals")
def get_goals(category: Optional[str] = None, status: Optional[str] = None):
    uid = get_user_id()
    return [g.model_dump(mode="json") for g in list_goals(category=category, status=status, user_id=uid)]


# ── Events ────────────────────────────────────────────────────────────────────

@app.get("/api/events")
def get_events():
    return [e.model_dump(mode="json") for e in list_events(user_id=get_user_id())]


# ── Financial ─────────────────────────────────────────────────────────────────

@app.get("/api/financial")
def get_financial(status: Optional[str] = None):
    uid = get_user_id()
    return [f.model_dump(mode="json") for f in list_financial_facts(status=status, user_id=uid)]


# ── Skills ────────────────────────────────────────────────────────────────────

@app.get("/api/skills")
def get_skills():
    return [s.model_dump(mode="json") for s in list_skills(user_id=get_user_id())]


# ── Relationships ─────────────────────────────────────────────────────────────

@app.get("/api/relationships")
def get_relationships():
    return [r.model_dump(mode="json") for r in list_relationships(user_id=get_user_id())]


# ── Delegated Tasks ───────────────────────────────────────────────────────────

@app.get("/api/tasks")
def get_tasks(status: Optional[str] = None):
    uid = get_user_id()
    return [t.model_dump(mode="json") for t in list_delegated_tasks(status=status, user_id=uid)]


# ── Follow-ups ────────────────────────────────────────────────────────────────

@app.get("/api/followups")
def get_followups(status: Optional[str] = "pending"):
    uid = get_user_id()
    generate_followups(user_id=uid)
    return [fu.model_dump(mode="json") for fu in list_followups(status=status, user_id=uid)]


@app.post("/api/followups/{followup_id}/dismiss")
def dismiss_followup(followup_id: str):
    fu = get_followup(followup_id)
    if not fu:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    fu.status = "dismissed"
    save_followup(fu)
    return {"ok": True}


@app.post("/api/followups/{followup_id}/answer")
def answer_followup_endpoint(followup_id: str, body: dict):
    fu = get_followup(followup_id)
    if not fu:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    fu.status = "answered"
    fu.answer = body.get("answer", "")
    fu.answered_at = datetime.now(timezone.utc)
    save_followup(fu)
    return {"ok": True}


# ── Context ──────────────────────────────────────────────────────────────────

@app.get("/api/context")
def get_context_text(purpose: Optional[str] = None):
    import server as srv
    return {"context": srv.get_context(purpose=purpose)}


# ── Profile & Stats ───────────────────────────────────────────────────────────

@app.get("/api/profile")
def profile():
    return get_profile(user_id=get_user_id())


@app.get("/api/stats")
def stats():
    uid = get_user_id()
    facts = list_memories(type="fact", user_id=uid)
    notes = list_memories(type="note", user_id=uid)
    goals = list_goals(status="active", user_id=uid)
    events_list = list_events(user_id=uid)
    financial = list_financial_facts(status="active", user_id=uid)
    skills_list = list_skills(user_id=uid)
    rels = list_relationships(user_id=uid)
    tasks = list_delegated_tasks(status="active", user_id=uid)
    followups_list = list_followups(status="pending", user_id=uid)

    cat_counts: dict[str, int] = {}
    for m in facts + notes:
        cat_counts[m.category] = cat_counts.get(m.category, 0) + 1

    return {
        "facts": len(facts),
        "notes": len(notes),
        "memories": len(facts) + len(notes),
        "goals": len(goals),
        "events": len(events_list),
        "financial": len(financial),
        "skills": len(skills_list),
        "relationships": len(rels),
        "tasks": len(tasks),
        "followups": len(followups_list),
        "memory_categories": [
            {"name": k, "count": v}
            for k, v in sorted(cat_counts.items(), key=lambda x: -x[1])
        ],
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7842))
    uvicorn.run("ui:app", host="0.0.0.0", port=port, reload=False)
