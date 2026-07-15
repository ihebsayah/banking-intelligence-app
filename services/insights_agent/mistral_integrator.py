import logging
import requests
from typing import Dict, Any, List

from config import Settings

logger = logging.getLogger(__name__)


class MistralIntegrator:
    """Generate natural language insights using local Mistral (Ollama)."""

    def __init__(self, config: Settings):
        self.config = config
        self._base_url = config.MISTRAL_API_URL
        self._model = config.MISTRAL_MODEL

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    # Monetary columns — format as currency in fallback
    _MONETARY_COLS = {"balance", "available_balance", "amount", "fee", "revenue"}

    def generate_summary(
        self,
        query_intent: str,
        query_text: str,
        results: List[Dict],
        statistics: Dict[str, Any],
        context: Dict[str, Any],
        trends: List[Dict],
        primary_col: str = None,
    ) -> str:
        """Call Mistral for a 2-3 sentence executive summary."""
        prompt = self._build_summary_prompt(
            query_intent, query_text, results, statistics, context, trends
        )
        summary = self._call_ollama(prompt, max_tokens=400)
        if summary:
            return summary

        # Dynamic fallback — format based on primary metric type
        num_records = len(results)
        total_sum = statistics.get("total_sum")
        avg = statistics.get("average")
        is_monetary = primary_col in self._MONETARY_COLS if primary_col else False

        top_region = max(
            context.get("regional_breakdown", {"Unknown": 1}),
            key=lambda k: context.get("regional_breakdown", {}).get(k, 0),
            default="Unknown",
        )

        col_label = primary_col.replace("_", " ").title() if primary_col else "metric"
        fallback = f"Analysis of '{query_text}' across {num_records} records: "

        if total_sum is not None and avg is not None:
            if is_monetary:
                fallback += (
                    f"total {col_label} = ${total_sum:,.0f}, "
                    f"average {col_label} = ${avg:,.0f} per record. "
                )
            else:
                fallback += (
                    f"average {col_label} = {avg:.3f} "
                    f"(total = {total_sum:.3f}). "
                )
        else:
            fallback += f"highest concentration in {top_region} region. "

        if trends:
            t_names = [t.get("metric", "").replace("_", " ") for t in trends]
            fallback += f"Key drivers: {', '.join(t_names)}. "

        fallback += f"Recommend prioritising {top_region} branch for strategic allocation."
        return fallback

    def generate_recommendations(
        self,
        summary: str,
        statistics: Dict[str, Any],
        trends: List[Dict],
    ) -> List[str]:
        """Return up to 3 actionable business recommendations."""
        prompt = (
            f"Banking analysis summary: {summary}\n"
            f"Key statistics: total={statistics.get('total_sum')}, "
            f"avg={statistics.get('average')}, outliers={len(statistics.get('outliers', []))}\n"
            f"Trends: {[t.get('metric') for t in trends]}\n\n"
            "Generate exactly 3 specific, actionable banking business recommendations.\n"
            "Format: numbered list 1. 2. 3. — one per line, no preamble."
        )
        raw = self._call_ollama(prompt, max_tokens=250)
        if raw:
            lines = [
                ln.strip()
                for ln in raw.splitlines()
                if ln.strip() and ln.strip()[0].isdigit()
            ]
            if len(lines) >= 3:
                return lines[:3]

        # Smart, specific fallbacks based on trends & metrics
        outliers_count = len(statistics.get("outliers", []))
        avg = statistics.get("average") or 0.0
        
        recs = [
            f"1. Optimize operational capacity in high-performing regions to sustain recent transaction growth trends.",
            f"2. Schedule a portfolio risk review for segments displaying anomalous behaviors (detected {outliers_count} outliers).",
            f"3. Tailor personalized high-value product packages for customer profiles exceeding average margins ({avg:.2f})."
        ]
        return recs

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    def _call_ollama(self, prompt: str, max_tokens: int = 300) -> str:
        """POST to Ollama /api/generate. Returns text or empty string on failure."""
        try:
            resp = requests.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.6,
                    "num_predict": max_tokens,
                },
                timeout=180,
            )
            if resp.status_code == 200:
                return resp.json().get("response", "").strip()
            logger.warning(f"Ollama HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            logger.error(f"Ollama call failed: {exc}")
        return ""

    def _build_summary_prompt(
        self,
        query_intent: str,
        query_text: str,
        results: List[Dict],
        statistics: Dict[str, Any],
        context: Dict[str, Any],
        trends: List[Dict],
    ) -> str:
        top_region = max(
            context.get("regional_breakdown", {"Unknown": 1}),
            key=lambda k: context.get("regional_breakdown", {}).get(k, 0),
            default="Unknown",
        )
        return (
            "You are a senior banking analyst. Write a 2-3 sentence executive summary.\n\n"
            f"Query: \"{query_text}\"\n"
            f"Intent category: {query_intent}\n"
            f"Records returned: {len(results)}\n"
            f"Sample rows: {results[:2]}\n\n"
            f"Statistics:\n"
            f"  Total: {statistics.get('total_sum', 'N/A')}\n"
            f"  Average: {statistics.get('average', 'N/A')}\n"
            f"  Std dev: {statistics.get('std_dev', 'N/A')}\n"
            f"  Outliers: {len(statistics.get('outliers', []))}\n\n"
            f"System context:\n"
            f"  System total deposits: {context.get('system_totals', {}).get('total_deposits', 'N/A')}\n"
            f"  Total customers: {context.get('system_totals', {}).get('total_customers', 'N/A')}\n"
            f"  Top region: {top_region}\n\n"
            f"Trends detected: {[t.get('metric') for t in trends]}\n\n"
            "Summary (be specific, use numbers, use banking terminology):"
        )
