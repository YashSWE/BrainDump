from contextvars import ContextVar

current_user_id: ContextVar[str] = ContextVar("current_user_id", default="default")


def get_user_id() -> str:
    return current_user_id.get()
