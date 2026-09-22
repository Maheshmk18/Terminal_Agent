import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from app.graph.runtime import AgentRuntime
from app.graph.workflow import build_graph
from app.main import create_app
from tests.integration.fake_llm import FakeChatModel


def tool_call(name: str, args: dict) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"id": "c1", "name": name, "args": args}])


def client_with(responses: list[AIMessage]) -> TestClient:
    app = create_app()
    graph = build_graph(llm=FakeChatModel(responses=responses), checkpointer=MemorySaver())

    client = TestClient(app)
    client.__enter__()
    app.state.runtime = AgentRuntime(graph)
    return client


@pytest.fixture
def safe_client():
    client = client_with([tool_call("list_directory", {"path": "."}), AIMessage(content="Done")])
    yield client
    client.__exit__(None, None, None)


@pytest.fixture
def risky_client():
    client = client_with(
        [tool_call("run_shell_command", {"command": "rm -rf build"}), AIMessage(content="Removed")]
    )
    yield client
    client.__exit__(None, None, None)


def test_chat_returns_a_reply(safe_client):
    response = safe_client.post("/api/chat", json={"message": "list files"})
    body = response.json()

    assert response.status_code == 200
    assert body["reply"] == "Done"
    assert body["awaiting_approval"] is False
    assert body["thread_id"]


def test_chat_pauses_on_risky_command(risky_client):
    body = risky_client.post("/api/chat", json={"message": "delete build"}).json()

    assert body["awaiting_approval"] is True
    assert body["approval_request"]["calls"][0]["risk"] == "dangerous"


def test_approval_resumes_the_thread(risky_client):
    started = risky_client.post("/api/chat", json={"message": "delete build"}).json()

    resumed = risky_client.post(
        "/api/approve",
        json={"thread_id": started["thread_id"], "approved": False},
    ).json()

    assert resumed["awaiting_approval"] is False
    assert resumed["reply"] == "Removed"


def test_history_is_kept_per_thread(safe_client):
    started = safe_client.post("/api/chat", json={"message": "list files"}).json()

    history = safe_client.get(f"/api/sessions/{started['thread_id']}/history").json()
    roles = [message["role"] for message in history["messages"]]

    assert "human" in roles
    assert "ai" in roles


def test_empty_message_is_rejected(safe_client):
    assert safe_client.post("/api/chat", json={"message": ""}).status_code == 422


def test_routes_fail_cleanly_without_a_runtime():
    app = create_app()
    with TestClient(app) as client:
        app.state.runtime = None
        assert client.post("/api/chat", json={"message": "hi"}).status_code == 503


def test_websocket_streams_and_asks_for_approval(risky_client):
    with risky_client.websocket_connect("/ws/wsthread") as socket:
        socket.send_json({"type": "message", "text": "delete build"})

        frame = socket.receive_json()
        assert frame["type"] == "approval_request"
        assert frame["calls"][0]["command"] == "rm -rf build"

        socket.send_json({"type": "approval", "approved": False})
        assert socket.receive_json()["type"] == "done"


def test_websocket_reports_unknown_frames(safe_client):
    with safe_client.websocket_connect("/ws/wsthread2") as socket:
        socket.send_json({"type": "nonsense"})
        assert socket.receive_json()["type"] == "error"
