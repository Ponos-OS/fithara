"""
Filesystem contents under the repo must be byte-identical before and after
a batch of requests — the stateless contract's "no server-side storage"
promise extended to "no disk writes at all", not just "no state kept in
memory between requests".
"""

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from httpx import AsyncClient


REPO_ROOT = Path(__file__).parent.parent
EXCLUDED_DIR_NAMES = {".git", ".pytest_cache", "__pycache__", ".ruff_cache", ".venv", ".mypy_cache"}


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    snapshot = {}
    for path in root.rglob("*"):
        if path.is_dir() or EXCLUDED_DIR_NAMES.intersection(path.parts):
            continue
        stat = path.stat()
        snapshot[str(path.relative_to(root))] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


async def test_no_disk_writes_across_a_batch_of_requests(
    app: FastAPI, client: AsyncClient, stub_agent: Callable[[FastAPI, dict], None]
) -> None:
    stub_agent(
        app,
        {
            "assistantMessage": "here you go",
            "draft": None,
            "draftChanged": False,
            "recommendations": [],
            "disclaimers": ["This is not legal advice."],
            "isReadyToFinalize": False,
        },
    )
    before = _snapshot(REPO_ROOT)

    await client.get("/v1/licenses")
    await client.get("/v1/licenses/FIXTURE-ACTIVE")
    await client.get("/v1/licenses/DOES-NOT-EXIST")
    await client.post("/v1/draft", json={"message": "what license should I use?"})
    await client.post("/v1/draft", json={"message": ""})

    after = _snapshot(REPO_ROOT)  # act

    assert after == before
