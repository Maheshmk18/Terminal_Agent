from typing import Any


async def get_pending_interrupt(graph, config: dict) -> dict | None:
    snapshot = await graph.aget_state(config)

    for task in snapshot.tasks:
        for interrupt in task.interrupts:
            return _as_dict(interrupt.value)

    return None


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    return {"type": "approval_request", "payload": value}
