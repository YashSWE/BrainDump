import json
from datetime import datetime, timezone
from typing import Optional

from mcp.server.fastmcp import FastMCP

from auth import get_user_id
from models import Memory, Goal, Event, FinancialFact, Skill, Relationship, DelegatedTask, Followup
from storage import (
    init_db,
    save_memory, delete_memory as db_delete_memory, list_memories, get_memory,
    save_goal, get_goal, list_goals,
    save_event, get_event, list_events,
    save_financial_fact, get_financial_fact, list_financial_facts,
    save_skill, list_skills,
    save_relationship, list_relationships,
    save_delegated_task, get_delegated_task, list_delegated_tasks,
    save_followup, get_followup, list_followups,
    get_profile, update_profile,
    vec_add_memory, search_memories, vec_delete_memory,
)

mcp = FastMCP(
    "BrainDump",
    instructions=(
        "You are connected to BrainDump, the user's persistent User Information Management System (UIMS). "
        "RULES — follow these strictly:\n"
        "1. Call get_context() at the start of EVERY new conversation before saying anything else.\n"
        "2. ALWAYS use the correct typed tool — in strict priority order:\n"
        "   - Money, investments, savings, debt, income → add_financial_fact()\n"
        "   - Goals, targets, aspirations → track_goal()\n"
        "   - Events, meetings, trips, milestones → add_event()\n"
        "   - Skills, technologies, expertise → add_skill()\n"
        "   - People, relationships, contacts → add_relationship()\n"
        "   - Tracking requests, reminders, follow-up intentions → offload_task()\n"
        "   - Permanent objective facts about the user (preferences, background, attributes) → store_fact()\n"
        "   - Thoughts, feelings, reflections, mood entries → add_note()\n"
        "3. store_fact() and add_note() are the ONLY fallbacks. There is no 'remember' tool.\n"
        "4. Call get_pending_followups() at the start of each session after get_context().\n"
        "5. When the user updates the status of something (sold investment, completed goal, event outcome) — "
        "call the matching update tool: update_financial_fact(), update_goal(), update_event().\n"
        "6. Populate ALL fields you can infer — don't leave structured data in notes when it belongs in a field."
    ),
)


# ── Facts & Notes ─────────────────────────────────────────────────────────────

@mcp.tool()
def store_fact(
    fact: str,
    category: str = "general",
    tags: list[str] = [],
    importance: int = 6,
    source: str = "claude-desktop",
) -> str:
    """
    Store a permanent, objective fact about the user that doesn't fit a typed tool.
    Use for things like: language preferences, dietary habits, location, personal background,
    communication style, values, or any persistent attribute about who the user is.

    Do NOT use for: money (→ add_financial_fact), goals (→ track_goal), events (→ add_event),
    skills (→ add_skill), people (→ add_relationship), tracking requests (→ offload_task).

    Args:
        fact: The objective fact. E.g. "Prefers Python over JavaScript", "Vegetarian", "Speaks Hindi and English".
        category: One of: career, financial, health, creative, learning, relationships, lifestyle, wellbeing, general.
        tags: Optional keyword tags.
        importance: 1 (low) to 10 (critical). Default 6 — facts are generally important.
        source: Which AI assistant is storing this.
    """
    uid = get_user_id()
    memory = Memory(
        content=fact, type="fact", category=category,
        tags=tags, importance=importance, source=source, user_id=uid,
    )
    save_memory(memory)
    vec_add_memory(memory.id, fact, {"type": "fact", "category": category, "importance": importance, "user_id": uid})
    return f"Fact stored [{memory.id[:8]}]: {fact[:100]}"


@mcp.tool()
def add_note(
    content: str,
    category: str = "general",
    mood: Optional[str] = None,
    emotion_tags: list[str] = [],
    tags: list[str] = [],
    source: str = "claude-desktop",
) -> str:
    """
    Store an unstructured thought, reflection, mood entry, or observation.
    Use for things like: how the user is feeling, a passing thought they want to record,
    a conversation snippet, or anything subjective and moment-in-time.

    Do NOT use for objective facts (→ store_fact) or structured data (typed tools).

    Args:
        content: The note content. E.g. "Feeling burnt out after the sprint", "Had a great call with Rahul today".
        category: One of: career, financial, health, creative, learning, relationships, lifestyle, wellbeing, general.
        mood: Detected mood. One of: happy, neutral, stressed, anxious, excited, sad.
        emotion_tags: Specific emotions, e.g. ["proud", "relieved", "overwhelmed"].
        tags: Optional keyword tags.
        source: Which AI assistant is storing this.
    """
    uid = get_user_id()
    memory = Memory(
        content=content, type="note", category=category,
        mood=mood, emotion_tags=emotion_tags,
        tags=tags, importance=4, source=source, user_id=uid,
    )
    save_memory(memory)
    vec_add_memory(memory.id, content, {"type": "note", "category": category, "mood": mood or "", "user_id": uid})
    return f"Note added [{memory.id[:8]}]: {content[:100]}"


