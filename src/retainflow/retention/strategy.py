"""Retention strategy recommendations built from the priority queue."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from retainflow.config import ChurnModelConfig
from retainflow.data.dataset import sqlalchemy_dsn
from retainflow.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RetentionStrategy:
    action_type: str
    offer_label: str
    message_template: str
    default_next_step: str


STRATEGY_CATALOG = {
    "LOYALTY_DISCOUNT_REVIEW": RetentionStrategy(
        action_type="LOYALTY_DISCOUNT_REVIEW",
        offer_label="Remise fidelite controlee",
        message_template=(
            "Recontacter le client pour reconnaitre la sensibilite prix et proposer "
            "une remise fidelite adaptee a la valeur du portefeuille."
        ),
        default_next_step="Validation manager retention avant proposition commerciale.",
    ),
    "SERVICE_RECOVERY_CALL": RetentionStrategy(
        action_type="SERVICE_RECOVERY_CALL",
        offer_label="Appel de resolution prioritaire",
        message_template=(
            "Appeler le client pour traiter les irritants service, clarifier le dossier "
            "ouvert et confirmer une action corrective."
        ),
        default_next_step="Assigner un conseiller service senior sous 24h.",
    ),
    "RENEWAL_SAVE_CALL": RetentionStrategy(
        action_type="RENEWAL_SAVE_CALL",
        offer_label="Appel sauvegarde renouvellement",
        message_template=(
            "Contacter le client avant echeance pour expliquer la valeur des garanties "
            "et proposer un ajustement si necessaire."
        ),
        default_next_step="Planifier un appel sortant avant la prochaine echeance.",
    ),
    "PAYMENT_PLAN_PROPOSAL": RetentionStrategy(
        action_type="PAYMENT_PLAN_PROPOSAL",
        offer_label="Amenagement de paiement",
        message_template=(
            "Proposer une solution de paiement plus souple afin de reduire le risque "
            "de resiliation lie aux incidents de paiement."
        ),
        default_next_step="Verifier eligibilite paiement fractionne.",
    ),
    "DIGITAL_REENGAGEMENT": RetentionStrategy(
        action_type="DIGITAL_REENGAGEMENT",
        offer_label="Reactivation digitale accompagnee",
        message_template=(
            "Envoyer une sequence de reengagement digital avec rappel des services "
            "utiles et proposition de rendez-vous si besoin."
        ),
        default_next_step="Declencher campagne email personnalisee.",
    ),
    "PROACTIVE_RETENTION_CHECK": RetentionStrategy(
        action_type="PROACTIVE_RETENTION_CHECK",
        offer_label="Controle retention proactif",
        message_template=(
            "Verifier la situation client et proposer un point de contact preventif "
            "avant degradation du risque."
        ),
        default_next_step="Creer une tache conseiller pour qualification.",
    ),
}


class RetentionStrategyLoader:
    """Load prioritized customers for strategy generation."""

    def __init__(self, config: ChurnModelConfig) -> None:
        self.config = config

    def load(self, limit: int = 500, tiers: tuple[str, ...] = ("CRITICAL", "HIGH", "MEDIUM")):
        placeholders = ", ".join(f":tier_{index}" for index, _ in enumerate(tiers))
        params = {f"tier_{index}": tier for index, tier in enumerate(tiers)}
        params["limit"] = int(limit)
        query = f"""
            SELECT *
            FROM {self.config.retention_queue_fqn}
            WHERE priority_tier IN ({placeholders})
            ORDER BY priority_score DESC, expected_saved_value DESC
            LIMIT :limit
        """
        logger.info("Loading top retention queue rows from %s", self.config.retention_queue_fqn)
        engine = create_engine(sqlalchemy_dsn(self.config.postgres_dsn))
        with engine.connect() as conn:
            return pd.read_sql_query(text(query), conn, params=params)


class RetentionStrategyEngine:
    """Generate human-reviewable retention recommendations."""

    def __init__(
        self,
        strategy_catalog: dict[str, RetentionStrategy] | None = None,
    ) -> None:
        self.strategy_catalog = strategy_catalog or STRATEGY_CATALOG

    def recommend(self, priority_queue: pd.DataFrame) -> pd.DataFrame:
        if priority_queue.empty:
            return self._empty_recommendations()

        frame = priority_queue.copy()
        frame["strategy"] = frame["recommended_action_type"].map(self._strategy_for_action)
        frame["recommendation_id"] = frame.apply(self._recommendation_id, axis=1)
        frame["recommended_offer"] = frame.apply(self._recommended_offer, axis=1)
        frame["advisor_message"] = frame.apply(self._advisor_message, axis=1)
        frame["decision_rationale"] = frame.apply(self._decision_rationale, axis=1)
        frame["next_best_step"] = frame["strategy"].map(lambda strategy: strategy.default_next_step)
        frame["human_review_status"] = "PENDING_REVIEW"
        frame["approval_decision"] = None
        frame["approval_comment"] = None

        columns = [
            "recommendation_id",
            "observation_date",
            "customer_id",
            "split_name",
            "first_name",
            "last_name",
            "priority_tier",
            "priority_score",
            "churn_probability",
            "expected_saved_value",
            "recommended_action_type",
            "recommended_channel",
            "recommended_offer",
            "estimated_offer_value",
            "advisor_message",
            "decision_rationale",
            "next_best_step",
            "human_review_status",
            "approval_decision",
            "approval_comment",
            "mlflow_run_id",
        ]
        return frame[columns].reset_index(drop=True)

    def _strategy_for_action(self, action_type: str) -> RetentionStrategy:
        return self.strategy_catalog.get(action_type, self.strategy_catalog["PROACTIVE_RETENTION_CHECK"])

    def _recommendation_id(self, row: pd.Series) -> str:
        raw = f"{row['observation_date']}|{row['customer_id']}|{row['mlflow_run_id']}"
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        return f"REC_{digest.upper()}"

    def _recommended_offer(self, row: pd.Series) -> str:
        strategy = row["strategy"]
        return f"{strategy.offer_label} - budget max {float(row['estimated_offer_value']):.2f} EUR"

    def _advisor_message(self, row: pd.Series) -> str:
        strategy = row["strategy"]
        customer_name = f"{row['first_name']} {row['last_name']}"
        return (
            f"{customer_name}: {strategy.message_template} "
            f"Canal recommande: {row['recommended_channel']}."
        )

    def _decision_rationale(self, row: pd.Series) -> str:
        return (
            f"Priorite {row['priority_tier']} avec score {float(row['priority_score']):.2f}. "
            f"Probabilite de churn {float(row['churn_probability']):.1%}. "
            f"Valeur sauvee attendue {float(row['expected_saved_value']):.2f} EUR. "
            f"Raisons: {row['action_reason']}."
        )

    def _empty_recommendations(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "recommendation_id",
                "customer_id",
                "priority_tier",
                "recommended_action_type",
                "recommended_offer",
                "human_review_status",
            ]
        )


class RetentionRecommendationRepository:
    """Persist retention recommendations to CSV and PostgreSQL."""

    def __init__(self, config: ChurnModelConfig) -> None:
        self.config = config

    def save_csv(self, recommendations: pd.DataFrame, path: str | Path | None = None) -> Path:
        output_path = Path(path or self.config.retention_recommendation_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        recommendations.to_csv(output_path, index=False)
        return output_path

    def save_postgres(self, recommendations: pd.DataFrame) -> None:
        logger.info(
            "Saving %s retention recommendations to %s",
            len(recommendations),
            self.config.retention_recommendation_fqn,
        )
        engine = create_engine(sqlalchemy_dsn(self.config.postgres_dsn))
        with engine.begin() as conn:
            conn.execute(text(self._create_table_sql()))
            conn.execute(text(f"TRUNCATE TABLE {self.config.retention_recommendation_fqn}"))
            recommendations.to_sql(
                self.config.retention_recommendation_table,
                conn,
                schema=self.config.schema_name,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=1000,
            )

    def _create_table_sql(self) -> str:
        return f"""
            CREATE TABLE IF NOT EXISTS {self.config.retention_recommendation_fqn} (
              recommendation_id text PRIMARY KEY,
              observation_date date NOT NULL,
              customer_id text NOT NULL,
              split_name text NOT NULL,
              first_name text NOT NULL,
              last_name text NOT NULL,
              priority_tier text NOT NULL,
              priority_score numeric(8,2) NOT NULL,
              churn_probability numeric(8,6) NOT NULL,
              expected_saved_value numeric(12,2) NOT NULL,
              recommended_action_type text NOT NULL,
              recommended_channel text NOT NULL,
              recommended_offer text NOT NULL,
              estimated_offer_value numeric(12,2) NOT NULL,
              advisor_message text NOT NULL,
              decision_rationale text NOT NULL,
              next_best_step text NOT NULL,
              human_review_status text NOT NULL,
              approval_decision text,
              approval_comment text,
              mlflow_run_id text NOT NULL,
              created_at timestamptz NOT NULL DEFAULT now()
            )
        """
