"""
Groq LLM Client — powers the Maintenance Planner agent reasoning.

Uses the model named by GROQ_MODEL via Groq's free-tier API for natural language
maintenance recommendations based on RAG context.
"""

import httpx
from ..config import get_settings


async def ask_llm(system_prompt: str, user_prompt: str) -> str:
    """Call the Groq chat-completions API. Returns "" when no key is set or the call fails."""
    settings = get_settings()
    if not settings.groq_api_key or settings.groq_api_key.startswith("gsk_PASTE"):
        # No key configured — return a sensible fallback
        return ""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.groq_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""
    except Exception as e:
        print(f"[LLM] Groq API error: {e}")
        return ""
