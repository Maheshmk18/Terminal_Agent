from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.safety.models import PendingCall


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    pending_calls: list[PendingCall]
    approved_ids: list[str]
    iterations: int
    working_dir: str
