"""Customer-level reasoning for RetainFlow agent responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class CustomerReasoning:
    """Structured reasoning prepared for the API and frontend."""

    answer: str
    metadata: dict[str, Any]


class ReasoningOrchestrator:
    """Turn model outputs and SHAP context into a business explanation."""

    def explain_customer_risk(
        self,
        *,
        customer_id: str,
        profile: pd.DataFrame,
        shap_summary: pd.DataFrame | None = None,
    ) -> CustomerReasoning:
        if profile.empty:
            return CustomerReasoning(
                answer=f"Aucun profil client disponible pour {customer_id}.",
                metadata={
                    "goal": "explain_customer_churn",
                    "prediction": None,
                    "signals": [],
                    "shap_drivers": [],
                    "recommended_action": None,
                },
            )

        row = profile.iloc[0]
        prediction = self._prediction(row)
        signals = self._customer_signals(row)
        shap_drivers = self._shap_drivers(shap_summary, row)
        action = self._recommended_action(row)

        signal_text = "; ".join(signal["label"] for signal in signals[:4])
        driver_text = "; ".join(driver["label"] for driver in shap_drivers[:3])
        answer = (
            f"{customer_id} ne doit pas etre interprete comme un churn certain: "
            f"le modele estime une probabilite de churn de {prediction['probability_label']} "
            f"({prediction['probability_interpretation']}). "
            f"Les signaux client les plus importants sont: {signal_text or 'aucun signal client prioritaire disponible'}. "
            f"Le contexte SHAP global indique que le modele est surtout influence par: "
            f"{driver_text or 'aucun driver SHAP disponible'}. "
            f"Action recommandee: {action}."
        )

        return CustomerReasoning(
            answer=answer,
            metadata={
                "goal": "explain_customer_churn",
                "prediction": prediction,
                "signals": signals,
                "shap_drivers": shap_drivers,
                "recommended_action": action,
                "plan": [
                    "load_customer_profile",
                    "read_latest_prediction",
                    "identify_customer_risk_signals",
                    "compare_with_global_shap_context",
                    "prepare_business_explanation",
                ],
            },
        )

    @staticmethod
    def _get(row: pd.Series, key: str, fallback: Any = None) -> Any:
        value = row.get(key, fallback)
        return fallback if pd.isna(value) else value

    def _prediction(self, row: pd.Series) -> dict[str, Any]:
        probability = self._get(row, "churn_probability")
        probability_float = float(probability) if probability is not None else None
        risk_band = self._get(row, "churn_risk_band") or self._risk_band(probability_float)
        derived_risk_band = self._risk_band(probability_float)
        return {
            "probability": probability_float,
            "probability_label": f"{probability_float * 100:.0f}%" if probability_float is not None else "non estimee",
            "risk_band": risk_band,
            "risk_band_label": self._risk_band_label(str(risk_band)) if risk_band else "non estime",
            "probability_interpretation": self._probability_interpretation(probability_float),
            "derived_risk_band": derived_risk_band,
            "consistency_note": self._consistency_note(risk_band, derived_risk_band),
            "predicted_churn_label": self._get(row, "predicted_churn_label"),
            "observation_date": self._get(row, "observation_date"),
            "mlflow_run_id": self._get(row, "mlflow_run_id"),
        }

    @staticmethod
    def _risk_band(probability: float | None) -> str | None:
        if probability is None:
            return None
        if probability >= 0.75:
            return "VERY_HIGH"
        if probability >= 0.5:
            return "HIGH"
        if probability >= 0.25:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _risk_band_label(risk_band: str) -> str:
        labels = {
            "VERY_HIGH": "tres eleve",
            "HIGH": "eleve",
            "MEDIUM": "moyen",
            "LOW": "faible",
        }
        return labels.get(risk_band, risk_band.replace("_", " ").lower())

    @staticmethod
    def _probability_interpretation(probability: float | None) -> str:
        if probability is None:
            return "score non disponible"
        if probability >= 0.75:
            return "risque tres eleve"
        if probability >= 0.5:
            return "risque eleve"
        if probability >= 0.25:
            return "risque moyen"
        return "risque faible a surveiller"

    @staticmethod
    def _consistency_note(risk_band: object, derived_risk_band: str | None) -> str | None:
        if risk_band is None or derived_risk_band is None:
            return None
        if str(risk_band) == derived_risk_band:
            return None
        return (
            f"La table retourne une bande {risk_band}, alors que la probabilite correspond "
            f"a {derived_risk_band}; verifier la calibration ou la definition de la bande."
        )

    def _customer_signals(self, row: pd.Series) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        self._add_numeric_signal(
            candidates,
            row,
            key="price_sensitivity_score",
            threshold=0.65,
            label="sensibilite prix elevee",
            direction="risk",
        )
        self._add_numeric_signal(
            candidates,
            row,
            key="avg_satisfaction_score_12m",
            threshold=3.5,
            label="satisfaction faible sur 12 mois",
            direction="risk",
            lower_is_risk=True,
        )
        self._add_numeric_signal(
            candidates,
            row,
            key="renewal_days_min",
            threshold=45,
            label="renouvellement proche",
            direction="risk",
            lower_is_risk=True,
            suffix="jours",
        )
        self._add_numeric_signal(
            candidates,
            row,
            key="days_since_last_contact",
            threshold=90,
            label="pas de contact recent",
            direction="risk",
            suffix="jours",
        )
        self._add_numeric_signal(
            candidates,
            row,
            key="payment_incidents_6m",
            threshold=0,
            label="incidents de paiement recents",
            direction="risk",
        )
        self._add_numeric_signal(
            candidates,
            row,
            key="complaints_6m",
            threshold=0,
            label="reclamations recentes",
            direction="risk",
        )

        action_reason = self._get(row, "action_reason")
        if action_reason:
            candidates.insert(
                0,
                {
                    "field": "action_reason",
                    "label": str(action_reason),
                    "value": action_reason,
                    "severity": 0.95,
                    "direction": "risk",
                },
            )
        return sorted(candidates, key=lambda item: float(item["severity"]), reverse=True)

    def _add_numeric_signal(
        self,
        signals: list[dict[str, Any]],
        row: pd.Series,
        *,
        key: str,
        threshold: float,
        label: str,
        direction: str,
        lower_is_risk: bool = False,
        suffix: str = "",
    ) -> None:
        raw = self._get(row, key)
        if raw is None:
            return
        value = float(raw)
        is_risk = value <= threshold if lower_is_risk else value > threshold
        if not is_risk:
            return
        denominator = max(abs(threshold), 1.0)
        severity = min(abs(value - threshold) / denominator + 0.5, 1.0)
        display_value = f"{value:.0f} {suffix}".strip() if suffix else round(value, 3)
        signals.append(
            {
                "field": key,
                "label": label,
                "value": display_value,
                "threshold": threshold,
                "severity": round(severity, 3),
                "direction": direction,
            }
        )

    def _shap_drivers(
        self,
        shap_summary: pd.DataFrame | None,
        row: pd.Series,
    ) -> list[dict[str, Any]]:
        if shap_summary is None or shap_summary.empty:
            return []
        drivers: list[dict[str, Any]] = []
        for shap_row in shap_summary.head(8).itertuples(index=False):
            feature = str(getattr(shap_row, "feature", ""))
            value = self._get(row, feature)
            drivers.append(
                {
                    "feature": feature,
                    "label": self._human_feature(feature),
                    "impact_direction": getattr(shap_row, "impact_direction", None),
                    "importance_pct": round(float(getattr(shap_row, "normalized_importance_pct", 0.0)), 1),
                    "customer_value": value,
                    "feature_available_for_customer": value is not None,
                }
            )
        return drivers

    def _recommended_action(self, row: pd.Series) -> str:
        return str(
            self._get(row, "next_best_step")
            or self._get(row, "advisor_message")
            or self._get(row, "recommended_action_type")
            or "faire revoir ce client par un conseiller retention"
        )

    @staticmethod
    def _human_feature(feature: str) -> str:
        labels = {
            "price_sensitivity_score": "sensibilite au prix",
            "loyalty_score": "score de fidelite",
            "service_sensitivity_score": "sensibilite au service",
            "customer_segment": "segment client",
            "claim_propensity_score": "propension aux sinistres",
            "days_since_last_contact": "anciennete du dernier contact",
            "digital_engagement_score": "engagement digital",
            "avg_satisfaction_score_12m": "satisfaction moyenne",
        }
        return labels.get(feature, feature.replace("_", " "))
