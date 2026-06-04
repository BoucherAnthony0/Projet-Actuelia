"""Couche LLM commutable. Tout le couplage au fournisseur est ici.
  LLM_PROVIDER=openai_compat  -> Gemini / Groq / Mistral… (gratuit, SDK openai)
  LLM_PROVIDER=anthropic      -> Claude (SDK anthropic)
Passer de l'un à l'autre = changer le .env, aucun autre fichier ne bouge.
"""
import json
import config

_client = None


def _get_client():
    """Retourne (kind, client) où kind ∈ {'anthropic','openai'}."""
    global _client
    if _client is None:
        if config.LLM_PROVIDER == "anthropic":
            from anthropic import Anthropic
            if not config.ANTHROPIC_API_KEY:
                raise RuntimeError("ANTHROPIC_API_KEY manquant (voir .env).")
            _client = ("anthropic", Anthropic(api_key=config.ANTHROPIC_API_KEY))
        else:
            from openai import OpenAI
            if not config.LLM_API_KEY:
                raise RuntimeError("LLM_API_KEY manquant (voir .env).")
            _client = ("openai", OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL))
    return _client


def complete(system: str, user: str, *, temperature: float = 0.3, model: str | None = None) -> str:
    kind, cli = _get_client()
    if kind == "anthropic":
        r = cli.messages.create(
            model=model or config.ANTHROPIC_MODEL, max_tokens=config.LLM_MAX_TOKENS,
            temperature=temperature, system=system,
            messages=[{"role": "user", "content": user}])
        return r.content[0].text.strip()
    r = cli.chat.completions.create(
        model=model or config.LLM_MODEL, temperature=temperature,
        max_tokens=config.LLM_MAX_TOKENS,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    return r.choices[0].message.content.strip()


def complete_json(system: str, user: str, *, model: str | None = None) -> dict:
    kind, cli = _get_client()
    if kind == "anthropic":
        r = cli.messages.create(
            model=model or config.ANTHROPIC_MODEL, max_tokens=config.LLM_MAX_TOKENS,
            temperature=0.1,
            system=system + "\nRéponds UNIQUEMENT par un objet JSON valide.",
            messages=[{"role": "user", "content": user},
                      {"role": "assistant", "content": "{"}])
        return json.loads("{" + r.content[0].text)
    txt = complete(system + "\nRéponds UNIQUEMENT par un JSON valide, sans texte ni balises.",
                   user, temperature=0.1, model=model)
    txt = txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(txt)
