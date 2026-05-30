import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras

from models import Memory, Goal, Event, FinancialFact, Skill, Relationship, DelegatedTask, Followup

DATABASE_URL = os.environ.get("DATABASE_URL", "")


@contextmanager
def _db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Verify connectivity — tables are created by schema.sql in Supabase."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")


def _j(val) -> str:
    return json.dumps(val)


def _l(val) -> list:
    if isinstance(val, list):
        return val
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


# ── Memory ────────────────────────────────────────────────────────────────────

def _row_to_memory(row) -> Memory:
    return Memory(
        id=row["id"],
        user_id=row["user_id"] or "default",
        content=row["content"],
        type=row["type"] or "fact",
        tags=_l(row["tags"]),
        category=row["category"],
        mood=row["mood"],
        emotion_tags=_l(row["emotion_tags"]),
        importance=row["importance"],
        source=row["source"] or "unknown",
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def save_memory(memory: Memory):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO memories
                   (id, user_id, content, type, tags, category, mood, emotion_tags, importance, source, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                       content=EXCLUDED.content, type=EXCLUDED.type, tags=EXCLUDED.tags,
                       category=EXCLUDED.category, mood=EXCLUDED.mood,
                       emotion_tags=EXCLUDED.emotion_tags, importance=EXCLUDED.importance,
                       source=EXCLUDED.source""",
                (
                    memory.id, memory.user_id, memory.content, memory.type,
                    _j(memory.tags), memory.category, memory.mood,
                    _j(memory.emotion_tags), memory.importance, memory.source,
                    memory.created_at.isoformat(),
                ),
            )


def get_memory(memory_id: str) -> Optional[Memory]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM memories WHERE id = %s", (memory_id,))
            row = cur.fetchone()
    return _row_to_memory(row) if row else None


def delete_memory(memory_id: str) -> bool:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM memories WHERE id = %s", (memory_id,))
            return cur.rowcount > 0


def list_memories(
    category: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 500,
    user_id: Optional[str] = None,
) -> list[Memory]:
    with _db() as conn:
        with conn.cursor() as cur:
            q = "SELECT * FROM memories WHERE 1=1"
            params: list = []
            if user_id:
                q += " AND user_id = %s"; params.append(user_id)
            if category:
                q += " AND category = %s"; params.append(category)
            if type:
                q += " AND type = %s"; params.append(type)
            q += " ORDER BY importance DESC, created_at DESC LIMIT %s"
            params.append(limit)
            cur.execute(q, params)
            return [_row_to_memory(r) for r in cur.fetchall()]


# ── Goals ─────────────────────────────────────────────────────────────────────

def _row_to_goal(row) -> Goal:
    return Goal(
        id=row["id"], user_id=row["user_id"], title=row["title"],
        category=row["category"], progress=row["progress"],
        milestones=_l(row["milestones"]),
        deadline=row["deadline"], status=row["status"], notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def save_goal(goal: Goal):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO goals
                   (id, user_id, title, category, progress, milestones, deadline, status, notes, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                       title=EXCLUDED.title, category=EXCLUDED.category, progress=EXCLUDED.progress,
                       milestones=EXCLUDED.milestones, deadline=EXCLUDED.deadline, status=EXCLUDED.status,
                       notes=EXCLUDED.notes, updated_at=EXCLUDED.updated_at""",
                (
                    goal.id, goal.user_id, goal.title, goal.category,
                    goal.progress, _j(goal.milestones), goal.deadline,
                    goal.status, goal.notes,
                    goal.created_at.isoformat(), goal.updated_at.isoformat(),
                ),
            )


def get_goal(goal_id: str) -> Optional[Goal]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM goals WHERE id = %s", (goal_id,))
            row = cur.fetchone()
    return _row_to_goal(row) if row else None


def list_goals(
    category: Optional[str] = None,
    status: Optional[str] = None,
    user_id: Optional[str] = None,
) -> list[Goal]:
    with _db() as conn:
        with conn.cursor() as cur:
            q = "SELECT * FROM goals WHERE 1=1"
            params: list = []
            if user_id:
                q += " AND user_id = %s"; params.append(user_id)
            if category:
                q += " AND category = %s"; params.append(category)
            if status:
                q += " AND status = %s"; params.append(status)
            q += " ORDER BY updated_at DESC"
            cur.execute(q, params)
            return [_row_to_goal(r) for r in cur.fetchall()]


# ── Events ────────────────────────────────────────────────────────────────────

def _row_to_event(row) -> Event:
    return Event(
        id=row["id"], user_id=row["user_id"], title=row["title"],
        category=row["category"], event_date=row["event_date"],
        people_involved=_l(row["people_involved"]),
        outcome=row["outcome"], follow_up_sent=bool(row["follow_up_sent"]),
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def save_event(event: Event):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO events
                   (id, user_id, title, category, event_date, people_involved, outcome, follow_up_sent, notes, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                       title=EXCLUDED.title, category=EXCLUDED.category, event_date=EXCLUDED.event_date,
                       people_involved=EXCLUDED.people_involved, outcome=EXCLUDED.outcome,
                       follow_up_sent=EXCLUDED.follow_up_sent, notes=EXCLUDED.notes""",
                (
                    event.id, event.user_id, event.title, event.category,
                    event.event_date, _j(event.people_involved),
                    event.outcome, int(event.follow_up_sent), event.notes,
                    event.created_at.isoformat(),
                ),
            )


def get_event(event_id: str) -> Optional[Event]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM events WHERE id = %s", (event_id,))
            row = cur.fetchone()
    return _row_to_event(row) if row else None


def list_events(user_id: Optional[str] = None) -> list[Event]:
    with _db() as conn:
        with conn.cursor() as cur:
            q = "SELECT * FROM events WHERE 1=1"
            params: list = []
            if user_id:
                q += " AND user_id = %s"; params.append(user_id)
            q += " ORDER BY event_date DESC"
            cur.execute(q, params)
            return [_row_to_event(r) for r in cur.fetchall()]


# ── Financial Facts ───────────────────────────────────────────────────────────

def _row_to_fact(row) -> FinancialFact:
    return FinancialFact(
        id=row["id"], user_id=row["user_id"], type=row["type"],
        asset=row["asset"], amount=row["amount"], currency=row["currency"],
        transaction_date=row["transaction_date"], status=row["status"],
        notes=row["notes"], follow_up_sent=bool(row["follow_up_sent"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def save_financial_fact(fact: FinancialFact):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO financial_facts
                   (id, user_id, type, asset, amount, currency, transaction_date, status, notes, follow_up_sent, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                       type=EXCLUDED.type, asset=EXCLUDED.asset, amount=EXCLUDED.amount,
                       currency=EXCLUDED.currency, transaction_date=EXCLUDED.transaction_date,
                       status=EXCLUDED.status, notes=EXCLUDED.notes,
                       follow_up_sent=EXCLUDED.follow_up_sent""",
                (
                    fact.id, fact.user_id, fact.type, fact.asset, fact.amount,
                    fact.currency, fact.transaction_date, fact.status, fact.notes,
                    int(fact.follow_up_sent), fact.created_at.isoformat(),
                ),
            )


def get_financial_fact(fact_id: str) -> Optional[FinancialFact]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM financial_facts WHERE id = %s", (fact_id,))
            row = cur.fetchone()
    return _row_to_fact(row) if row else None


def list_financial_facts(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
) -> list[FinancialFact]:
    with _db() as conn:
        with conn.cursor() as cur:
            q = "SELECT * FROM financial_facts WHERE 1=1"
            params: list = []
            if user_id:
                q += " AND user_id = %s"; params.append(user_id)
            if status:
                q += " AND status = %s"; params.append(status)
            q += " ORDER BY transaction_date DESC"
            cur.execute(q, params)
            return [_row_to_fact(r) for r in cur.fetchall()]


# ── Skills ────────────────────────────────────────────────────────────────────

def _row_to_skill(row) -> Skill:
    return Skill(
        id=row["id"], user_id=row["user_id"], name=row["name"],
        domain=row["domain"], proficiency=row["proficiency"],
        actively_using=bool(row["actively_using"]), notes=row["notes"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def save_skill(skill: Skill):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO skills
                   (id, user_id, name, domain, proficiency, actively_using, notes, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                       name=EXCLUDED.name, domain=EXCLUDED.domain, proficiency=EXCLUDED.proficiency,
                       actively_using=EXCLUDED.actively_using, notes=EXCLUDED.notes,
                       updated_at=EXCLUDED.updated_at""",
                (
                    skill.id, skill.user_id, skill.name, skill.domain,
                    skill.proficiency, int(skill.actively_using), skill.notes,
                    skill.updated_at.isoformat(),
                ),
            )


def list_skills(user_id: Optional[str] = None) -> list[Skill]:
    with _db() as conn:
        with conn.cursor() as cur:
            q = "SELECT * FROM skills WHERE 1=1"
            params: list = []
            if user_id:
                q += " AND user_id = %s"; params.append(user_id)
            q += " ORDER BY domain, name"
            cur.execute(q, params)
            return [_row_to_skill(r) for r in cur.fetchall()]


# ── Relationships ─────────────────────────────────────────────────────────────

def _row_to_relationship(row) -> Relationship:
    return Relationship(
        id=row["id"], user_id=row["user_id"], name=row["name"],
        relationship_type=row["relationship_type"], notes=row["notes"],
        last_mentioned=datetime.fromisoformat(row["last_mentioned"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def save_relationship(rel: Relationship):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO relationships
                   (id, user_id, name, relationship_type, notes, last_mentioned, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                       name=EXCLUDED.name, relationship_type=EXCLUDED.relationship_type,
                       notes=EXCLUDED.notes, last_mentioned=EXCLUDED.last_mentioned""",
                (
                    rel.id, rel.user_id, rel.name, rel.relationship_type,
                    rel.notes, rel.last_mentioned.isoformat(), rel.created_at.isoformat(),
                ),
            )


def list_relationships(user_id: Optional[str] = None) -> list[Relationship]:
    with _db() as conn:
        with conn.cursor() as cur:
            q = "SELECT * FROM relationships WHERE 1=1"
            params: list = []
            if user_id:
                q += " AND user_id = %s"; params.append(user_id)
            q += " ORDER BY last_mentioned DESC"
            cur.execute(q, params)
            return [_row_to_relationship(r) for r in cur.fetchall()]


# ── Delegated Tasks ───────────────────────────────────────────────────────────

def _row_to_task(row) -> DelegatedTask:
    return DelegatedTask(
        id=row["id"], user_id=row["user_id"], description=row["description"],
        category=row["category"], source=row["source"], status=row["status"],
        check_in_date=row["check_in_date"], outcome=row["outcome"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def save_delegated_task(task: DelegatedTask):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO delegated_tasks
                   (id, user_id, description, category, source, status, check_in_date, outcome, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                       description=EXCLUDED.description, category=EXCLUDED.category,
                       source=EXCLUDED.source, status=EXCLUDED.status,
                       check_in_date=EXCLUDED.check_in_date, outcome=EXCLUDED.outcome,
                       updated_at=EXCLUDED.updated_at""",
                (
                    task.id, task.user_id, task.description, task.category,
                    task.source, task.status, task.check_in_date, task.outcome,
                    task.created_at.isoformat(), task.updated_at.isoformat(),
                ),
            )


def get_delegated_task(task_id: str) -> Optional[DelegatedTask]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM delegated_tasks WHERE id = %s", (task_id,))
            row = cur.fetchone()
    return _row_to_task(row) if row else None


def list_delegated_tasks(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
) -> list[DelegatedTask]:
    with _db() as conn:
        with conn.cursor() as cur:
            q = "SELECT * FROM delegated_tasks WHERE 1=1"
            params: list = []
            if user_id:
                q += " AND user_id = %s"; params.append(user_id)
            if status:
                q += " AND status = %s"; params.append(status)
            q += " ORDER BY updated_at DESC"
            cur.execute(q, params)
            return [_row_to_task(r) for r in cur.fetchall()]


# ── Follow-ups ────────────────────────────────────────────────────────────────

def _row_to_followup(row) -> Followup:
    return Followup(
        id=row["id"], user_id=row["user_id"], question=row["question"],
        source_entity_type=row["source_entity_type"],
        source_entity_id=row["source_entity_id"],
        status=row["status"], answer=row["answer"],
        created_at=datetime.fromisoformat(row["created_at"]),
        answered_at=datetime.fromisoformat(row["answered_at"]) if row["answered_at"] else None,
    )


def save_followup(fu: Followup):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO followups
                   (id, user_id, question, source_entity_type, source_entity_id, status, answer, created_at, answered_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                       status=EXCLUDED.status, answer=EXCLUDED.answer,
                       answered_at=EXCLUDED.answered_at""",
                (
                    fu.id, fu.user_id, fu.question, fu.source_entity_type,
                    fu.source_entity_id, fu.status, fu.answer,
                    fu.created_at.isoformat(),
                    fu.answered_at.isoformat() if fu.answered_at else None,
                ),
            )


def get_followup(fu_id: str) -> Optional[Followup]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM followups WHERE id = %s", (fu_id,))
            row = cur.fetchone()
    return _row_to_followup(row) if row else None


def list_followups(
    status: Optional[str] = "pending",
    user_id: Optional[str] = None,
) -> list[Followup]:
    with _db() as conn:
        with conn.cursor() as cur:
            q = "SELECT * FROM followups WHERE 1=1"
            params: list = []
            if user_id:
                q += " AND user_id = %s"; params.append(user_id)
            if status:
                q += " AND status = %s"; params.append(status)
            q += " ORDER BY created_at DESC"
            cur.execute(q, params)
            return [_row_to_followup(r) for r in cur.fetchall()]


# ── Profile ───────────────────────────────────────────────────────────────────

def get_profile(user_id: str = "default") -> dict:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM user_profile WHERE user_id = %s", (user_id,))
            rows = cur.fetchall()
    return {r["key"]: json.loads(r["value"]) for r in rows}


def update_profile(updates: dict, user_id: str = "default"):
    with _db() as conn:
        with conn.cursor() as cur:
            for key, value in updates.items():
                cur.execute(
                    """INSERT INTO user_profile (user_id, key, value) VALUES (%s, %s, %s)
                       ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value""",
                    (user_id, key, json.dumps(value)),
                )
