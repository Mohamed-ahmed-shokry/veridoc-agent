"""Deterministic final verdict derivation for complete processing."""

from veridoc.processing.models import ProcessingVerdict
from veridoc.verification.models import FindingSeverity, VerificationResult

_SEVERITY_RANK: dict[FindingSeverity, int] = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}


def derive_verdict(verification: VerificationResult) -> ProcessingVerdict:
    """Return a review status without treating the absence of findings as trust."""
    findings = verification.findings
    if not findings:
        return ProcessingVerdict(
            status="clear",
            summary="No deterministic verification findings require review.",
            finding_count=0,
        )

    highest_severity = max(
        (finding.severity for finding in findings), key=_SEVERITY_RANK.__getitem__
    )
    count = len(findings)
    suffix = "finding" if count == 1 else "findings"
    verb = "requires" if count == 1 else "require"
    return ProcessingVerdict(
        status="review_required",
        summary=f"{count} deterministic verification {suffix} {verb} review.",
        finding_count=count,
        highest_severity=highest_severity,
    )
