"""Proposed read-only example; runtime execution awaits program authorization."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from robot import Client


def inspect_public_state(client):
    """One public status request; no actuation, retry, polling or host import."""
    return client.status()


if __name__ == "__main__":
    print(json.dumps(inspect_public_state(Client()), ensure_ascii=False))
