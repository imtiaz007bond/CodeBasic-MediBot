import os
from openai import OpenAI
_client = None
def client():
    global _client
    if _client is None:
        key = os.getenv("OPENAI_API_KEY", "")
        if not key or key == "replace_me": return None
        _client = OpenAI(api_key=key, base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    return _client
def generate(system: str, user: str, temperature: float = 0.1) -> str:
    c = client()
    if c is None: return "LLM is not configured. Set OPENAI_API_KEY in backend/.env and retry."
    r = c.chat.completions.create(model=os.getenv("CHAT_MODEL", "gpt-4o-mini"), messages=[{"role":"system","content":system},{"role":"user","content":user}], temperature=temperature)
    return (r.choices[0].message.content or "").strip()
