import shutil
from pathlib import Path

import pytest

from src.registry.loader import RegistryLoadError, load_registry

REAL_SCHEMA = Path(__file__).parent.parent / "licenses" / "_schema.json"

VALID_FRONTMATTER = """---
id: {id}
name: Example License
shortName: Example
version: "1.0"
category: creative_commons
officialUrl: https://example.com/license
summary: An example license.
permissions: [share]
limitations: []
conditions: [attribution]
active: {active}
order: 10
---

# Example License

Body text.
"""


def _write_license(directory: Path, filename: str, license_id: str, active: bool = True) -> None:
    (directory / filename).write_text(VALID_FRONTMATTER.format(id=license_id, active=active))


@pytest.fixture
def registry_dir(tmp_path: Path) -> Path:
    shutil.copy(REAL_SCHEMA, tmp_path / "_schema.json")
    return tmp_path


def test_load_registry_loads_valid_fixture_directory(registry_dir: Path) -> None:
    _write_license(registry_dir, "one.md", "EXAMPLE-ONE")
    _write_license(registry_dir, "two.md", "EXAMPLE-TWO")

    licenses = load_registry(registry_dir)

    assert len(licenses) == 2
    assert {license_.id for license_ in licenses} == {"EXAMPLE-ONE", "EXAMPLE-TWO"}
    assert licenses[0].short_name == "Example"
    assert licenses[0].official_url == "https://example.com/license"
    assert licenses[0].permissions == ["share"]


def test_load_registry_raises_on_malformed_frontmatter(registry_dir: Path) -> None:
    (registry_dir / "bad.md").write_text("---\nid: BAD\nname: Missing required fields\n---\nBody.\n")

    with pytest.raises(RegistryLoadError):
        load_registry(registry_dir)


def test_load_registry_raises_on_duplicate_ids(registry_dir: Path) -> None:
    _write_license(registry_dir, "one.md", "DUPLICATE-ID")
    _write_license(registry_dir, "two.md", "DUPLICATE-ID")

    with pytest.raises(RegistryLoadError):
        load_registry(registry_dir)


def test_load_registry_loads_inactive_license_as_retrievable(registry_dir: Path) -> None:
    _write_license(registry_dir, "inactive.md", "INACTIVE-ONE", active=False)

    licenses = load_registry(registry_dir)

    assert len(licenses) == 1
    assert licenses[0].active is False
