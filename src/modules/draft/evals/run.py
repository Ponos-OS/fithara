"""
Entrypoint for `make evals`: runs the golden dataset (dataset.yaml) against
the live drafting agent and writes report.json.

Requires a real LLM__* provider configured (see `src.utils.config.Llm`).
Never runs in CI and is never asserted on by any pytest suite — see the
Testing Philosophy in `.github/CONTRIBUTING.md`. Judged manually; if a
regression is deliberate, run `make evals_baseline` to accept report.json
as the new baseline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_evals import Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from src.modules.draft import DraftRequest, DraftResponse, run_draft_agent


_DATASET_PATH = Path(__file__).parent / "dataset.yaml"
_REPORT_PATH = Path(__file__).parent / "report.json"


@dataclass
class MatchesExpectedShape(Evaluator):
    """
    Structural check only, per the project's testing philosophy: never grades
    wording. Compares `draftChanged` and (when given) `draft.source.type`
    against the case's expected metadata.
    """

    def evaluate(
        self, ctx: EvaluatorContext[dict[str, Any], DraftResponse, dict[str, Any]]
    ) -> bool:
        metadata = ctx.metadata or {}
        response = ctx.output

        expected_changed = metadata.get("expected_draft_changed")
        if expected_changed is not None and response.draft_changed != expected_changed:
            return False

        expected_source_type = metadata.get("expected_source_type")
        if expected_source_type is not None and (
            response.draft is None or response.draft.source.type != expected_source_type
        ):
            return False

        return bool(response.disclaimers)


async def _run_case(inputs: dict[str, Any]) -> DraftResponse:
    return await run_draft_agent(DraftRequest.model_validate(inputs))


def main() -> None:
    dataset = Dataset[dict[str, Any], DraftResponse, dict[str, Any]].from_file(_DATASET_PATH)
    dataset.evaluators.append(MatchesExpectedShape())

    report = dataset.evaluate_sync(_run_case)
    report.print()

    summary = {
        case.name: {name: result.value for name, result in case.assertions.items()}
        for case in report.cases
    }
    _REPORT_PATH.write_text(json.dumps(summary, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()
