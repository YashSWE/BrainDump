import os
import time
import uuid
from typing import Optional, Any

from google import genai
from google.genai import types
from fastapi import APIRouter
from pydantic import BaseModel

from auth import get_user_id
import server as srv

router = APIRouter()

_sessions: dict[str, dict[str, Any]] = {}
SESSION_TTL = 1800  # 30 minutes


SYSTEM_PROMPT = (
    "You are BrainDump, the user's personal AI companion with perfect persistent memory. "
    "You have direct access to their life data through tools — goals, finances, events, relationships, skills, and more.\n\n"
    "HOW TO BEHAVE:\n"
    "- Be warm and conversational. You're their trusted companion, not a data entry bot.\n"
    "- At the start of every NEW session, call get_context() first, then get_pending_followups().\n"
    "- When the user mentions money → add_financial_fact(). Goals → track_goal(). Events → add_event(). "
    "People → add_relationship(). Skills → add_skill(). Tracking requests → offload_task(). "
    "Feelings/reflections → add_note(). Facts → store_fact().\n"
    "- After storing something, acknowledge it naturally — don't announce 'I called a tool'.\n"
    "- Show that you remember things from context. Reference their goals, finances, relationships by name.\n"
    "- Always use source='braindump-chat' when storing data.\n"
    "- If there are pending follow-ups, weave the most relevant one into conversation naturally."
)


TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_context",
        description="Get a structured summary of the user — profile, goals, finances, events, skills, relationships, tasks, follow-ups. Call at the start of every new conversation.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "purpose": types.Schema(type=types.Type.STRING, description="What you need context for, e.g. 'financial advice'. Omit for full context.")
            }
        )
    ),
    types.FunctionDeclaration(
        name="recall",
        description="Semantic search across all stored memories.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(type=types.Type.STRING),
                "n_results": types.Schema(type=types.Type.INTEGER, description="Max results. Default 5.")
            },
            required=["query"]
        )
    ),
    types.FunctionDeclaration(
        name="store_fact",
        description="Store a permanent objective fact about the user — preferences, background, attributes.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "fact": types.Schema(type=types.Type.STRING),
                "category": types.Schema(type=types.Type.STRING, description="career, financial, health, creative, learning, relationships, lifestyle, wellbeing, or general"),
                "tags": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "importance": types.Schema(type=types.Type.INTEGER, description="1-10"),
                "source": types.Schema(type=types.Type.STRING)
            },
            required=["fact"]
        )
    ),
    types.FunctionDeclaration(
        name="add_note",
        description="Store a thought, reflection, mood entry, or feeling.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "content": types.Schema(type=types.Type.STRING),
                "category": types.Schema(type=types.Type.STRING),
                "mood": types.Schema(type=types.Type.STRING, description="happy, neutral, stressed, anxious, excited, or sad"),
                "emotion_tags": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "tags": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "source": types.Schema(type=types.Type.STRING)
            },
            required=["content"]
        )
    ),
    types.FunctionDeclaration(
        name="track_goal",
        description="Create a new goal to track.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "title": types.Schema(type=types.Type.STRING),
                "category": types.Schema(type=types.Type.STRING),
                "deadline": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD"),
                "notes": types.Schema(type=types.Type.STRING)
            },
            required=["title", "category"]
        )
    ),
    types.FunctionDeclaration(
        name="update_goal",
        description="Update progress or status on an existing goal.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "goal_id": types.Schema(type=types.Type.STRING),
                "progress": types.Schema(type=types.Type.INTEGER),
                "status": types.Schema(type=types.Type.STRING, description="active, paused, completed, or abandoned"),
                "notes": types.Schema(type=types.Type.STRING)
            },
            required=["goal_id"]
        )
    ),
    types.FunctionDeclaration(
        name="list_goals_tool",
        description="List goals, optionally filtered by category or status.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "category": types.Schema(type=types.Type.STRING),
                "status": types.Schema(type=types.Type.STRING)
            }
        )
    ),
    types.FunctionDeclaration(
        name="add_event",
        description="Log an upcoming or past event.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "title": types.Schema(type=types.Type.STRING),
                "event_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD"),
                "category": types.Schema(type=types.Type.STRING),
                "people": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "notes": types.Schema(type=types.Type.STRING)
            },
            required=["title", "event_date", "category"]
        )
    ),
    types.FunctionDeclaration(
        name="update_event",
        description="Record the outcome of a past event.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "event_id": types.Schema(type=types.Type.STRING),
                "outcome": types.Schema(type=types.Type.STRING)
            },
            required=["event_id", "outcome"]
        )
    ),
    types.FunctionDeclaration(
        name="add_financial_fact",
        description="Log a financial fact — investment, expense, income, debt, or saving.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "type": types.Schema(type=types.Type.STRING, description="investment, expense, income, debt, or saving"),
                "asset": types.Schema(type=types.Type.STRING),
                "amount": types.Schema(type=types.Type.NUMBER),
                "date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD"),
                "currency": types.Schema(type=types.Type.STRING),
                "notes": types.Schema(type=types.Type.STRING)
            },
            required=["type", "asset", "amount", "date"]
        )
    ),
    types.FunctionDeclaration(
        name="update_financial_fact",
        description="Update the status of a financial fact.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "fact_id": types.Schema(type=types.Type.STRING),
                "status": types.Schema(type=types.Type.STRING, description="active, sold, settled, or pending"),
                "notes": types.Schema(type=types.Type.STRING)
            },
            required=["fact_id", "status"]
        )
    ),
    types.FunctionDeclaration(
        name="add_skill",
        description="Log or update a skill.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(type=types.Type.STRING),
                "domain": types.Schema(type=types.Type.STRING),
                "proficiency": types.Schema(type=types.Type.STRING, description="beginner, intermediate, advanced, or expert"),
                "actively_using": types.Schema(type=types.Type.BOOLEAN),
                "notes": types.Schema(type=types.Type.STRING)
            },
            required=["name", "domain"]
        )
    ),
    types.FunctionDeclaration(
        name="add_relationship",
        description="Log a person or organisation.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(type=types.Type.STRING),
                "relationship_type": types.Schema(type=types.Type.STRING),
                "notes": types.Schema(type=types.Type.STRING)
            },
            required=["name", "relationship_type"]
        )
    ),
    types.FunctionDeclaration(
        name="get_user_profile",
        description="Get the user's profile — name, age, role, location.",
        parameters=types.Schema(type=types.Type.OBJECT, properties={})
    ),
    types.FunctionDeclaration(
        name="update_user_profile",
        description="Update the user's profile fields.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "updates": types.Schema(type=types.Type.OBJECT, description="Key-value pairs, e.g. {\"name\": \"Yash\", \"age\": 22}")
            },
            required=["updates"]
        )
    ),
    types.FunctionDeclaration(
        name="offload_task",
        description="Delegate a tracking task or reminder to BrainDump for cross-session memory.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "description": types.Schema(type=types.Type.STRING),
                "category": types.Schema(type=types.Type.STRING),
                "check_in_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD"),
                "notes": types.Schema(type=types.Type.STRING),
                "source": types.Schema(type=types.Type.STRING)
            },
            required=["description", "category"]
        )
    ),
    types.FunctionDeclaration(
        name="update_delegated_task",
        description="Mark a delegated task complete, cancelled, or push its check-in date.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "task_id": types.Schema(type=types.Type.STRING),
                "status": types.Schema(type=types.Type.STRING),
                "outcome": types.Schema(type=types.Type.STRING),
                "check_in_date": types.Schema(type=types.Type.STRING)
            },
            required=["task_id", "status"]
        )
    ),
    types.FunctionDeclaration(
        name="list_delegated_tasks_tool",
        description="List delegated tasks.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={"status": types.Schema(type=types.Type.STRING)}
        )
    ),
    types.FunctionDeclaration(
        name="get_pending_followups",
        description="Get all pending follow-up questions. Call at the start of each session.",
        parameters=types.Schema(type=types.Type.OBJECT, properties={})
    ),
    types.FunctionDeclaration(
        name="answer_followup",
        description="Record the user's answer to a follow-up question.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "followup_id": types.Schema(type=types.Type.STRING),
                "answer": types.Schema(type=types.Type.STRING)
            },
            required=["followup_id", "answer"]
        )
    ),
    types.FunctionDeclaration(
        name="forget",
        description="Delete a stored fact or note permanently.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={"entry_id": types.Schema(type=types.Type.STRING)},
            required=["entry_id"]
        )
    )
]

