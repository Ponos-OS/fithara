"""
Entrypoint for `make evals_nightly`: brings up a real Ollama server via
Testcontainers (building the pinned image in this directory if it isn't
already cached locally), points the drafting agent at it via `LLM__*` env
vars, then runs the same `src.modules.draft.evals.run` module `make evals`
runs manually — overriding whatever provider `.env` configures.

This is what actually exercises the pydantic-evals dataset against a live
model in CI: a live LLM never runs in the unit/integration suites (see
`.github/CONTRIBUTING.md`), so this script — not pytest — is the only place
Ollama gets started for evals. Never import this module from `src/`; it's CI
tooling, not application code, which is why it lives outside `src/` entirely.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import docker
import docker.errors
from testcontainers.community.ollama import OllamaContainer
from testcontainers.core.image import DockerImage


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OLLAMA_MODEL = "llama3.2:1b"
OLLAMA_IMAGE = "fithara-ollama:latest"
OLLAMA_CONTEXT = PROJECT_ROOT / "local-setup" / "ollama"


def _ensure_ollama_image_exists() -> None:
    client = docker.from_env()

    try:
        client.images.get(OLLAMA_IMAGE)
        return
    except docker.errors.ImageNotFound:
        pass

    image = DockerImage(
        path=str(OLLAMA_CONTEXT),
        tag=OLLAMA_IMAGE,
        buildargs={"OLLAMA_MODEL": OLLAMA_MODEL},
    )
    image.build()


def main() -> int:
    _ensure_ollama_image_exists()

    with OllamaContainer(image=OLLAMA_IMAGE) as container:
        env = {
            **os.environ,
            "LLM__PROVIDER": "ollama",
            "LLM__MODEL": OLLAMA_MODEL,
            "LLM__BASE_URL": f"{container.get_endpoint()}/v1",
            "LLM__API_KEY": "unused-local-ollama",
        }
        result = subprocess.run(
            [sys.executable, "-m", "src.modules.draft.evals.run"],
            cwd=PROJECT_ROOT,
            env=env,
            check=False,
        )

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
