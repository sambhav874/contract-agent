"""Output synthesis and formatting."""

from typing import Any

from app.config import settings
from app.db.models import BaseAnalysisOutput
from app.llm.gemini_client import call_gemini


class Synthesiser:
    """Synthesizes analysis output into human-readable format."""

    def __init__(self):
        self.model = settings.gemini_fast_model

    async def synthesise(
        self,
        output: BaseAnalysisOutput,
        mode: str = "plain",
    ) -> dict[str, Any]:
        """
        Synthesize analysis output.

        Args:
            output: Analysis output from agent
            mode: 'plain' or 'legal'

        Returns:
            Dict with structured data and narrative summary
        """
        narrative = await self._generate_narrative(output, mode)
        stats = self._compute_stats(output)

        return {
            "structured": output.model_dump(),
            "narrative": narrative,
            "statistics": stats,
        }

    async def _generate_narrative(
        self,
        output: BaseAnalysisOutput,
        mode: str,
    ) -> str:
        """Generate human-readable narrative from structured output."""
        system_prompt = f"""You are summarizing contract analysis results.
Generate a concise narrative summary (1-3 sentences per major finding).
Use {'plain English' if mode == 'plain' else 'precise legal terminology'}."""

        user_message = f"""Analysis output:
{output.model_dump_json(indent=2)}

Generate a narrative summary."""

        try:
            response = await call_gemini(
                model=self.model,
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=0.2,
            )
            # Try specific keys, then fallback to 'text', then string conversion
            return response.get("summary") or response.get("text") or str(response)
        except Exception:
            return f"Analysis complete. Type: {type(output).__name__}"

    def _compute_stats(self, output: BaseAnalysisOutput) -> dict[str, Any]:
        """Compute summary statistics."""
        stats: dict[str, Any] = {}

        # Risk analysis
        if hasattr(output, "risks"):
            risks = getattr(output, "risks", [])
            stats["total_risks"] = len(risks)

            severity_counts: dict[str, int] = {}
            for risk in risks:
                sev = getattr(risk, "severity", 0)
                severity_counts[str(sev)] = severity_counts.get(str(sev), 0) + 1

            stats["by_severity"] = severity_counts

        # KPI analysis
        if hasattr(output, "kpis"):
            kpis = getattr(output, "kpis", [])
            stats["total_kpis"] = len(kpis)

        # Red flag analysis
        if hasattr(output, "flags"):
            flags = getattr(output, "flags", [])
            stats["total_flags"] = len(flags)

            severity_summary: dict[str, int] = {}
            for flag in flags:
                sev = getattr(flag, "severity", "Unknown")
                severity_summary[sev] = severity_summary.get(sev, 0) + 1

            stats["by_severity"] = severity_summary

        return stats


# Global synthesiser instance
_synthesiser: Synthesiser | None = None


def get_synthesiser() -> Synthesiser:
    """Get or create synthesiser."""
    global _synthesiser
    if _synthesiser is None:
        _synthesiser = Synthesiser()
    return _synthesiser


async def synthesise_output(
    output: BaseAnalysisOutput,
    mode: str = "plain",
) -> dict[str, Any]:
    """Convenience function to synthesize output."""
    synthesiser = get_synthesiser()
    return await synthesiser.synthesise(output, mode)
