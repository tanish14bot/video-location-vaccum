"""Evidence rubric and the skip/run decision.

The score is bound to a *precision bucket*: "identified" at country scale and at
building scale are different claims. Gates are caps, not weights, so a strong
landmark cannot paper over a broken provenance chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..config import TriageConfig, TriageMode


class PrecisionBucket(str, Enum):
    COUNTRY = "country"
    REGION = "region"
    CITY = "city"
    STREET = "street"
    POINT = "point"


_RANK = {
    PrecisionBucket.COUNTRY: 0,
    PrecisionBucket.REGION: 1,
    PrecisionBucket.CITY: 2,
    PrecisionBucket.STREET: 3,
    PrecisionBucket.POINT: 4,
}


class UseMode(str, Enum):
    EXPLORATION = "exploration"
    PUBLICATION = "publication"
    FORENSIC = "forensic"
    LEGAL = "legal"
    SAFETY = "safety"


class Gate(str, Enum):
    PROVENANCE = "provenance"
    AUTHENTICITY = "authenticity"
    UNIQUENESS = "uniqueness"
    TEMPORAL = "temporal"
    NEGATIVE_CONTROL = "negative_control"
    PRECISION_DISCIPLINE = "precision_discipline"
    INTEGRITY = "integrity"


class GateResult(str, Enum):
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"
    UNKNOWN = "unknown"


class EvidenceKind(str, Enum):
    UNIQUE_LANDMARK = "unique_landmark"
    MICRO_CUE = "micro_cue"
    REFERENCE_IMAGERY = "reference_imagery"
    TERRAIN = "terrain"
    CHRONOLOCATION = "chronolocation"
    INDEPENDENT_CORROBORATION = "independent_corroboration"
    SOURCE_RELIABILITY = "source_reliability"
    DISCONFIRMATION = "disconfirmation"
    METADATA_GPS = "metadata_gps"


_WEIGHTS: dict[EvidenceKind, float] = {
    EvidenceKind.UNIQUE_LANDMARK: 0.18,
    EvidenceKind.MICRO_CUE: 0.14,
    EvidenceKind.REFERENCE_IMAGERY: 0.14,
    EvidenceKind.TERRAIN: 0.10,
    EvidenceKind.CHRONOLOCATION: 0.12,
    EvidenceKind.INDEPENDENT_CORROBORATION: 0.16,
    EvidenceKind.SOURCE_RELIABILITY: 0.08,
    EvidenceKind.DISCONFIRMATION: 0.08,
    EvidenceKind.METADATA_GPS: 0.10,
}

_GATE_CAPS: dict[tuple[Gate, GateResult], float] = {
    (Gate.PROVENANCE, GateResult.FAIL): 0.45,
    (Gate.PROVENANCE, GateResult.PARTIAL): 0.75,
    (Gate.PROVENANCE, GateResult.UNKNOWN): 0.75,
    (Gate.AUTHENTICITY, GateResult.FAIL): 0.00,
    (Gate.AUTHENTICITY, GateResult.PARTIAL): 0.35,
    (Gate.AUTHENTICITY, GateResult.UNKNOWN): 0.35,
    (Gate.UNIQUENESS, GateResult.FAIL): 0.50,
    (Gate.UNIQUENESS, GateResult.UNKNOWN): 0.50,
    (Gate.TEMPORAL, GateResult.FAIL): 0.40,
    (Gate.TEMPORAL, GateResult.PARTIAL): 0.80,
    (Gate.TEMPORAL, GateResult.UNKNOWN): 0.80,
    (Gate.NEGATIVE_CONTROL, GateResult.FAIL): 0.60,
    (Gate.NEGATIVE_CONTROL, GateResult.UNKNOWN): 0.60,
    (Gate.PRECISION_DISCIPLINE, GateResult.FAIL): 0.55,
    (Gate.PRECISION_DISCIPLINE, GateResult.UNKNOWN): 0.55,
    (Gate.INTEGRITY, GateResult.FAIL): 0.60,
    (Gate.INTEGRITY, GateResult.PARTIAL): 0.60,
    (Gate.INTEGRITY, GateResult.UNKNOWN): 0.60,
}


@dataclass
class EvidenceItem:
    kind: EvidenceKind
    score: float = 0.0  # 0..1 quality within this kind
    note: str = ""
    independent: bool = True

    @property
    def weight(self) -> float:
        return _WEIGHTS[self.kind]


@dataclass
class TriageAssessment:
    claim_place: str
    precision: PrecisionBucket
    mode: UseMode = UseMode.EXPLORATION
    requested_precision: PrecisionBucket = PrecisionBucket.CITY
    evidence: list[EvidenceItem] = field(default_factory=list)
    gates: dict[Gate, GateResult] = field(default_factory=dict)
    candidates_examined: int = 0
    target_is_private_individual: bool = False
    authenticity_disputed: bool = False
    ai_geolocator_sole_basis: bool = False
    reference_imagery_undated: bool = False
    landmark_replicas_not_excluded: bool = False
    has_cross_source: bool = False
    rubric_version: str = "1.0"

    def raw_score(self) -> float:
        total = 0.0
        for item in self.evidence:
            total += item.weight * max(0.0, min(1.0, item.score))
        return min(1.0, total)

    def confidence(self, *, legal_mode: bool = False) -> tuple[float, list[str]]:
        score = self.raw_score()
        binding: list[str] = []
        cap = 1.0
        for gate, result in self.gates.items():
            gate_cap = _GATE_CAPS.get((gate, result))
            if (
                gate is Gate.INTEGRITY
                and legal_mode
                and result in {GateResult.FAIL, GateResult.PARTIAL, GateResult.UNKNOWN}
            ):
                gate_cap = 0.0
            if gate_cap is not None and gate_cap < cap:
                cap = gate_cap
                binding.append(f"{gate.value}:{result.value}")

        if self.ai_geolocator_sole_basis and cap > 0.35:
            cap = 0.35
            binding.append("ai-sole-basis")
        if self.landmark_replicas_not_excluded and cap > 0.50:
            cap = 0.50
            binding.append("replicas-not-excluded")
        if self.reference_imagery_undated and cap > 0.70:
            cap = 0.70
            binding.append("reference-undated")
        if not self.has_cross_source and cap > 0.80:
            cap = 0.80
            binding.append("no-cross-source")

        score = min(score, cap)
        if self._landmark_sufficient_at_requested_precision():
            score = max(score, min(0.92, cap))
        return float(score), binding

    def _landmark_sufficient_at_requested_precision(self) -> bool:
        """A unique, dated, replica-excluded landmark can settle a coarse query.

        This is the Eiffel Tower rule: at country/region/city precision, one
        unambiguous landmark with dated reference imagery is enough. It never
        applies to street/point precision, and it is disabled by any provenance,
        authenticity, uniqueness, or replica failure.
        """
        if _RANK[self.requested_precision] > _RANK[PrecisionBucket.CITY]:
            return False
        if self.gates.get(Gate.UNIQUENESS) is not GateResult.PASS:
            return False
        if self.gates.get(Gate.AUTHENTICITY) in {GateResult.FAIL, GateResult.PARTIAL}:
            return False
        if self.gates.get(Gate.PROVENANCE) is GateResult.FAIL:
            return False
        if self.landmark_replicas_not_excluded:
            return False
        landmark = [e for e in self.evidence if e.kind is EvidenceKind.UNIQUE_LANDMARK]
        reference = [e for e in self.evidence if e.kind is EvidenceKind.REFERENCE_IMAGERY]
        return bool(landmark and landmark[0].score >= 0.90 and reference and reference[0].score >= 0.80)

    def meets_precision(self) -> bool:
        return _RANK[self.precision] >= _RANK[self.requested_precision]


@dataclass
class Decision:
    action: str  # skip | probe | pipeline
    confidence: float
    binding_caps: list[str]
    reasons: list[str]
    forced_by_user: bool = False
    allowed_skip: bool = True
    calibrated: bool = False


_FORCING_MODES = {UseMode.PUBLICATION, UseMode.FORENSIC, UseMode.LEGAL, UseMode.SAFETY}


def decide(
    assessment: TriageAssessment,
    cfg: TriageConfig,
    *,
    force_skip: bool = False,
) -> Decision:
    reasons: list[str] = []
    legal = assessment.mode is UseMode.LEGAL or cfg.mode is TriageMode.FORENSIC
    confidence, caps = assessment.confidence(legal_mode=legal)

    if cfg.force_pipeline or cfg.mode in {TriageMode.DOPPLER, TriageMode.FORENSIC}:
        reasons.append("user/config forced the acoustic pipeline")
        return Decision("pipeline", confidence, caps, reasons, forced_by_user=True, calibrated=False)
    if cfg.ignore_visuals:
        reasons.append("user asked to ignore visual evidence")
        return Decision("pipeline", confidence, caps, reasons, forced_by_user=True, calibrated=False)
    if force_skip and legal:
        reasons.append("a forced skip is not permitted in legal/forensic use")
        return Decision("pipeline", confidence, caps, reasons, forced_by_user=True, calibrated=False)
    if assessment.mode in _FORCING_MODES:
        reasons.append(f"use mode '{assessment.mode.value}' requires independent verification")
        return Decision("pipeline", confidence, caps, reasons, calibrated=False)
    if assessment.authenticity_disputed:
        reasons.append("authenticity is disputed; visual identification cannot settle it")
        return Decision("pipeline", confidence, caps, reasons, calibrated=False)
    if assessment.target_is_private_individual:
        reasons.append("private-individual target forces the full pipeline and a restricted result")
        return Decision("pipeline", confidence, caps, reasons, calibrated=False)
    if not assessment.meets_precision():
        reasons.append(
            f"evidence supports {assessment.precision.value}, "
            f"requested {assessment.requested_precision.value}"
        )
        return Decision("pipeline", confidence, caps, reasons, calibrated=False)

    if force_skip:
        if legal:
            reasons.append("a forced skip is not permitted in legal/forensic use")
            return Decision("pipeline", confidence, caps, reasons, forced_by_user=True, calibrated=False)
        reasons.append("user forced a skip; result is labelled unverified and capped at 0.75")
        return Decision(
            "skip",
            min(confidence, 0.75),
            [*caps, "forced-skip"],
            reasons,
            forced_by_user=True,
            allowed_skip=False,
            calibrated=False,
        )

    if confidence >= cfg.min_confidence:
        reasons.append(
            f"confidence {confidence:.2f} >= {cfg.min_confidence:.2f} "
            f"at {assessment.precision.value} precision"
        )
        return Decision("skip", confidence, caps, reasons, calibrated=False)
    if confidence >= 0.75:
        reasons.append(f"confidence {confidence:.2f} in the probe band")
        return Decision("probe", confidence, caps, reasons, calibrated=False)
    reasons.append(f"confidence {confidence:.2f} below the probe threshold")
    return Decision("pipeline", confidence, caps, reasons, calibrated=False)
