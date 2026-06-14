"""OA-002: SolutionOptionsScoringService — compute and persist prioritisation scores."""

from app.extensions import db
from app.models.capability_gap_analysis import CapabilityGapDetail, GapSolutionOption


class SolutionOptionsScoringService:
    """Compute feasibility, strategic alignment, and prioritisation scores for solution options."""

    def score_options(self, gap_analysis_id: int) -> list:
        """Score all GapSolutionOptions belonging to the given gap analysis.

        Scoring rules:
          feasibility_score  = 1.0 if time_to_implement_weeks <= 12
                              = 0.7 if <= 26
                              = 0.4 if > 26
                              = 0.5 if None
          strategic_alignment_score = option.strategic_alignment_score or 0.5
          prioritisation_score = (feasibility_score * 0.4) + (strategic_alignment_score * 0.6)

        Persists computed scores back via ORM and returns results sorted by
        prioritisation_score descending.
        """
        options = (
            GapSolutionOption.query
            .join(CapabilityGapDetail, GapSolutionOption.gap_detail_id == CapabilityGapDetail.id)
            .filter(CapabilityGapDetail.analysis_id == gap_analysis_id)
            .all()
        )

        results = []
        for option in options:
            weeks = option.time_to_implement_weeks
            if weeks is None:
                feasibility = 0.5
            elif weeks <= 12:
                feasibility = 1.0
            elif weeks <= 26:
                feasibility = 0.7
            else:
                feasibility = 0.4

            alignment = option.strategic_alignment_score if option.strategic_alignment_score is not None else 0.5
            prioritisation = round((feasibility * 0.4) + (alignment * 0.6), 6)

            option.feasibility_score = feasibility
            option.strategic_alignment_score = alignment
            option.prioritisation_score = prioritisation

            results.append({
                "option_id": option.id,
                "option_name": option.solution_name,
                "feasibility_score": feasibility,
                "strategic_alignment_score": alignment,
                "prioritisation_score": prioritisation,
                "time_to_implement_weeks": weeks,
            })

        db.session.commit()

        results.sort(key=lambda r: r["prioritisation_score"], reverse=True)
        return results
