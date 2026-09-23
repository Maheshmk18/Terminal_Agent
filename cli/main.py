import asyncio
from uuid import uuid4

import typer
from websockets.exceptions import ConnectionClosed, InvalidHandshake

from cli import display
from cli.client import AgentClient

app = typer.Typer(add_completion=False, help="Talk to the terminal agent.", no_args_is_help=True)

EXIT_WORDS = {"exit", "quit", ":q"}


@app.command()
def chat(
    url: str = typer.Option("http://127.0.0.1:8000", help="Agent server URL"),
    thread: str = typer.Option("", help="Resume an existing session"),
) -> None:
    """Start an interactive session with the agent."""
    thread_id = thread or uuid4().hex[:12]
    asyncio.run(_run(url, thread_id))


@app.command()
def version() -> None:
    """Show the client version."""
    typer.echo("terminal-agent 0.1.0")


async def _run(url: str, thread_id: str) -> None:
    display.show_banner(url, thread_id)

    try:
        async with AgentClient(url, thread_id) as client:
            await _loop(client)
    except (OSError, InvalidHandshake):
        display.show_error(f"Could not reach {url}, is the server running?")
    except ConnectionClosed:
        display.show_error("The server closed the connection, restart it and try again.")


async def _loop(client: AgentClient) -> None:
    while True:
        try:
            text = display.prompt_user().strip()
        except (EOFError, KeyboardInterrupt):
            return

        if not text:
            continue
        if text.lower() in EXIT_WORDS:
            return

        try:
            await _turn(client, client.send_message(text))
        except ConnectionClosed:
            display.show_error("The server dropped the connection, reconnecting.")
            if not await client.reconnect():
                display.show_error("Could not reconnect, is the server running?")
                return


async def _turn(client: AgentClient, stream) -> None:
    while stream is not None:
        request = await _consume(stream)

        if request is None:
            return

        approved = display.ask_approval(request)
        stream = client.send_approval(approved)


async def _consume(stream) -> dict | None:
    streamed = False
    started = False

    async for frame in stream:
        kind = frame.get("type")

        if kind == "token":
            if not started:
                display.start_reply()
                started = True
            display.write_token(frame["text"])
            streamed = True

        elif kind == "approval_request":
            if streamed:
                display.finish_reply("", streamed=True)
            return frame

        elif kind == "done":
            if not started:
                display.start_reply()
            display.finish_reply(frame.get("reply", ""), streamed)
            return None

        elif kind == "error":
            display.show_error(frame.get("message", "unknown error"))
            return None

    return None


if __name__ == "__main__":
    app()
