import shutil
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import create_app
from src.registry.loader import get_registry, load_registry


REAL_SCHEMA = Path(__file__).parent.parent / "src" / "licenses" / "_schema.json"

_LICENSE_TEMPLATE = """---
id: {id}
name: {name}
shortName: {short_name}
version: "1.0"
category: creative_commons
officialUrl: https://example.com/{id}
summary: A fixture license.
permissions: [share]
limitations: []
conditions: [attribution]
active: {active}
order: {order}
---

# {name}

Fixture license body for {id}.
"""


@pytest.fixture
def fixture_registry_dir(tmp_path: Path) -> Path:
    shutil.copy(REAL_SCHEMA, tmp_path / "_schema.json")
    (tmp_path / "active.md").write_text(
        _LICENSE_TEMPLATE.format(
            id="FIXTURE-ACTIVE",
            name="Fixture Active License",
            short_name="Fixture Active",
            active=True,
            order=10,
        )
    )
    (tmp_path / "inactive.md").write_text(
        _LICENSE_TEMPLATE.format(
            id="FIXTURE-INACTIVE",
            name="Fixture Inactive License",
            short_name="Fixture Inactive",
            active=False,
            order=20,
        )
    )
    return tmp_path


@pytest.fixture
async def client(fixture_registry_dir: Path) -> AsyncIterator[AsyncClient]:
    app = create_app()
    registry = load_registry(fixture_registry_dir)
    app.dependency_overrides[get_registry] = lambda: registry

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
