import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from models import Memory, Goal, Event, FinancialFact, Skill, Relationship, DelegatedTask, Followup

DB_PATH = Path.home() / ".braindump" / "braindump.db"


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn):
    """Add columns introduced after initial schema — safe to run every startup."""
    migrations = [
        ("memories", "user_id",      "TEXT DEFAULT 'default'"),
        ("memories", "mood",         "TEXT"),
        ("memories", "emotion_tags", "TEXT DEFAULT '[]'"),
        ("memories", "source",       "TEXT DEFAULT 'unknown'"),
        ("memories", "type",         "TEXT DEFAULT 'fact'"),
    ]
    existing = {
        table: {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for table in ("memories",)
    }
    for table, col, typedef in migrations:
        if col not in existing.get(table, set()):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
    conn.commit()


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id           TEXT PRIMARY KEY,
                user_id      TEXT DEFAULT 'default',
                content      TEXT NOT NULL,
                tags         TEXT DEFAULT '[]',
                category     TEXT DEFAULT 'general',
                mood         TEXT,
                emotion_tags TEXT DEFAULT '[]',
                importance   INTEGER DEFAULT 5,
                source       TEXT DEFAULT 'unknown',
                created_at   TEXT NOT NULL
            )
        """)
        _migrate(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id          TEXT PRIMARY KEY,
                user_id     TEXT DEFAULT 'default',
                title       TEXT NOT NULL,
                category    TEXT NOT NULL,
                progress    INTEGER DEFAULT 0,
                milestones  TEXT DEFAULT '[]',
                deadline    TEXT,
                status      TEXT DEFAULT 'active',
                notes       TEXT,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id               TEXT PRIMARY KEY,
                user_id          TEXT DEFAULT 'default',
                title            TEXT NOT NULL,
                category         TEXT NOT NULL,
                event_date       TEXT NOT NULL,
                people_involved  TEXT DEFAULT '[]',
                outcome          TEXT,
                follow_up_sent   INTEGER DEFAULT 0,
                notes            TEXT,
                created_at       TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS financial_facts (
                id               TEXT PRIMARY KEY,
                user_id          TEXT DEFAULT 'default',
                type             TEXT NOT NULL,
                asset            TEXT NOT NULL,
                amount           REAL NOT NULL,
                currency         TEXT DEFAULT 'INR',
                transaction_date TEXT NOT NULL,
                status           TEXT DEFAULT 'active',
                notes            TEXT,
                follow_up_sent   INTEGER DEFAULT 0,
                created_at       TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id            TEXT PRIMARY KEY,
                user_id       TEXT DEFAULT 'default',
                name          TEXT NOT NULL,
                domain        TEXT NOT NULL,
                proficiency   TEXT DEFAULT 'intermediate',
                actively_using INTEGER DEFAULT 1,
                notes         TEXT,
                updated_at    TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id                TEXT PRIMARY KEY,
                user_id           TEXT DEFAULT 'default',
                name              TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                notes             TEXT,
                last_mentioned    TEXT NOT NULL,
                created_at        TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS delegated_tasks (
                id             TEXT PRIMARY KEY,
                user_id        TEXT DEFAULT 'default',
                description    TEXT NOT NULL,
                category       TEXT NOT NULL,
                source         TEXT DEFAULT 'unknown',
                status         TEXT DEFAULT 'active',
                check_in_date  TEXT,
                outcome        TEXT,
                created_at     TEXT NOT NULL,
                updated_at     TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS followups (
                id                 TEXT PRIMARY KEY,
                user_id            TEXT DEFAULT 'default',
                question           TEXT NOT NULL,
                source_entity_type TEXT NOT NULL,
                source_entity_id   TEXT NOT NULL,
                status             TEXT DEFAULT 'pending',
                answer             TEXT,
                created_at         TEXT NOT NULL,
                answered_at        TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.commit()


# ── Memory ──────────────────────────────────────────────────────────────────

def _parse_json_list(val) -> list:
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


def _row_to_memory(row) -> Memory:
    return Memory(
        id=row["id"],
        user_id=row["user_id"] or "default",
        content=row["content"],
        type=row["type"] or "fact",
        tags=_parse_json_list(row["tags"]),
        category=row["category"],
        mood=row["mood"],
        emotion_tags=_parse_json_list(row["emotion_tags"]),
        importance=row["importance"],
        source=row["source"] or "unknown",
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def save_memory(memory: Memory):
    with _conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO memories
               (id, user_id, content, type, tags, category, mood, emotion_tags, importance, source, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                memory.id, memory.user_id, memory.content, memory.type,
                json.dumps(memory.tags), memory.category,
                memory.mood, json.dumps(memory.emotion_tags),
                memory.importance, memory.source,
                memory.created_at.isoformat(),
            ),
        )
        conn.commit()


def get_memory(memory_id: str) -> Optional[Memory]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return _row_to_memory(row) if row else None


def delete_memory(memory_id: str) -> bool:
    with _conn() as conn:
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
        return cursor.rowcount > 0


def list_memories(
    category: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 500,
    user_id: Optional[str] = None,
) -> list[Memory]:
    with _conn() as conn:
        q = "SELECT * FROM memories WHERE 1=1"
        params: list = []
        if user_id:
            q += " AND user_id = ?"; params.append(user_id)
        if category:
            q += " AND category = ?"; params.append(category)
        if type:
            q += " AND type = ?"; params.append(type)
        q += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)
        return [_row_to_memory(r) for r in conn.execute(q, params).fetchall()]


# ── Goals ────────────────────────────────────────────────────────────────────

def save_goal(goal: Goal):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO goals VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                goal.id, goal.user_id, goal.title, goal.category,
                goal.progress, json.dumps(goal.milestones), goal.deadline,
                goal.status, goal.notes,
                goal.created_at.isoformat(), goal.updated_at.isoformat(),
            ),
        )
        conn.commit()


def get_goal(goal_id: str) -> Optional[Goal]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return _row_to_goal(row) if row else None


def _row_to_goal(row) -> Goal:
    return Goal(
        id=row["id"], user_id=row["user_id"], title=row["title"],
        category=row["category"], progress=row["progress"],
        milestones=json.loads(row["milestones"] or "[]"),
        deadline=row["deadline"], status=row["status"], notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def list_goals(
    category: Optional[str] = None,
    status: Optional[str] = None,
    user_id: Optional[str] = None,
) -> list[Goal]:
    with _conn() as conn:
        q = "SELECT * FROM goals WHERE 1=1"
        params: list = []
        if user_id:
            q += " AND user_id = ?"; params.append(user_id)
        if category:
            q += " AND category = ?"; params.append(category)
        if status:
            q += " AND status = ?"; params.append(status)
        q += " ORDER BY updated_at DESC"
        return [_row_to_goal(r) for r in conn.execute(q, params).fetchall()]


# ── Events ───────────────────────────────────────────────────────────────────

def save_event(event: Event):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                event.id, event.user_id, event.title, event.category,
                event.event_date, json.dumps(event.people_involved),
                event.outcome, int(event.follow_up_sent), event.notes,
                event.created_at.isoformat(),
            ),
        )
        conn.commit()


def get_event(event_id: str) -> Optional[Event]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return _row_to_event(row) if row else None


def _row_to_event(row) -> Event:
    return Event(
        id=row["id"], user_id=row["user_id"], title=row["title"],
        category=row["category"], event_date=row["event_date"],
        people_involved=json.loads(row["people_involved"] or "[]"),
        outcome=row["outcome"], follow_up_sent=bool(row["follow_up_sent"]),
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def list_events(user_id: Optional[str] = None) -> list[Event]:
    with _conn() as conn:
        if user_id:
            return [_row_to_event(r) for r in
                    conn.execute("SELECT * FROM events WHERE user_id = ? ORDER BY event_date DESC", (user_id,)).fetchall()]
        return [_row_to_event(r) for r in
                conn.execute("SELECT * FROM events ORDER BY event_date DESC").fetchall()]


# ── Financial Facts ───────────────────────────────────────────────────────────

def save_financial_fact(fact: FinancialFact):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO financial_facts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                fact.id, fact.user_id, fact.type, fact.asset, fact.amount,
                fact.currency, fact.transaction_date, fact.status, fact.notes,
                int(fact.follow_up_sent), fact.created_at.isoformat(),
            ),
        )
        conn.commit()


def get_financial_fact(fact_id: str) -> Optional[FinancialFact]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM financial_facts WHERE id = ?", (fact_id,)).fetchone()
        return _row_to_fact(row) if row else None


def _row_to_fact(row) -> FinancialFact:
    return FinancialFact(
        id=row["id"], user_id=row["user_id"], type=row["type"],
        asset=row["asset"], amount=row["amount"], currency=row["currency"],
        transaction_date=row["transaction_date"], status=row["status"],
        notes=row["notes"], follow_up_sent=bool(row["follow_up_sent"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def list_financial_facts(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
) -> list[FinancialFact]:
    with _conn() as conn:
        q = "SELECT * FROM financial_facts WHERE 1=1"
        params: list = []
        if user_id:
            q += " AND user_id = ?"; params.append(user_id)
        if status:
            q += " AND status = ?"; params.append(status)
        q += " ORDER BY transaction_date DESC"
        return [_row_to_fact(r) for r in conn.execute(q, params).fetchall()]


# ── Skills ────────────────────────────────────────────────────────────────────

def save_skill(skill: Skill):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO skills VALUES (?,?,?,?,?,?,?,?)",
            (
                skill.id, skill.user_id, skill.name, skill.domain,
                skill.proficiency, int(skill.actively_using), skill.notes,
                skill.updated_at.isoformat(),
            ),
        )
        conn.commit()


def _row_to_skill(row) -> Skill:
    return Skill(
        id=row["id"], user_id=row["user_id"], name=row["name"],
        domain=row["domain"], proficiency=row["proficiency"],
        actively_using=bool(row["actively_using"]), notes=row["notes"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def list_skills(user_id: Optional[str] = None) -> list[Skill]:
    with _conn() as conn:
        if user_id:
            return [_row_to_skill(r) for r in
                    conn.execute("SELECT * FROM skills WHERE user_id = ? ORDER BY domain, name", (user_id,)).fetchall()]
        return [_row_to_skill(r) for r in
                conn.execute("SELECT * FROM skills ORDER BY domain, name").fetchall()]


# ── Relationships ─────────────────────────────────────────────────────────────

def save_relationship(rel: Relationship):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO relationships VALUES (?,?,?,?,?,?,?)",
            (
                rel.id, rel.user_id, rel.name, rel.relationship_type,
                rel.notes, rel.last_mentioned.isoformat(), rel.created_at.isoformat(),
            ),
        )
        conn.commit()


def _row_to_relationship(row) -> Relationship:
    return Relationship(
        id=row["id"], user_id=row["user_id"], name=row["name"],
        relationship_type=row["relationship_type"], notes=row["notes"],
        last_mentioned=datetime.fromisoformat(row["last_mentioned"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def list_relationships(user_id: Optional[str] = None) -> list[Relationship]:
    with _conn() as conn:
        if user_id:
            return [_row_to_relationship(r) for r in
                    conn.execute("SELECT * FROM relationships WHERE user_id = ? ORDER BY last_mentioned DESC", (user_id,)).fetchall()]
        return [_row_to_relationship(r) for r in
                conn.execute("SELECT * FROM relationships ORDER BY last_mentioned DESC").fetchall()]


# ── Delegated Tasks ───────────────────────────────────────────────────────────

def save_delegated_task(task: DelegatedTask):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO delegated_tasks VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                task.id, task.user_id, task.description, task.category,
                task.source, task.status, task.check_in_date, task.outcome,
                task.created_at.isoformat(), task.updated_at.isoformat(),
            ),
        )
        conn.commit()


def get_delegated_task(task_id: str) -> Optional[DelegatedTask]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM delegated_tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None


def _row_to_task(row) -> DelegatedTask:
    return DelegatedTask(
        id=row["id"], user_id=row["user_id"], description=row["description"],
        category=row["category"], source=row["source"], status=row["status"],
        check_in_date=row["check_in_date"], outcome=row["outcome"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def list_delegated_tasks(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
) -> list[DelegatedTask]:
    with _conn() as conn:
        q = "SELECT * FROM delegated_tasks WHERE 1=1"
        params: list = []
        if user_id:
            q += " AND user_id = ?"; params.append(user_id)
        if status:
            q += " AND status = ?"; params.append(status)
        q += " ORDER BY updated_at DESC"
        return [_row_to_task(r) for r in conn.execute(q, params).fetchall()]


# ── Follow-ups ────────────────────────────────────────────────────────────────

def save_followup(fu: Followup):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO followups VALUES (?,?,?,?,?,?,?,?,?)",
            (
                fu.id, fu.user_id, fu.question, fu.source_entity_type,
                fu.source_entity_id, fu.status, fu.answer,
                fu.created_at.isoformat(),
                fu.answered_at.isoformat() if fu.answered_at else None,
            ),
        )
        conn.commit()


def get_followup(fu_id: str) -> Optional[Followup]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM followups WHERE id = ?", (fu_id,)).fetchone()
        return _row_to_followup(row) if row else None


def _row_to_followup(row) -> Followup:
    return Followup(
        id=row["id"], user_id=row["user_id"], question=row["question"],
        source_entity_type=row["source_entity_type"],
        source_entity_id=row["source_entity_id"],
        status=row["status"], answer=row["answer"],
        created_at=datetime.fromisoformat(row["created_at"]),
        answered_at=datetime.fromisoformat(row["answered_at"]) if row["answered_at"] else None,
    )


def list_followups(
    status: Optional[str] = "pending",
    user_id: Optional[str] = None,
) -> list[Followup]:
    with _conn() as conn:
        q = "SELECT * FROM followups WHERE 1=1"
        params: list = []
        if user_id:
            q += " AND user_id = ?"; params.append(user_id)
        if status:
            q += " AND status = ?"; params.append(status)
        q += " ORDER BY created_at DESC"
        return [_row_to_followup(r) for r in conn.execute(q, params).fetchall()]


# ── Profile ───────────────────────────────────────────────────────────────────

def get_profile(user_id: Optional[str] = None) -> dict:
    with _conn() as conn:
        rows = conn.execute("SELECT key, value FROM user_profile").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}


def update_profile(updates: dict, user_id: Optional[str] = None):
    with _conn() as conn:
        for key, value in updates.items():
            conn.execute(
                "INSERT OR REPLACE INTO user_profile (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )
        conn.commit()
