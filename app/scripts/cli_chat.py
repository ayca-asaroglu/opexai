"""
Interactive CLI client for the orchestration flow API.

Extension points:
- Add persistent session storage for chat history.
- Add authentication headers or request signing.
- Add streaming output support if the API supports it.

Example usage:
    python -m app.scripts.cli_chat --url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = os.getenv("LLM_ORCH_API_URL", "http://127.0.0.1:8000")


def build_payload(question: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build the request payload for the /flow/run endpoint.

    Extension points:
    - Add optional nodes or custom orchestration metadata.
    - Add additional input fields for prompt customization.
    """

    return {
        "nodes": [],
        "input": {
            "question": question,
            "chat_history": history,
        },
    }


def call_flow(url: str, payload: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    """
    Call the /flow/run endpoint and return the parsed JSON response.

    Extension points:
    - Add retry logic for transient network errors.
    - Add custom headers for auth or tracing.
    """

    endpoint = f"{url.rstrip('/')}/flow/run"
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"HTTP {exc.code} error: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Connection error: {exc.reason}") from exc

    return json.loads(raw)


def extract_output(response: dict[str, Any]) -> str:
    """
    Extract a displayable response payload from the API response.

    Extension points:
    - Handle structured tool calls or streaming output.
    - Add formatting for trace metadata.
    """

    output = response.get("answer", response.get("output", ""))
    if isinstance(output, str):
        return output
    return json.dumps(output, ensure_ascii=False, indent=2)


def append_history(
    history: list[dict[str, Any]],
    question: str,
    answer: str,
) -> None:
    """
    Append the latest conversation turn to the history.

    Extension points:
    - Store additional metadata such as timestamps.
    - Persist history to disk for long-running sessions.
    """

    history.append(
        {
            "inputs": {"question": question},
            "outputs": {"llm_output": answer},
        }
    )


def run_chat(base_url: str) -> None:
    """
    Run an interactive CLI chat session against the flow API.

    Extension points:
    - Add interactive commands to reset or export history.
    - Add formatted output or multi-line input handling.
    """

    print("LLM Orchestration CLI - type 'exit' to quit.")
    history: list[dict[str, Any]] = []

    while True:
        question = input("> ").strip()
        if not question:
            continue
        if question.lower() in {"exit", "quit", "q"}:
            print("Görüşmek üzere.")
            break

        payload = build_payload(question, history)
        response = call_flow(base_url, payload)
        answer = extract_output(response)
        print(answer)
        append_history(history, question, answer)


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments for the CLI client.

    Extension points:
    - Add options for authentication or default input values.
    """

    parser = argparse.ArgumentParser(description="Flow CLI client.")
    parser.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help="Base URL for the orchestration API.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Entry point for the CLI script.

    Extension points:
    - Add startup diagnostics or environment validation.
    """

    args = parse_args()
    run_chat(args.url)


if __name__ == "__main__":
    main()
