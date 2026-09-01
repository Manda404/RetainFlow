"""Draft email and call-script content for retention advisors."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class EmailDraft:
    """Human-reviewable message generated for a retention action."""

    subject: str
    body: str
    channel: str
    requires_human_approval: bool = True


class EmailDraftingTool:
    """Create French retention drafts without sending anything automatically."""

    def draft_from_recommendation(self, recommendation: pd.Series) -> EmailDraft:
        """Build a concise advisor message from one recommendation row."""
        first_name = recommendation.get("first_name", "")
        last_name = recommendation.get("last_name", "")
        offer = recommendation.get("recommended_offer", "un point de contact personnalise")
        rationale = recommendation.get("decision_rationale", "")
        next_step = recommendation.get("next_best_step", "Planifier un contact conseiller.")
        channel = str(recommendation.get("recommended_channel", "EMAIL"))

        subject = "Faisons le point sur votre contrat"
        body = (
            f"Bonjour {first_name} {last_name},\n\n"
            "Nous souhaitons faire un point avec vous afin de verifier que vos garanties "
            "restent bien adaptees a votre situation actuelle.\n\n"
            f"Proposition conseillee: {offer}.\n"
            f"Contexte conseiller: {rationale}\n"
            f"Prochaine etape: {next_step}\n\n"
            "Ce message est un brouillon et doit etre valide par un conseiller avant envoi."
        )
        return EmailDraft(subject=subject, body=body, channel=channel)