@mcp.tool()
def get_context(purpose: Optional[str] = None, categories: Optional[list[str]] = None) -> str:
    """
    Returns a structured summary of the user — their profile, goals, recent events, finances, skills, and relationships.
    Call this at the start of every conversation to ground yourself in who the user is.

    Args:
        purpose: What you need the context for, e.g. "financial advice", "career coaching", "health check-in".
                 This filters which sections are included. Without it, all sections are summarised briefly.
        categories: Explicit list of categories to include, e.g. ["financial", "career"].
                    Overrides purpose-based filtering if provided.
    """
    uid = get_user_id()
    profile = get_profile(user_id=uid)
    goals = list_goals(user_id=uid)
    events = list_events(user_id=uid)
    facts = list_financial_facts(user_id=uid)
    skills = list_skills(user_id=uid)
    rels = list_relationships(user_id=uid)
    tasks = list_delegated_tasks(status="active", user_id=uid)
    followups = list_followups(status="pending", user_id=uid)

    show_all = not purpose and not categories
    p = (purpose or "").lower()

    def show(section: str) -> bool:
        if show_all:
            return True
        if categories:
            return section in categories
        financial_keywords = ["finance", "financial", "invest", "money", "budget", "saving", "wealth"]
        career_keywords = ["career", "job", "work", "skill", "professional"]
        health_keywords = ["health", "fitness", "wellness", "mental"]
        if section == "financial" and any(k in p for k in financial_keywords):
            return True
        if section in ("career", "skills") and any(k in p for k in career_keywords):
            return True
        if section in ("health", "wellbeing") and any(k in p for k in health_keywords):
            return True
        if section in ("goals", "tasks", "followups"):
            return True
        return False

    lines: list[str] = []

    if profile:
        name = profile.get("name", "User")
        age = profile.get("age", "")
        role = profile.get("role", "")
        location = profile.get("location", "")
        header = f"User: {name}"
        if age:
            header += f", {age}"
        if role:
            header += f", {role}"
        if location:
            header += f" ({location})"
        lines.append(header)
        lines.append("")

    if show("goals") and goals:
        active = [g for g in goals if g.status == "active"]
        if active:
            lines.append("GOALS")
            for g in active[:6]:
                deadline = f" · deadline {g.deadline}" if g.deadline else ""
                lines.append(f"  [{g.category}] {g.title} — {g.progress}% complete{deadline}")
            lines.append("")

    if show("financial") and facts:
        lines.append("FINANCIAL SNAPSHOT")
        for f in facts[:8]:
            status_badge = f" [{f.status}]" if f.status != "active" else ""
            lines.append(f"  {f.type.capitalize()}: {f.currency} {f.amount:,.0f} in {f.asset}{status_badge} ({f.transaction_date})")
        lines.append("")

    if show("events") and events:
        now = datetime.now(timezone.utc).date().isoformat()
        upcoming = [e for e in events if e.event_date >= now]
        if upcoming:
            lines.append("UPCOMING EVENTS")
            for e in upcoming[:5]:
                people = f" · {', '.join(e.people_involved)}" if e.people_involved else ""
                lines.append(f"  {e.event_date}: {e.title}{people}")
            lines.append("")

    if show("skills") and skills:
        active_skills = [s for s in skills if s.actively_using]
        if active_skills:
            lines.append("SKILLS (active)")
            by_domain: dict[str, list] = {}
            for s in active_skills:
                by_domain.setdefault(s.domain, []).append(s)
            for domain, domain_skills in list(by_domain.items())[:4]:
                names = ", ".join(f"{s.name} ({s.proficiency})" for s in domain_skills[:4])
                lines.append(f"  [{domain}] {names}")
            lines.append("")

    if show("relationships") and rels:
        lines.append("PEOPLE")
        for r in rels[:6]:
            notes = f" — {r.notes[:60]}" if r.notes else ""
            lines.append(f"  {r.name} ({r.relationship_type}){notes}")
        lines.append("")

    if tasks:
        lines.append("DELEGATED TASKS (active)")
        for t in tasks[:5]:
            due = f" · check-in {t.check_in_date}" if t.check_in_date else ""
            lines.append(f"  [{t.category}] {t.description[:80]}{due}")
        lines.append("")

    if followups:
        lines.append(f"PENDING FOLLOW-UPS ({len(followups)})")
        for fu in followups[:3]:
            lines.append(f"  · {fu.question}")
        lines.append("")

    return "\n".join(lines) if lines else "No information stored yet. Ask the user to tell you about themselves."