TOOL_MAP = {
    "get_context": srv.get_context,
    "recall": srv.recall,
    "store_fact": srv.store_fact,
    "add_note": srv.add_note,
    "track_goal": srv.track_goal,
    "update_goal": srv.update_goal,
    "list_goals_tool": srv.list_goals_tool,
    "add_event": srv.add_event,
    "update_event": srv.update_event,
    "add_financial_fact": srv.add_financial_fact,
    "update_financial_fact": srv.update_financial_fact,
    "add_skill": srv.add_skill,
    "add_relationship": srv.add_relationship,
    "get_user_profile": srv.get_user_profile,
    "update_user_profile": srv.update_user_profile,
    "offload_task": srv.offload_task,
    "update_delegated_task": srv.update_delegated_task,
    "list_delegated_tasks_tool": srv.list_delegated_tasks_tool,
    "get_pending_followups": srv.get_pending_followups,
    "answer_followup": srv.answer_followup,
    "forget": srv.forget,
}


def _normalize(val: Any) -> Any:
    """Recursively convert proto map/list types to plain Python."""
    if hasattr(val, "items"):
        return {k: _normalize(v) for k, v in val.items()}
    if hasattr(val, "__iter__") and not isinstance(val, (str, bytes)):
        return [_normalize(v) for v in val]
    return val


def execute_tool(name: str, args: dict) -> str:
    fn = TOOL_MAP.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    try:
        return fn(**_normalize(args))
    except Exception as e:
        return f"Tool error ({name}): {e}"


def _cleanup_sessions() -> None:
    cutoff = time.time() - SESSION_TTL
    expired = [k for k, v in _sessions.items() if v["last_active"] < cutoff]
    for k in expired:
        del _sessions[k]


def _get_or_create_session(session_id: Optional[str], user_id: str) -> tuple[str, Any]:
    _cleanup_sessions()
    now = time.time()

    if session_id and session_id in _sessions:
        entry = _sessions[session_id]
        if entry["user_id"] == user_id and now - entry["last_active"] < SESSION_TTL:
            entry["last_active"] = now
            return session_id, entry["chat"]

    api_key = os.environ.get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=api_key)
    chat = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(function_declarations=TOOL_DECLARATIONS)],
        ),
    )
    new_id = str(uuid.uuid4())
    # Store client alongside chat to prevent premature GC of the httpx client
    _sessions[new_id] = {"user_id": user_id, "client": client, "chat": chat, "last_active": now}
    return new_id, chat


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    tools_called: list[str] = []
    session_id: str


@router.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    if not os.environ.get("GEMINI_API_KEY"):
        return ChatResponse(
            reply="No GEMINI_API_KEY set. Add it to your .env file to enable the chat.",
            tools_called=[],
            session_id="",
        )

    user_id = get_user_id()
    session_id, chat_session = _get_or_create_session(req.session_id, user_id)

    tools_called: list[str] = []
    response = chat_session.send_message(req.message)

    for _ in range(12):
        try:
            parts = response.candidates[0].content.parts or []
        except (AttributeError, IndexError, TypeError):
            break

        fn_calls = [p.function_call for p in parts if p.function_call is not None]
        if not fn_calls:
            break

        fn_responses = []
        for fn_call in fn_calls:
            result = execute_tool(fn_call.name, dict(fn_call.args))
            tools_called.append(fn_call.name)
            fn_responses.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fn_call.name,
                        response={"result": result},
                    )
                )
            )

        response = chat_session.send_message(fn_responses)

    seen: set[str] = set()
    unique_tools = [t for t in tools_called if not (t in seen or seen.add(t))]  # type: ignore[func-returns-value]

    try:
        reply_text = response.text or ""
    except (AttributeError, ValueError):
        reply_text = "Something went wrong generating a response. Please try again."

    return ChatResponse(reply=reply_text, tools_called=unique_tools, session_id=session_id)


@router.delete("/api/chat/session/{session_id}")
async def clear_session(session_id: str):
    _sessions.pop(session_id, None)
    return {"ok": True}
