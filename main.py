#!/usr/bin/env python3
"""Snippets CLI - A note-taking REPL with PostgreSQL storage."""

import os
from pathlib import Path

from dotenv import load_dotenv
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings

import httpx
from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.input.vt100_parser import _IS_PREFIX_OF_LONGER_MATCH_CACHE
from prompt_toolkit.keys import Keys

import client

# Map Shift+Enter (kitty/CSI u protocol from WezTerm) to Ctrl+J
ANSI_SEQUENCES["\x1b[13;2u"] = Keys.ControlJ
_IS_PREFIX_OF_LONGER_MATCH_CACHE.clear()
from session import Session
from commands import dispatch
from completers import ReplCompleter

load_dotenv()

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5000")
EXPORT_DIR = os.environ.get("EXPORT_DIR", "./exports")


def main():
    client.init(BACKEND_URL)

    try:
        client.health()
    except (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError):
        print("Error: SnippetsBackend is not reachable.")
        print("Make sure the backend is running (docker compose up --build).")
        return

    session = Session()
    completer = ReplCompleter()

    history_dir = Path.home() / ".snippets_cli"
    history_dir.mkdir(exist_ok=True)
    history = FileHistory(str(history_dir / "history"))

    kb = KeyBindings()

    @kb.add("c-j")
    def _insert_newline(event):
        event.current_buffer.insert_text("\n")

    print("Snippets CLI ready. Type 'help' for commands.")
    if client.is_authenticated():
        try:
            user = client.me()
            print(f"Logged in as {user['username']}.")
        except client.AuthExpiredError:
            print("Session expired. Please 'login' again.")
            client.clear_token()
    else:
        print("Not logged in. Type 'login' or 'register' to get started.")

    while True:
        try:
            src_label = ""
            try:
                if session.current_source_id:
                    src = client.get_source(session.current_source_id)
                    if src:
                        src_label = f' [{src["name"][:20]}]'
            except (httpx.NetworkError, httpx.TimeoutException):
                src_label = " [offline]"

            user_input = prompt(f"snippets{src_label}> ", history=history,
                                completer=completer, complete_while_typing=False,
                                key_bindings=kb)
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        try:
            if not dispatch(user_input, session, EXPORT_DIR):
                break
        except (httpx.NetworkError, httpx.TimeoutException):
            print("Error: SnippetsBackend is not reachable.")
            print("Check that the backend is still running.")
        except client.BackendError as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