@mcp.tool()
def recall(query: str, n_results: int = 5) -> str:
    """
    Semantic search across stored memories.

    Args:
        query: Natural language description of what you're looking for.
        n_results: Max results (default 5).
    """
    uid = get_user_id()
    results = search_memories(query, n_results, user_id=uid)
    if not results:
        return "No relevant memories found."
    lines = [
        f"[{r['id'][:8]}] (relevance: {r['relevance']:.2f}) [{r['metadata'].get('category', '?')}] {r['content']}"
        for r in results
    ]
    return "\n\n".join(lines)


@mcp.tool()
def forget(entry_id: str) -> str:
    """
    Delete a stored fact or note permanently.

    Args:
        entry_id: Full or partial (first 8 chars) ID from store_fact or add_note.
    """
    uid = get_user_id()
    if len(entry_id) < 36:
        all_entries = list_memories(limit=500, user_id=uid)
        matches = [m for m in all_entries if m.id.startswith(entry_id)]
        if not matches:
            return f"No entry found with ID starting with '{entry_id}'."
        if len(matches) > 1:
            return f"Ambiguous ID '{entry_id}' matches {len(matches)} entries."
        entry_id = matches[0].id
    db_delete_memory(entry_id)
    vec_delete_memory(entry_id)
    return f"Deleted entry {entry_id[:8]}."


# ── Goals ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def track_goal(
    title: str,
    category: str,
    deadline: Optional[str] = None,
    milestones: list[dict] = [],
    notes: Optional[str] = None,
) -> str:
    """
    Create a new goal to track.

    Args:
        title: What the user wants to achieve. E.g. "Run a consistent 5K".
        category: Life category — career, financial, health, creative, learning, relationships, lifestyle, wellbeing.
        deadline: Optional target date in YYYY-MM-DD format.
        milestones: Optional list of milestones, each {"label": str, "target_date": str, "done": bool}.
        notes: Any additional context.
    """
    goal = Goal(title=title, category=category, deadline=deadline, milestones=milestones, notes=notes, user_id=get_user_id())
    save_goal(goal)
    return f"Goal tracked [{goal.id[:8]}]: {title}"


@mcp.tool()
def update_goal(goal_id: str, progress: Optional[int] = None, status: Optional[str] = None, notes: Optional[str] = None) -> str:
    """
    Update progress or status on an existing goal.

    Args:
        goal_id: First 8+ characters of the goal ID.
        progress: Completion percentage 0–100.
        status: One of: active, paused, completed, abandoned.
        notes: Updated notes.
    """
    uid = get_user_id()
    goals = list_goals(user_id=uid)
    matches = [g for g in goals if g.id.startswith(goal_id)]
    if not matches:
        return f"No goal found with ID starting with '{goal_id}'."
    goal = matches[0]
    if progress is not None:
        goal.progress = progress
    if status:
        goal.status = status
    if notes:
        goal.notes = notes
    goal.updated_at = datetime.now(timezone.utc)
    save_goal(goal)
    return f"Goal updated [{goal.id[:8]}]: {goal.title} — {goal.progress}% [{goal.status}]"


@mcp.tool()
def list_goals_tool(category: Optional[str] = None, status: Optional[str] = "active") -> str:
    """
    List goals, optionally filtered.

    Args:
        category: Filter by life category.
        status: Filter by status (active, paused, completed, abandoned). Default "active".
    """
    goals = list_goals(category=category, status=status, user_id=get_user_id())
    if not goals:
        return "No goals found."
    lines = []
    for g in goals:
        deadline = f" · due {g.deadline}" if g.deadline else ""
        lines.append(f"[{g.id[:8]}] [{g.category}] {g.title} — {g.progress}%{deadline} [{g.status}]")
    return "\n".join(lines)


# ── Events ────────────────────────────────────────────────────────────────────

