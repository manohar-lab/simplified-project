"""Choose the best available service using weighted QoS scoring, strict SLA constraints, and hysteresis anti-flapping.

This module implements the complete decision-making step of the project:
    1. Filters candidate services by requested category (e.g. "Compute", "Storage").
    2. Strictly excludes unavailable services (outages).
    3. Strictly validates each candidate against active SLA thresholds (latency,
       availability, reliability). Candidates violating any SLA are excluded.
    4. Evaluates each eligible candidate's QoS score using QoSEvaluator.
    5. Ranks eligible services by descending QoS score (ties broken by service_id).
    6. Applies intelligent hysteresis and anti-flapping decision rules:
       - Initial Selection: Highest-scoring SLA-compliant service.
       - Emergency Outage: Immediate reselection if active service is UNAVAILABLE.
       - Emergency SLA Violation: Immediate reselection if active service violates SLA.
       - Eligible Current Service: Switch ONLY if alternative improvement > hysteresis
         threshold and cooldown is satisfied; otherwise retain current service.
       - Recovery: Recovered service is reconsidered but only switched to if normal
         hysteresis rules justify switching (prevents flapping/bounce-back).
    7. Generates human-readable, transparent decision explanations.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.qos_evaluator import MetricScores, QoSEvaluator
from src.service_registry import CloudService
from src.sla_config import SLAConfig, get_default_sla_config, validate_service_sla
from src.hysteresis_config import HysteresisConfig, DEFAULT_HYSTERESIS_CONFIG, check_cooldown_active


@dataclass
class RecommendationResult:
    """Encapsulates the full output of a recommendation decision.

    Fields:
        category: The service category evaluated.
        selected_service: The top-ranked CloudService, or None if no eligible service exists.
        selected_scores: The MetricScores of the selected service, or None.
        ranked_eligible: List of (CloudService, MetricScores) tuples for all eligible
                         services, sorted by descending QoS score then ascending service_id.
        excluded_services: List of (CloudService, reason_string) for excluded services.
        selection_reason: A human-readable string explaining why the service was chosen.
        has_eligible_service: True if at least one compliant service exists in the category.
        status_message: Summary status message for the dashboard.
        sla_config: The SLAConfig applied during eligibility evaluation.
        status_code: High-level status code (e.g. "RECOMMENDED", "NO_SLA_COMPLIANT_SERVICE").
        hysteresis_config: The HysteresisConfig applied during switching evaluation.
        decision_type: Type of decision ("INITIAL_SELECTION", "RETAINED", "SWITCHED",
                       "EMERGENCY_OUTAGE", "EMERGENCY_SLA_VIOLATION", "NO_ELIGIBLE_SERVICE").
        decision_reason: Concise statement explaining why the service was retained or switched.
        best_alternative: The best alternative candidate service, or None.
        best_alternative_score: MetricScores of the best alternative, or None.
        qos_improvement: Composite score advantage of the best alternative over current (0.0 if retained/none).
        cooldown_active: True if switching was blocked by an active cooldown period.
    """
    category: str
    selected_service: Optional[CloudService]
    selected_scores: Optional[MetricScores]
    ranked_eligible: List[Tuple[CloudService, MetricScores]]
    excluded_services: List[Tuple[CloudService, str]]
    selection_reason: str
    has_eligible_service: bool
    status_message: str
    sla_config: Optional[SLAConfig] = None
    status_code: str = "RECOMMENDED"
    hysteresis_config: Optional[HysteresisConfig] = None
    decision_type: str = "INITIAL_SELECTION"
    decision_reason: str = ""
    best_alternative: Optional[CloudService] = None
    best_alternative_score: Optional[MetricScores] = None
    qos_improvement: float = 0.0
    cooldown_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert the recommendation result to a summary dictionary for inspection or serialization."""
        service, scores = self.selected_service, self.selected_scores
        alt, alt_scores = self.best_alternative, self.best_alternative_score
        return {
            "category": self.category,
            "status_code": self.status_code,
            "decision_type": self.decision_type,
            "decision_reason": self.decision_reason,
            "selected_service_id": service.service_id if service else None,
            "selected_service_name": service.name if service else None,
            "qos_score": scores.qos_score if scores else None,
            "best_alternative_id": alt.service_id if alt else None,
            "best_alternative_name": alt.name if alt else None,
            "best_alternative_qos": alt_scores.qos_score if alt_scores else None,
            "qos_improvement": self.qos_improvement,
            "cooldown_active": self.cooldown_active,
            "selection_reason": self.selection_reason,
            "has_eligible_service": self.has_eligible_service,
            "status_message": self.status_message,
            "num_eligible": len(self.ranked_eligible),
            "num_excluded": len(self.excluded_services),
            "sla_config": self.sla_config.to_dict() if self.sla_config else None,
            "hysteresis_config": self.hysteresis_config.to_dict() if self.hysteresis_config else None,
        }


