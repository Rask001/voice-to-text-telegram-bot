import json
from typing import TypedDict


class TaskItem(TypedDict):
    text: str
    priority: bool


def normalize_tasks(value: object) -> list[TaskItem]:
    if isinstance(value, str):
        return parse_stored_tasks(value)
    if not isinstance(value, list):
        return []

    tasks = []
    for item in value:
        task = _normalize_task(item)
        if task is not None:
            tasks.append(task)
    return tasks


def serialize_tasks(tasks: list[TaskItem]) -> str:
    return json.dumps(tasks, ensure_ascii=False)


def parse_stored_tasks(value: str | None) -> list[TaskItem]:
    if not value:
        return []

    try:
        raw_tasks = json.loads(value)
    except json.JSONDecodeError:
        raw_tasks = None

    if isinstance(raw_tasks, list):
        return normalize_tasks(raw_tasks)

    return [{"text": line, "priority": False} for line in split_stored_list(value)]


def sort_tasks_for_display(tasks: list[TaskItem]) -> list[TaskItem]:
    priority_tasks = [task for task in tasks if task["priority"]]
    regular_tasks = [task for task in tasks if not task["priority"]]
    return priority_tasks + regular_tasks


def split_stored_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [line.strip() for line in value.splitlines() if line.strip()]


def _normalize_task(value: object) -> TaskItem | None:
    if isinstance(value, dict):
        text = str(value.get("text", "")).strip()
        priority = bool(value.get("priority", False))
    else:
        text = str(value).strip()
        priority = False

    if not text:
        return None
    return {"text": text, "priority": priority}