@mcp.tool()
def add_event(
    title: str,
    event_date: str,
    category: str,
    people: list[str] = [],
    notes: Optional[str] = None,
) -> str:
    """
    Log an upcoming or past event.

    Args:
        title: Event name. E.g. "Sister's wedding", "Syngenta performance review".
        event_date: Date in YYYY-MM-DD format.
        category: Life category.
        people: People involved, e.g. ["sister", "family"].
        notes: Any additional context.
    """
    event = Event(title=title, event_date=event_date, category=category, people_involved=people, notes=notes, user_id=get_user_id())
    save_event(event)
    return f"Event logged [{event.id[:8]}]: {title} on {event_date}"


@mcp.tool()
def update_event(event_id: str, outcome: str) -> str:
    """
    Record the outcome of a past event.

    Args:
        event_id: First 8+ characters of the event ID.
        outcome: What happened at the event.
    """
    uid = get_user_id()
    events = list_events(user_id=uid)
    matches = [e for e in events if e.id.startswith(event_id)]
    if not matches:
        return f"No event found with ID starting with '{event_id}'."
    event = matches[0]
    event.outcome = outcome
    save_event(event)
    return f"Event updated [{event.id[:8]}]: {event.title}"


# ── Financial ─────────────────────────────────────────────────────────────────

@mcp.tool()
def add_financial_fact(
    type: str,
    asset: str,
    amount: float,
    date: str,
    currency: str = "INR",
    notes: Optional[str] = None,
) -> str:
    """
    Log a financial fact — investment, expense, income, debt, or saving.

    Args:
        type: One of: investment, expense, income, debt, saving.
        asset: What it relates to. E.g. "gold", "mutual fund", "salary", "emergency fund".
        amount: Numeric amount.
        date: Transaction date in YYYY-MM-DD format.
        currency: Currency code. Default "INR".
        notes: Any additional context.
    """
    fact = FinancialFact(
        type=type, asset=asset, amount=amount,
        transaction_date=date, currency=currency, notes=notes, user_id=get_user_id(),
    )
    save_financial_fact(fact)
    return f"Financial fact logged [{fact.id[:8]}]: {type} {currency} {amount:,.0f} in {asset} on {date}"


@mcp.tool()
def update_financial_fact(fact_id: str, status: str, notes: Optional[str] = None) -> str:
    """
    Update the status of a financial fact.

    Args:
        fact_id: First 8+ characters of the fact ID.
        status: One of: active, sold, settled, pending.
        notes: Updated notes.
    """
    uid = get_user_id()
    facts = list_financial_facts(user_id=uid)
    matches = [f for f in facts if f.id.startswith(fact_id)]
    if not matches:
        return f"No financial fact found with ID starting with '{fact_id}'."
    fact = matches[0]
    fact.status = status
    if notes:
        fact.notes = notes
    save_financial_fact(fact)
    return f"Financial fact updated [{fact.id[:8]}]: {fact.asset} → {status}"


# ── Skills & Relationships ────────────────────────────────────────────────────

@mcp.tool()
def add_skill(
    name: str,
    domain: str,
    proficiency: str = "intermediate",
    actively_using: bool = True,
    notes: Optional[str] = None,
) -> str:
    """
    Log or update a skill.

    Args:
        name: Skill name. E.g. "PyTorch", "System Design", "SQL".
        domain: Broad domain. E.g. "ML", "Software Engineering", "Data".
        proficiency: beginner, intermediate, advanced, or expert.
        actively_using: Whether the user is currently using this skill.
        notes: Any context.
    """
    skill = Skill(name=name, domain=domain, proficiency=proficiency, actively_using=actively_using, notes=notes, user_id=get_user_id())
    save_skill(skill)
    return f"Skill logged [{skill.id[:8]}]: {name} ({domain}) — {proficiency}"


@mcp.tool()
def add_relationship(
    name: str,
    relationship_type: str,
    notes: Optional[str] = None,
) -> str:
    """
    Log a person or organisation.

    Args:
        name: Person's or organisation's name.
        relationship_type: E.g. "friend", "manager", "sister", "mentor", "company".
        notes: Key facts about this person.
    """
    rel = Relationship(name=name, relationship_type=relationship_type, notes=notes, user_id=get_user_id())
    save_relationship(rel)
    return f"Relationship logged [{rel.id[:8]}]: {name} ({relationship_type})"


# ── Profile ───────────────────────────────────────────────────────────────────

@mcp.tool()
def get_user_profile() -> str:
    """
    Retrieve the user's profile — name, age, role, location, and other persisted facts.
    """
    profile = get_profile(user_id=get_user_id())
    if not profile:
        return "No profile set yet. Use update_user_profile to add information."
    return json.dumps(profile, indent=2)


