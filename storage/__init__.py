import os

if os.environ.get("DATABASE_URL"):
    from storage.pg_db import (
        init_db,
        save_memory, get_memory, delete_memory, list_memories,
        save_goal, get_goal, list_goals,
        save_event, get_event, list_events,
        save_financial_fact, get_financial_fact, list_financial_facts,
        save_skill, list_skills,
        save_relationship, list_relationships,
        save_delegated_task, get_delegated_task, list_delegated_tasks,
        save_followup, get_followup, list_followups,
        get_profile, update_profile,
    )
    from storage.pg_vectors import (
        add_memory as vec_add_memory,
        search_memories,
        delete_memory as vec_delete_memory,
    )
else:
    from storage.db import (
        init_db,
        save_memory, get_memory, delete_memory, list_memories,
        save_goal, get_goal, list_goals,
        save_event, get_event, list_events,
        save_financial_fact, get_financial_fact, list_financial_facts,
        save_skill, list_skills,
        save_relationship, list_relationships,
        save_delegated_task, get_delegated_task, list_delegated_tasks,
        save_followup, get_followup, list_followups,
        get_profile, update_profile,
    )
    from storage.vectors import (
        add_memory as vec_add_memory,
        search_memories,
        delete_memory as vec_delete_memory,
    )
