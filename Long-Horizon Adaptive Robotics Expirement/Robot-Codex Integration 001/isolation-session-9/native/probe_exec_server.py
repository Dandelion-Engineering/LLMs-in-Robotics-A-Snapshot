"""Read-only protocol metadata probe; never starts a model turn or child command."""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from websockets.asyncio.client import connect


async def probe(url: str) -> dict:
    messages = []
    async with connect(url, open_timeout=5, close_timeout=2, max_size=1_048_576, proxy=None) as socket:
        async def request(number: int, method: str, params: dict) -> dict:
            value = {"id": number, "method": method, "params": params}
            messages.append({"direction": "sent", "message": value})
            await socket.send(json.dumps(value))
            while True:
                response = json.loads(await asyncio.wait_for(socket.recv(), 8))
                messages.append({"direction": "received", "message": response})
                if response.get("id") == number:
                    if "error" in response:
                        raise RuntimeError(json.dumps(response["error"]))
                    return response["result"]

        initialized = await request(1, "initialize", {"clientName": "robot-isolation-nonmodel-probe"})
        notification = {"method": "initialized", "params": {}}
        messages.append({"direction": "sent", "message": notification})
        await socket.send(json.dumps(notification))
        info = await request(2, "environment/info", {})
        status = await request(3, "environment/status", {})
    return {
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": url,
        "probe_scope": "initialize and environment metadata only; no file, process, auth, or model RPC",
        "expected_linux_01571": info.get("platformOs") == "linux" and info.get("executorVersion") == "0.157.1",
        "initialize": initialized,
        "environment_info": info,
        "environment_status": status,
        "messages": messages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.url.startswith("ws://127.0.0.1:"):
        parser.error("Only the explicitly launched loopback bridge is allowed")
    if args.out.exists():
        parser.error("Use a fresh evidence file")
    try:
        result = asyncio.run(asyncio.wait_for(probe(args.url), 25))
    except Exception as error:
        result = {"passed": False, "error_type": type(error).__name__, "error": str(error)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result.get("expected_linux_01571") else 1


if __name__ == "__main__":
    raise SystemExit(main())