@mcp.tool()
def update_user_profile(updates: dict) -> str:
    """
    Update fields in the user's profile.

    Args:
        updates: Key-value pairs to upsert. E.g. {"name": "Yash", "age": 22, "role": "AI Engineer", "location": "Pune, India"}.
    """
    update_profile(updates, user_id=get_user_id())
    return f"Profile updated: {list(updates.keys())}"


# ── Delegated Tasks ───────────────────────────────────────────────────────────

@mcp.tool()
def offload_task(
    description: str,
    category: str,
    check_in_date: Optional[str] = None,
    notes: Optional[str] = None,
    source: str = "claude-desktop",
) -> str:
    """
    Delegate a task or intention to BrainDump for cross-session tracking.
    Use this when the user says things like "remind me to check on X", "track whether I do Y", "follow up on Z in 3 months".

    Args:
        description: What to track. E.g. "Track whether I post to YouTube every week".
        category: Life category.
        check_in_date: When to surface this back to the user, in YYYY-MM-DD format.
        notes: Any additional context.
        source: Which AI assistant is delegating the task.
    """
    task = DelegatedTask(
        description=description, category=category,
        check_in_date=check_in_date, notes=notes, source=source, user_id=get_user_id(),
    )
    save_delegated_task(task)
    checkin = f" · check-in on {check_in_date}" if check_in_date else ""
    return f"Task offloaded [{task.id[:8]}]: {description[:80]}{checkin}"


@mcp.tool()
def update_delegated_task(task_id: str, status: str, outcome: Optional[str] = None, check_in_date: Optional[str] = None) -> str:
    """
    Mark a delegated task complete, cancelled, or push its check-in date.

    Args:
        task_id: First 8+ characters of the task ID.
        status: One of: active, completed, cancelled.
        outcome: What happened — fill when resolving the task.
        check_in_date: New check-in date in YYYY-MM-DD format (to push it forward).
    """
    uid = get_user_id()
    tasks = list_delegated_tasks(user_id=uid)
    matches = [t for t in tasks if t.id.startswith(task_id)]
    if not matches:
        return f"No delegated task found with ID starting with '{task_id}'."
    task = matches[0]
    task.status = status
    if outcome:
        task.outcome = outcome
    if check_in_date:
        task.check_in_date = check_in_date
    task.updated_at = datetime.now(timezone.utc)
    save_delegated_task(task)
    return f"Task updated [{task.id[:8]}]: {task.description[:60]} → {status}"


@mcp.tool()
def list_delegated_tasks_tool(status: Optional[str] = "active") -> str:
    """
    List delegated tasks.

    Args:
        status: Filter by status (active, completed, cancelled). Default "active".
    """
    tasks = list_delegated_tasks(status=status, user_id=get_user_id())
    if not tasks:
        return f"No delegated tasks with status '{status}'."
    lines = []
    for t in tasks:
        checkin = f" · check-in {t.check_in_date}" if t.check_in_date else ""
        lines.append(f"[{t.id[:8]}] [{t.category}] {t.description[:80]}{checkin} [{t.status}]")
    return "\n".join(lines)


# ── Follow-ups ────────────────────────────────────────────────────────────────

@mcp.tool()
def get_pending_followups() -> str:
    """
    Returns all pending follow-up questions — from stale events, financials, goals, and delegated tasks.
    Call this periodically and weave the questions naturally into conversation.
    """
    from followup_engine import generate_followups
    uid = get_user_id()
    generate_followups(user_id=uid)

    followups = list_followups(status="pending", user_id=uid)
    if not followups:
        return "No pending follow-ups."
    lines = [f"[{fu.id[:8]}] {fu.question}" for fu in followups]
    return "\n".join(lines)


@mcp.tool()
def answer_followup(followup_id: str, answer: str) -> str:
    """
    Record the user's answer to a follow-up question.

    Args:
        followup_id: First 8+ characters of the follow-up ID.
        answer: The user's answer.
    """
    uid = get_user_id()
    followups = list_followups(status=None, user_id=uid)
    matches = [fu for fu in followups if fu.id.startswith(followup_id)]
    if not matches:
        return f"No follow-up found with ID starting with '{followup_id}'."
    fu = matches[0]
    fu.status = "answered"
    fu.answer = answer
    fu.answered_at = datetime.now(timezone.utc)
    save_followup(fu)
    return f"Follow-up answered [{fu.id[:8]}]."


def main():
    init_db()
    mcp.run()


if __name__ == "__main__":
    main()
