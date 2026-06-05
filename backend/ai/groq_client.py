"""
GROQ LLM Client — wraps the GROQ API for all AI-powered features.
Model: llama-3.3-70b-versatile (fast, high-quality, long context).
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from backend.core.config import settings

log = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are an elite UAE Real Estate Decision Intelligence AI.
You have deep expertise in Dubai and UAE real estate markets, DLD data, RERA regulations,
off-plan markets, investment strategies, and macroeconomic drivers.

Always structure your responses as:
1. Direct answer / headline insight
2. Key supporting data points (3-5 bullets)
3. Recommended action

Be precise, data-driven, and use AED for monetary values.
Never fabricate specific statistics — use directional language if uncertain.
"""


class GroqClient:

    def __init__(self):
        self._client = None
        self._available = False
        self._init()

    def _init(self):
        key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
        if not key:
            log.warning("GROQ_API_KEY not set — AI features will use fallback responses.")
            return
        try:
            from groq import Groq
            self._client = Groq(api_key=key)
            self._available = True
            log.info("GROQ client initialised.")
        except Exception as exc:
            log.warning("GROQ init failed: %s", exc)

    @property
    def available(self) -> bool:
        return self._available

    def chat(self, user_message: str, context: str = "",
             system_override: Optional[str] = None,
             max_tokens: int = 1024, temperature: float = 0.3) -> str:
        if not self._available:
            return self._fallback(user_message)
        system = system_override or SYSTEM_PROMPT
        messages = [{"role": "system", "content": system}]
        if context:
            messages.append({"role": "user", "content": f"Context data:\n{context}"})
            messages.append({"role": "assistant", "content": "I have reviewed the market data. How can I help you?"})
        messages.append({"role": "user", "content": user_message})
        try:
            response = self._client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            log.error("GROQ chat error: %s", exc)
            return self._fallback(user_message)

    def executive_summary(self, kpis: Dict, forecast: Dict, risks: List, opps: List) -> str:
        context = f"""
Current Market KPIs:
- Total Transaction Volume (YTD): {kpis.get('total_transactions', 'N/A'):,}
- Total Transaction Value: AED {kpis.get('total_value_aed', 0)/1e9:.1f}B
- Avg Price/Sqft: AED {kpis.get('avg_price_sqft', 0):,.0f}
- YoY Transaction Growth: {kpis.get('yoy_growth_pct', 0):+.1f}%

Demand Forecast (next quarter):
- Expected demand change: {forecast.get('direction', 'stable')}
- Model: {forecast.get('model', 'Ensemble')} | MAPE: {forecast.get('mape', 'N/A')}%

Top Opportunity: {opps[0].get('area_name', 'Dubai South') if opps else 'N/A'}
  Score: {opps[0].get('opportunity_score', 0) if opps else 0}/100
  Expected ROI: {opps[0].get('expected_roi_pct', 0) if opps else 0:.1f}%

Active Risk Alerts: {len(risks)}
{risks[0].get('factor', '') if risks else 'None'}
"""
        prompt = ("Generate a 3-sentence executive intelligence briefing for a UAE real estate "
                  "developer based on the market data. Focus on actionable insights only.")
        return self.chat(prompt, context, max_tokens=256, temperature=0.4)

    def answer_strategy_query(self, question: str, context: str) -> str:
        return self.chat(question, context, max_tokens=1500, temperature=0.3)

    def analyze_scenario(self, scenario_desc: str, results: Dict) -> str:
        context = f"Scenario: {scenario_desc}\nSimulation Results: {results}"
        prompt = ("Analyse this what-if scenario for a UAE real estate developer. "
                  "State clearly: expected demand impact, price impact, and recommended action.")
        return self.chat(prompt, context, max_tokens=512, temperature=0.3)

    def launch_recommendation(self, area: str, property_type: str,
                               units: int, price_psf: float, context: str) -> str:
        prompt = (f"Evaluate the viability of launching a {units}-unit {property_type} project "
                  f"in {area} at AED {price_psf:,.0f}/sqft. "
                  f"Provide: success probability reasoning, optimal launch timing, "
                  f"and 3 specific pricing/marketing recommendations.")
        return self.chat(prompt, context, max_tokens=768, temperature=0.3)

    @staticmethod
    def _fallback(question: str) -> str:
        return (
            "**AI Analysis Unavailable** — GROQ API key not configured.\n\n"
            "To enable AI-powered insights, add your GROQ API key to the `.env` file:\n"
            "`GROQ_API_KEY=gsk_your_key_here`\n\n"
            "The platform will continue to function with data-driven analytics and ML models."
        )


groq_client = GroqClient()
