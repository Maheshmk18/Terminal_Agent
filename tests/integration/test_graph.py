import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph.interrupts import get_pending_interrupt
from app.graph.workflow import build_graph
from tests.integration.fake_llm import FakeChatModel


def config(thread: str) -> dict:
    return {"configurable": {"thread_id": thread}}


def tool_call(name: str, args: dict, call_id: str = "call_1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"id": call_id, "name": name, "args": args}],
    )


@pytest.fixture
def graph_factory():
    def make(responses):
        return build_graph(llm=FakeChatModel(responses=responses), checkpointer=MemorySaver())

    return make


async def test_plain_reply_ends_without_tools(graph_factory):
    graph = graph_factory([AIMessage(content="Hello there")])

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="hi")]},
        config("t1"),
    )

    assert result["messages"][-1].content == "Hello there"


async def test_safe_tool_runs_without_approval(graph_factory):
    graph = graph_factory(
        [
            tool_call("list_directory", {"path": "."}),
            AIMessage(content="Listed the directory"),
        ]
    )

    cfg = config("t2")
    result = await graph.ainvoke({"messages": [HumanMessage(content="list files")]}, cfg)

    tool_message = next(m for m in result["messages"] if m.type == "tool")
    assert "denied" not in tool_message.content.lower()
    assert result["messages"][-1].content == "Listed the directory"
    assert await get_pending_interrupt(graph, cfg) is None


async def test_risky_tool_interrupts_for_approval(graph_factory):
    graph = graph_factory(
        [
            tool_call("run_shell_command", {"command": "rm -rf build"}),
            AIMessage(content="Deleted the folder"),
        ]
    )

    cfg = config("t3")
    await graph.ainvoke({"messages": [HumanMessage(content="delete build")]}, cfg)

    payload = await get_pending_interrupt(graph, cfg)

    assert payload["type"] == "approval_request"
    assert payload["calls"][0]["risk"] == "dangerous"
    assert payload["calls"][0]["command"] == "rm -rf build"


async def test_denied_call_is_reported_to_the_model(graph_factory):
    graph = graph_factory(
        [
            tool_call("run_shell_command", {"command": "rm -rf build"}),
            AIMessage(content="Understood, I will not delete it"),
        ]
    )
    cfg = config("t4")

    await graph.ainvoke({"messages": [HumanMessage(content="delete build")]}, cfg)
    result = await graph.ainvoke(Command(resume={"approved": False}), cfg)

    tool_message = next(m for m in result["messages"] if m.type == "tool")
    assert "denied" in tool_message.content.lower()


async def test_approved_call_executes(graph_factory, tmp_path, monkeypatch):
    from app.config import Settings

    monkeypatch.setattr(
        "app.tools.filesystem.get_settings",
        lambda: Settings(_env_file=None, WORKING_DIR=str(tmp_path)),
    )

    graph = graph_factory(
        [
            tool_call("write_file", {"path": "note.txt", "content": "saved"}),
            AIMessage(content="File written"),
        ]
    )
    cfg = config("t5")

    await graph.ainvoke({"messages": [HumanMessage(content="write a note")]}, cfg)
    result = await graph.ainvoke(Command(resume={"approved": True}), cfg)

    assert (tmp_path / "note.txt").read_text() == "saved"
    assert result["messages"][-1].content == "File written"


async def test_blocked_call_never_executes(graph_factory):
    graph = graph_factory(
        [
            tool_call("run_shell_command", {"command": "rm -rf /"}),
            AIMessage(content="That would be destructive"),
        ]
    )

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="wipe everything")]},
        config("t6"),
    )

    tool_message = next(m for m in result["messages"] if m.type == "tool")
    assert "blocked" in tool_message.content.lower()


async def test_iteration_limit_stops_a_loop(graph_factory, monkeypatch):
    from app.config import Settings

    monkeypatch.setattr(
        "app.graph.nodes.agent_node.get_settings",
        lambda: Settings(_env_file=None, MAX_ITERATIONS=3),
    )

    graph = graph_factory([tool_call("list_directory", {"path": "."}, f"c{i}") for i in range(10)])

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="loop forever")]},
        config("t7"),
    )

    final = result["messages"][-1].content
    assert "stopped after 3 steps" in final
    assert "MAX_ITERATIONS" in final
