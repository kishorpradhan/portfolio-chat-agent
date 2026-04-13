import json
import sys
from typing import Any

from urllib.request import Request, urlopen

DEFAULT_URL = "http://localhost:8082/chat/run"


def run(question: str, conversation_id: str | None = None, url: str = DEFAULT_URL) -> dict[str, Any]:
    payload: dict[str, Any] = {"question": question}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def main() -> None:
    url = DEFAULT_URL
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        url = sys.argv[1]
        args = sys.argv[2:]
    else:
        args = sys.argv[1:]

    if not args:
        print("Usage: python scripts/test_chat_run.py [url] \"question\"")
        sys.exit(1)

    question = " ".join(args)
    first = run(question, url=url)
    print("First response:\n", json.dumps(first, indent=2))

    if first.get("followup_needed"):
        conversation_id = first.get("conversation_id")
        followup = "What are my top 5 holdings in the US market?"
        second = run(followup, conversation_id=conversation_id, url=url)
        print("\nFollow-up response:\n", json.dumps(second, indent=2))


if __name__ == "__main__":
    main()
