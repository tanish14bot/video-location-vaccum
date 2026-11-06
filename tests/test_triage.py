from __future__ import annotations

from video_location_vaccum.config import TriageConfig, TriageMode
from video_location_vaccum.triage.rubric import (
    EvidenceItem,
    EvidenceKind,
    Gate,
    GateResult,
    PrecisionBucket,
    TriageAssessment,
    UseMode,
    decide,
)


def _strong(city: bool = True) -> TriageAssessment:
    ev = [
        EvidenceItem(EvidenceKind.UNIQUE_LANDMARK, 1.0),
        EvidenceItem(EvidenceKind.MICRO_CUE, 1.0),
        EvidenceItem(EvidenceKind.REFERENCE_IMAGERY, 1.0),
        EvidenceItem(EvidenceKind.TERRAIN, 1.0),
        EvidenceItem(EvidenceKind.CHRONOLOCATION, 1.0),
        EvidenceItem(EvidenceKind.INDEPENDENT_CORROBORATION, 1.0),
        EvidenceItem(EvidenceKind.SOURCE_RELIABILITY, 1.0),
        EvidenceItem(EvidenceKind.DISCONFIRMATION, 1.0),
    ]
    gates = {
        Gate.PROVENANCE: GateResult.PASS,
        Gate.AUTHENTICITY: GateResult.PASS,
        Gate.UNIQUENESS: GateResult.PASS,
        Gate.TEMPORAL: GateResult.PASS,
        Gate.NEGATIVE_CONTROL: GateResult.PASS,
        Gate.PRECISION_DISCIPLINE: GateResult.PASS,
        Gate.INTEGRITY: GateResult.PASS,
    }
    return TriageAssessment(
        claim_place="Eiffel Tower, Paris",
        precision=PrecisionBucket.CITY if city else PrecisionBucket.POINT,
        requested_precision=PrecisionBucket.CITY,
        mode=UseMode.EXPLORATION,
        evidence=ev,
        gates=gates,
        has_cross_source=True,
    )


def test_strong_visual_case_skips_acoustics() -> None:
    decision = decide(_strong(), TriageConfig())
    assert decision.action == "skip"
    assert decision.confidence >= 0.9


def test_force_pipeline_overrides_obvious_location() -> None:
    decision = decide(_strong(), TriageConfig(force_pipeline=True))
    assert decision.action == "pipeline"
    assert decision.forced_by_user


def test_ignore_visuals_forces_pipeline() -> None:
    decision = decide(_strong(), TriageConfig(ignore_visuals=True))
    assert decision.action == "pipeline"


def test_forensic_mode_forces_pipeline() -> None:
    decision = decide(_strong(), TriageConfig(mode=TriageMode.FORENSIC))
    assert decision.action == "pipeline"


def test_authenticity_failure_caps_to_zero() -> None:
    assessment = _strong()
    assessment.gates[Gate.AUTHENTICITY] = GateResult.FAIL
    decision = decide(assessment, TriageConfig())
    assert decision.action == "pipeline"
    assert decision.confidence == 0.0


def test_precision_mismatch_forces_pipeline() -> None:
    assessment = _strong()
    assessment.precision = PrecisionBucket.CITY
    assessment.requested_precision = PrecisionBucket.STREET
    decision = decide(assessment, TriageConfig())
    assert decision.action == "pipeline"


def test_forced_skip_is_refused_in_legal_mode() -> None:
    assessment = _strong()
    assessment.mode = UseMode.LEGAL
    decision = decide(assessment, TriageConfig(), force_skip=True)
    assert decision.action == "pipeline"
    assert decision.forced_by_user


def test_landmark_suffices_at_city_but_not_street() -> None:
    assessment = _strong()
    # Remove the supporting items; the landmark plus dated reference must carry a city claim.
    assessment.evidence = [
        EvidenceItem(EvidenceKind.UNIQUE_LANDMARK, 1.0),
        EvidenceItem(EvidenceKind.REFERENCE_IMAGERY, 0.9),
    ]
    assert decide(assessment, TriageConfig()).action == "skip"

    assessment.requested_precision = PrecisionBucket.STREET
    assert decide(assessment, TriageConfig()).action == "pipeline"
