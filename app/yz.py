"""Yapay zekâ sağlayıcı katmanı — ücretsiz veya ücretli, hangisi tanımlıysa.

Ortam değişkenleri:
  YZ_SAGLAYICI  gemini | openai | anthropic        (boşsa: anahtar hangisiyse otomatik)
  YZ_ANAHTAR    API anahtarı (Gemini için Google AI Studio'dan ücretsiz alınır)
  YZ_MODEL      model adı (gemini varsayılanı: gemini-flash-latest)
  YZ_URL        OpenAI uyumlu uç nokta (openai sağlayıcısı için; ör. OpenRouter, Groq, Cerebras, yerel Ollama)
  YZ_DAKIKADA   dakikada en fazla istek (ücretsiz katmanlar için yavaşlatma; varsayılan gemini 8, diğer 20)
Geriye dönük: ANTHROPIC_API_KEY tanımlıysa anthropic kullanılır.
"""
import json, os, threading, time, urllib.request, urllib.error

SAGLAYICI = os.environ.get("YZ_SAGLAYICI", "").lower()
ANAHTAR = os.environ.get("YZ_ANAHTAR", "")
if not SAGLAYICI:
    if ANAHTAR: SAGLAYICI = "gemini"
    elif os.environ.get("ANTHROPIC_API_KEY"): SAGLAYICI, ANAHTAR = "anthropic", os.environ["ANTHROPIC_API_KEY"]
if SAGLAYICI == "anthropic" and not ANAHTAR: ANAHTAR = os.environ.get("ANTHROPIC_API_KEY", "")

VARSAYILAN_MODEL = {"gemini": "gemini-flash-latest", "anthropic": "claude-sonnet-4-5", "openai": "meta-llama/llama-3.3-70b-instruct:free"}
MODEL = os.environ.get("YZ_MODEL") or os.environ.get("KURAN_MODEL") or VARSAYILAN_MODEL.get(SAGLAYICI, "")
URL = os.environ.get("YZ_URL") or {"gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                                    "openai": "https://openrouter.ai/api/v1/chat/completions"}.get(SAGLAYICI, "")
DAKIKADA = float(os.environ.get("YZ_DAKIKADA") or (8 if SAGLAYICI == "gemini" else 20))

def hazir(): return bool(SAGLAYICI and (ANAHTAR or URL.startswith("http://")))  # http:// = yerel sunucu (Ollama vb.), anahtarsız
def bilgi(): return {"saglayici": SAGLAYICI or None, "model": MODEL if hazir() else None, "hazir": hazir()}

_son = [0.0]; _kilit = threading.Lock()
def _bekle():
    with _kilit:
        ara = 60.0 / max(DAKIKADA, 0.1); simdi = time.time()
        if simdi - _son[0] < ara: time.sleep(ara - (simdi - _son[0]))
        _son[0] = time.time()

class KotaDoldu(Exception): pass

def sohbet(sistem, mesaj, max_tokens=4000, json_cikti=False, deneme=6):
    """Metin döndürür. Geçici hatalarda bekleyip tekrar dener; günlük kota dolarsa KotaDoldu fırlatır."""
    if not hazir(): raise RuntimeError("Yapay zekâ tanımlı değil (YZ_ANAHTAR / YZ_SAGLAYICI).")
    if SAGLAYICI == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        govde = {"model": MODEL, "max_tokens": max_tokens, "system": sistem, "messages": [{"role": "user", "content": mesaj}]}
        basliklar = {"x-api-key": ANAHTAR, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    else:
        url = URL
        govde = {"model": MODEL, "max_tokens": max_tokens, "temperature": 0.2,
                 "messages": [{"role": "system", "content": sistem}, {"role": "user", "content": mesaj}]}
        if json_cikti: govde["response_format"] = {"type": "json_object"}
        basliklar = {"content-type": "application/json"}
        if ANAHTAR: basliklar["authorization"] = "Bearer " + ANAHTAR
    hata = ""
    for i in range(deneme):
        _bekle()
        try:
            req = urllib.request.Request(url, data=json.dumps(govde).encode(), method="POST", headers=basliklar)
            with urllib.request.urlopen(req, timeout=600) as r: d = json.loads(r.read())
            if SAGLAYICI == "anthropic": return "".join(b.get("text", "") for b in d["content"])
            return d["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as e:
            hata = e.read().decode(errors="ignore")[:500]
            if e.code == 429:
                if any(k in hata.lower() for k in ("per day", "perday", "daily", "requests_per_day", "quota exceeded for metric")) and i >= 1:
                    raise KotaDoldu(hata)
                time.sleep(min(300, 30 * (i + 1))); continue
            if e.code == 400 and json_cikti and "response_format" in govde:
                govde.pop("response_format"); continue  # bazı sağlayıcılar desteklemiyor
            if e.code in (500, 502, 503, 504, 529): time.sleep(20 * (i + 1)); continue
            raise RuntimeError(f"YZ {e.code}: {hata}")
        except (urllib.error.URLError, TimeoutError) as e:
            hata = str(e); time.sleep(15 * (i + 1))
    raise RuntimeError("YZ yanıt vermedi: " + hata)
