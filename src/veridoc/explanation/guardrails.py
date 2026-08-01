"""Validation that prevents provider drafts from overriding verified evidence."""

from __future__ import annotations

import re

from veridoc.explanation.protocol import ExplanationDraftResult, ExplanationRequest

_DIGIT = re.compile(r"\d")
_NUMBER_WORD = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
    r"hundred|thousand|million|billion|dozen)\b",
    re.IGNORECASE,
)
_COMPARATIVE_CLAIM = re.compile(
    r"\b(?:above|below|greater|less|higher|lower|matches?|mismatches?|"
    r"same|different|equal|unequal|not|no)\b",
    re.IGNORECASE,
)


def validated_narratives(
    request: ExplanationRequest, drafts: ExplanationDraftResult
) -> list[str] | None:
    """Return safe guidance ordered by finding index, or reject every draft."""
    if len(drafts.drafts) != len(request.findings):
        return None

    narratives: list[str] = []
    expected_indexes = set(range(len(request.findings)))
    received_indexes = {draft.finding_index for draft in drafts.drafts}
    if received_indexes != expected_indexes:
        return None

    for draft in sorted(drafts.drafts, key=lambda item: item.finding_index):
        narrative = " ".join(draft.narrative.split())
        if not narrative or _contains_untrusted_claim(narrative):
            return None
        narratives.append(narrative)
    return narratives


def _contains_untrusted_claim(narrative: str) -> bool:
    return bool(
        _DIGIT.search(narrative)
        or _NUMBER_WORD.search(narrative)
        or _COMPARATIVE_CLAIM.search(narrative)
    )
