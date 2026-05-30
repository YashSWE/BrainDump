from datetime import datetime, timezone

from models import Followup
from storage import (
    list_events, save_event,
    list_financial_facts, save_financial_fact,
    list_goals,
    list_delegated_tasks,
    list_followups, save_followup,
)


def _already_has_followup(entity_id: str, existing: list[Followup]) -> bool:
    return any(fu.source_entity_id == entity_id and fu.status == "pending" for fu in existing)


def generate_followups(user_id: str = "default"):
    today = datetime.now(timezone.utc).date()
    existing = list_followups(status=None, user_id=user_id)

    for event in list_events(user_id=user_id):
        if _already_has_followup(event.id, existing):
            continue
        try:
            event_date = datetime.strptime(event.event_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if event_date < today and not event.outcome and not event.follow_up_sent:
            fu = Followup(
                user_id=user_id,
                question=f'Your event "{event.title}" was on {event.event_date} — how did it go?',
                source_entity_type="event",
                source_entity_id=event.id,
            )
            save_followup(fu)
            event.follow_up_sent = True
            save_event(event)

    for fact in list_financial_facts(user_id=user_id):
        if _already_has_followup(fact.id, existing):
            continue
        if fact.status != "active":
            continue
        try:
            fact_date = datetime.strptime(fact.transaction_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        age_days = (today - fact_date).days
        if age_days >= 60 and not fact.follow_up_sent:
            fu = Followup(
                user_id=user_id,
                question=f"You {fact.type}d {fact.currency} {fact.amount:,.0f} in {fact.asset} on {fact.transaction_date} — still {fact.status}?",
                source_entity_type="financial_fact",
                source_entity_id=fact.id,
            )
            save_followup(fu)
            fact.follow_up_sent = True
            save_financial_fact(fact)

    for goal in list_goals(status="active", user_id=user_id):
        if _already_has_followup(goal.id, existing):
            continue
        try:
            updated = datetime.fromisoformat(goal.updated_at.isoformat()).date()
        except Exception:
            continue
        age_days = (today - updated).days
        if age_days >= 30:
            fu = Followup(
                user_id=user_id,
                question=f'You set a goal "{goal.title}" ({goal.progress}% complete) — any progress?',
                source_entity_type="goal",
                source_entity_id=goal.id,
            )
            save_followup(fu)

    for task in list_delegated_tasks(status="active", user_id=user_id):
        if _already_has_followup(task.id, existing):
            continue
        if not task.check_in_date:
            continue
        try:
            checkin = datetime.strptime(task.check_in_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if checkin <= today:
            fu = Followup(
                user_id=user_id,
                question=f'You asked me to track: "{task.description}" — any update?',
                source_entity_type="delegated_task",
                source_entity_id=task.id,
            )
            save_followup(fu)
