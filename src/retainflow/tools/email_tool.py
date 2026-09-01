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
    """Create retention drafts without sending anything automatically."""

    def draft_from_recommendation(self, recommendation: pd.Series) -> EmailDraft:
        """Build a concise advisor message from one recommendation row."""
        first_name = recommendation.get("first_name", "")
        last_name = recommendation.get("last_name", "")
        offer = recommendation.get("recommended_offer", "a personalized advisor check-in")
        rationale = recommendation.get("decision_rationale", "")
        next_step = recommendation.get("next_best_step", "Schedule an advisor contact.")
        channel = str(recommendation.get("recommended_channel", "EMAIL"))

        subject = "Let's review your policy"
        body = (
            f"Hello {first_name} {last_name},\n\n"
            "We would like to review your policy with you to make sure your coverage still "
            "matches your current needs.\n\n"
            f"Recommended offer: {offer}.\n"
            f"Advisor context: {rationale}\n"
            f"Next step: {next_step}\n\n"
            "This message is a draft and must be approved by an advisor before sending."
        )
        return EmailDraft(subject=subject, body=body, channel=channel)