class RecommendationEngine:
    """Rank category-matched services and explain selections using SLA constraints and hysteresis."""

    def __init__(self, evaluator: QoSEvaluator):
        """Initialize the engine with a configured QoS evaluator.

        Args:
            evaluator: QoSEvaluator instance used to compute normalized scores for services.
        """
        self.evaluator = evaluator

    def recommend(
        self,
        services: List[CloudService],
        category: str,
        weights: Optional[Dict[str, float]] = None,
        previously_selected_id: Optional[str] = None,
        sla_config: Optional[SLAConfig] = None,
        hysteresis_config: Optional[HysteresisConfig] = None,
        current_step: Optional[int] = None,
        last_switch_step: Optional[int] = None,
        current_time: Optional[float] = None,
        last_switch_time: Optional[float] = None,
    ) -> RecommendationResult:
        """Select the optimal SLA-compliant service applying hysteresis anti-flapping rules.

        Decision Rules:
            Rule A (Initial Selection):
                If previously_selected_id is None, select highest-scoring SLA-compliant candidate.
            Rule B (Eligible Current Service):
                If current service remains operational and SLA-compliant, compare against best
                alternative. Switch only if alternative improvement > hysteresis_threshold and
                cooldown is satisfied; otherwise retain current service.
            Rule C (Emergency Outage):
                If current service becomes UNAVAILABLE, immediately switch to best eligible candidate.
            Rule D (Emergency SLA Violation):
                If current service violates SLA constraint, immediately switch to best eligible candidate.
            Rule E (No Eligible Service):
                If no candidate is SLA-compliant, return None with NO_SLA_COMPLIANT_SERVICE.
            Rule F (Recovery):
                Recovered services are reconsidered as candidates under normal Rule B switching rules.

        Args:
            services: Full list of CloudService candidates.
            category: Target category (e.g. "Compute", "Storage").
            weights: Optional custom metric weights for QoS scoring.
            previously_selected_id: Service ID previously recommended, if any.
            sla_config: Configurable SLA constraints. Defaults to category default.
            hysteresis_config: Configurable hysteresis delta and cooldown. Defaults to DEFAULT_HYSTERESIS_CONFIG.
            current_step: Optional current simulation step counter.
            last_switch_step: Optional step counter when last service switch occurred.
            current_time: Optional current wall-clock epoch timestamp.
            last_switch_time: Optional timestamp when last service switch occurred.

        Returns:
            RecommendationResult encapsulating decision, scores, rankings, and explanations.
        """
        effective_sla = sla_config if sla_config is not None else get_default_sla_config(category)
        effective_hysteresis = hysteresis_config if hysteresis_config is not None else DEFAULT_HYSTERESIS_CONFIG

        # --- Stage 1: Category Filtering ---
        candidates = [s for s in services if s.category == category]
        if not candidates:
            return RecommendationResult(
                category=category,
                selected_service=None,
                selected_scores=None,
                ranked_eligible=[],
                excluded_services=[],
                selection_reason=f"No services found registered under category '{category}'.",
                has_eligible_service=False,
                status_message=f"Category '{category}' has no candidate services registered.",
                sla_config=effective_sla,
                hysteresis_config=effective_hysteresis,
                status_code="NO_CANDIDATES",
                decision_type="NO_ELIGIBLE_SERVICE",
                decision_reason="No services registered in category.",
            )

        # --- Stage 2: Availability & SLA Filtering ---
        excluded: List[Tuple[CloudService, str]] = []
        available_candidates: List[CloudService] = []

        # 2a. Operational status filtering (fail-safe outage exclusion)
        for s in candidates:
            if s.operational_status == "UNAVAILABLE":
                excluded.append((s, "Service is marked UNAVAILABLE (simulated outage/down)."))
            else:
                available_candidates.append(s)

        # 2b. Strict SLA constraint evaluation on available candidates
        eligible: List[CloudService] = []
        for s in available_candidates:
            violations = validate_service_sla(s, effective_sla)
            if violations:
                excluded.append((s, f"Excluded: {'; '.join(violations)}"))
            else:
                eligible.append(s)

        # --- Stage 3: No Eligible Service Handling (Rule E) ---
        if not eligible:
            if not available_candidates:
                status_msg = f"No SLA-Compliant Service Available. All {len(candidates)} service(s) in category '{category}' are currently UNAVAILABLE."
                reason = "No eligible candidate service available. Every candidate is in an outage/unavailable state."
            else:
                status_msg = f"No SLA-Compliant Service Available. All {len(candidates)} candidate service(s) in category '{category}' are unavailable or violate SLA constraints."
                reason = f"No SLA-Compliant Service Available. All {len(available_candidates)} available candidate(s) violate configured SLA thresholds."

            return RecommendationResult(
                category=category,
                selected_service=None,
                selected_scores=None,
                ranked_eligible=[],
                excluded_services=excluded,
                selection_reason=reason,
                has_eligible_service=False,
                status_message=status_msg,
                sla_config=effective_sla,
                hysteresis_config=effective_hysteresis,
                status_code="NO_SLA_COMPLIANT_SERVICE",
                decision_type="NO_ELIGIBLE_SERVICE",
                decision_reason="No candidate service satisfies all operational and SLA constraints.",
            )

        # --- Stage 4: Evaluate and Rank ELIGIBLE Services Only ---
        ranked = [(s, self.evaluator.evaluate_service(s, weights)) for s in eligible]
        # Sort by descending QoS score; ties broken by ascending service_id (deterministic)
        ranked.sort(key=lambda pair: (-pair[1].qos_score, pair[0].service_id))
        top_candidate, top_score = ranked[0]

        # --- Stage 5: Switching & Hysteresis Decision Logic ---
        selected_service: CloudService
        selected_scores: MetricScores
        decision_type: str
        decision_reason: str
        best_alternative: Optional[CloudService] = None
        best_alternative_score: Optional[MetricScores] = None
        qos_improvement: float = 0.0
        cooldown_active: bool = False

        if previously_selected_id is None:
            # Rule A: Initial Selection
            selected_service = top_candidate
            selected_scores = top_score
            decision_type = "INITIAL_SELECTION"
            best_alternative = ranked[1][0] if len(ranked) > 1 else None
            best_alternative_score = ranked[1][1] if len(ranked) > 1 else None
            qos_improvement = round(top_score.qos_score - (best_alternative_score.qos_score if best_alternative_score else 0.0), 4)
            decision_reason = f"Initial selection: '{top_candidate.name}' ({top_candidate.service_id}) selected with highest aggregate QoS score ({top_score.qos_score:.4f})."

        else:
            # Look up previously selected service within current candidates
            prior_service = next((s for s in candidates if s.service_id == previously_selected_id), None)

            if prior_service is None:
                # Prior service not registered in category -> Initial selection
                selected_service = top_candidate
                selected_scores = top_score
                decision_type = "INITIAL_SELECTION"
                best_alternative = ranked[1][0] if len(ranked) > 1 else None
                best_alternative_score = ranked[1][1] if len(ranked) > 1 else None
                qos_improvement = round(top_score.qos_score - (best_alternative_score.qos_score if best_alternative_score else 0.0), 4)
                decision_reason = f"Initial selection: '{top_candidate.name}' ({top_candidate.service_id}) selected."

            elif prior_service.operational_status == "UNAVAILABLE":
                # Rule C: Emergency Outage (Bypass hysteresis and cooldown)
                selected_service = top_candidate
                selected_scores = top_score
                decision_type = "EMERGENCY_OUTAGE"
                best_alternative = ranked[1][0] if len(ranked) > 1 else None
                best_alternative_score = ranked[1][1] if len(ranked) > 1 else None
                qos_improvement = round(top_score.qos_score - (best_alternative_score.qos_score if best_alternative_score else 0.0), 4)
                decision_reason = f"Emergency reselection: current service became UNAVAILABLE. Switched to '{top_candidate.name}' ({top_candidate.service_id})."

            elif (prior_violations := validate_service_sla(prior_service, effective_sla)):
                # Rule D: Emergency SLA Violation (Bypass hysteresis and cooldown)
                selected_service = top_candidate
                selected_scores = top_score
                decision_type = "EMERGENCY_SLA_VIOLATION"
                best_alternative = ranked[1][0] if len(ranked) > 1 else None
                best_alternative_score = ranked[1][1] if len(ranked) > 1 else None
                qos_improvement = round(top_score.qos_score - (best_alternative_score.qos_score if best_alternative_score else 0.0), 4)
                violations_str = "; ".join(prior_violations)
                decision_reason = f"Emergency reselection: current service violated an SLA constraint ({violations_str}). Switched to '{top_candidate.name}' ({top_candidate.service_id})."

            else:
                # Rule B: Current Service Remains Eligible!
                # Prior service is operational and SLA-compliant
                current_scores = next(sc for s, sc in ranked if s.service_id == prior_service.service_id)

                if top_candidate.service_id == prior_service.service_id:
                    # Current service remains optimal (#1)
                    selected_service = prior_service
                    selected_scores = current_scores
                    decision_type = "RETAINED"
                    best_alternative = ranked[1][0] if len(ranked) > 1 else None
                    best_alternative_score = ranked[1][1] if len(ranked) > 1 else None
                    qos_improvement = 0.0
                    decision_reason = f"Service retained: '{prior_service.name}' ({prior_service.service_id}) remains the optimal candidate."

                else:
                    # An alternative candidate has a higher (or equal tie-break) score
                    best_alternative = top_candidate
                    best_alternative_score = top_score
                    # Calculate improvement offered by the alternative over current active service
                    qos_improvement = round(top_score.qos_score - current_scores.qos_score, 4)

                    # Check cooldown requirement
                    is_cd, cd_msg = check_cooldown_active(
                        effective_hysteresis,
                        current_step=current_step,
                        last_switch_step=last_switch_step,
                        current_time=current_time,
                        last_switch_time=last_switch_time,
                    )

                    if is_cd:
                        # Cooldown blocks performance-driven switching
                        selected_service = prior_service
                        selected_scores = current_scores
                        decision_type = "RETAINED"
                        cooldown_active = True
                        decision_reason = f"Service retained: switching blocked by active cooldown ({cd_msg})."

                    elif qos_improvement <= effective_hysteresis.min_qos_delta:
                        # Improvement does not exceed hysteresis threshold -> Retain current service
                        selected_service = prior_service
                        selected_scores = current_scores
                        decision_type = "RETAINED"
                        cooldown_active = False
                        decision_reason = (
                            f"Service retained: alternative improvement ({qos_improvement:.4f}) is below "
                            f"the hysteresis threshold ({effective_hysteresis.min_qos_delta:.4f})."
                        )

                    else:
                        # Improvement exceeds hysteresis threshold and cooldown satisfied -> Switch!
                        selected_service = top_candidate
                        selected_scores = top_score
                        decision_type = "SWITCHED"
                        cooldown_active = False
                        decision_reason = (
                            f"Service switched: alternative QoS improvement ({qos_improvement:.4f}) "
                            f"exceeds the configured threshold ({effective_hysteresis.min_qos_delta:.4f})."
                        )

        # --- Stage 6: Build Full Human-Readable Explanation ---
        reasons = [
            f"Selected '{selected_service.name}' ({selected_service.service_id}) with aggregate QoS score of {selected_scores.qos_score:.4f}.",
            f"Latency: {selected_service.latency:.1f}ms (score: {selected_scores.latency_score:.2f}) | "
            f"Cost: ${selected_service.cost:.3f} (score: {selected_scores.cost_score:.2f}) | "
            f"Availability: {selected_service.availability:.2f}% (score: {selected_scores.availability_score:.2f}) | "
            f"Reliability: {selected_service.reliability:.2f}% (score: {selected_scores.reliability_score:.2f}).",
        ]

        if previously_selected_id is not None:
            reasons.append(f"Reselection trigger: {decision_reason}")

        return RecommendationResult(
            category=category,
            selected_service=selected_service,
            selected_scores=selected_scores,
            ranked_eligible=ranked,
            excluded_services=excluded,
            selection_reason=" ".join(reasons),
            has_eligible_service=True,
            status_message=f"Successfully selected '{selected_service.name}' ({selected_service.service_id}) out of {len(eligible)} eligible services.",
            sla_config=effective_sla,
            hysteresis_config=effective_hysteresis,
            status_code="RECOMMENDED",
            decision_type=decision_type,
            decision_reason=decision_reason,
            best_alternative=best_alternative,
            best_alternative_score=best_alternative_score,
            qos_improvement=qos_improvement,
            cooldown_active=cooldown_active,
        )
