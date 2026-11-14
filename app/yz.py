"""Yapay zekâ sağlayıcı katmanı — ücretsiz veya ücretli, hangisi tanımlıysa.

Ortam değişkenleri:
  YZ_SAGLAYICI  gemini | openai | anthropic        (boşsa: anahtar hangisiyse otomatik)
  YZ_ANAHTAR    API anahtarı (Gemini için Google AI Studio'dan ücretsiz alınır)
  YZ_MODEL      model adı (gemini varsayılanı: gemini-flash-latest)
  YZ_URL        OpenAI uyumlu uç nokta (openai sağlayıcısı için; ör. OpenRouter, Groq, Cerebras, yerel Ollama)
  YZ_DAKIKADA   dakikada en fazla istek (ücretsiz katmanlar için yavaşlatma; varsayılan gemini 8, diğer 20)
Geriye dönük: ANTHROPIC_API_KEY tanımlıysa anthropic kullanılır.
"""
import json, os, re, sys, threading, time, urllib.request, urllib.error

def _kayit(m): print(time.strftime("%H:%M:%S"), "  [yz]", m, flush=True)

def _ozet(hata):
    """Sağlayıcının hata JSON'undan kısa, okunur mesaj çıkar."""
    try:
        d = json.loads(hata); d = d[0] if isinstance(d, list) else d
        e = d.get("error", d); m = e.get("message") if isinstance(e, dict) else str(e)
        return re.sub(r"\s+", " ", m or hata)[:300]
    except Exception:
        return re.sub(r"\s+", " ", hata)[:300]

# Anahtarın biçiminden sağlayıcıyı tanı (yanlış satıra yazılsa da doğru yere gitsin)
def _tani(anahtar):
    if anahtar.startswith("AIza"): return "gemini", ""
    if anahtar.startswith("sk-ant-"): return "anthropic", ""
    if anahtar.startswith("sk-or-"): return "openai", "https://openrouter.ai/api/v1/chat/completions"
    if anahtar.startswith("gsk_"): return "openai", "https://api.groq.com/openai/v1/chat/completions"
    if anahtar.startswith("csk-"): return "openai", "https://api.cerebras.ai/v1/chat/completions"
    return None, ""

ANAHTAR = (os.environ.get("YZ_ANAHTAR") or os.environ.get("ANTHROPIC_API_KEY") or "").strip()
SAGLAYICI = os.environ.get("YZ_SAGLAYICI", "").strip().lower()
_tahmin, _tahmin_url = _tani(ANAHTAR)
if _tahmin and (not SAGLAYICI or SAGLAYICI != _tahmin):
    SAGLAYICI = _tahmin  # anahtar biçimi kesin bilgi verir
if not SAGLAYICI and ANAHTAR: SAGLAYICI = "gemini"

VARSAYILAN_MODEL = {"gemini": "gemini-flash-latest", "anthropic": "claude-sonnet-4-5", "openai": "meta-llama/llama-3.3-70b-instruct:free"}
MODEL = os.environ.get("YZ_MODEL") or ""
if SAGLAYICI == "anthropic" and not MODEL: MODEL = os.environ.get("KURAN_MODEL", "")
if (SAGLAYICI == "gemini" and MODEL and not MODEL.startswith(("gemini", "gemma"))) or \
   (SAGLAYICI == "anthropic" and MODEL and not MODEL.startswith("claude")):
    MODEL = ""  # başka sağlayıcının model adı kalmışsa yok say
if not MODEL and "groq.com" in _tahmin_url: MODEL = "llama-3.3-70b-versatile"
if not MODEL and "cerebras.ai" in _tahmin_url: MODEL = "llama-3.3-70b"
MODEL = MODEL or VARSAYILAN_MODEL.get(SAGLAYICI, "")
URL = os.environ.get("YZ_URL") or _tahmin_url or {"gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
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
                kisa = _ozet(hata)
                if any(k in hata.lower() for k in ("per day", "perday", "daily", "requests_per_day", "per_day")) and i >= 1:
                    raise KotaDoldu(kisa)
                if re.search(r"limit:\s*0\b", hata):  # bu model ücretsiz katmanda hiç yok
                    raise RuntimeError(f"YZ 429: bu model ücretsiz katmanda kullanılamıyor, YZ_MODEL'i değiştirin. ({kisa})")
                bekle = min(300, 30 * (i + 1)); _kayit(f"429 sınır: {bekle} sn bekleyip tekrar denenecek ({i+1}/{deneme}) · {kisa}")
                time.sleep(bekle); continue
            if e.code == 400 and json_cikti and "response_format" in govde:
                _kayit("sağlayıcı JSON biçimini desteklemiyor, düz metinle tekrar"); govde.pop("response_format"); continue
            if e.code in (500, 502, 503, 504, 529):
                _kayit(f"{e.code} sunucu hatası, {20*(i+1)} sn sonra tekrar · {_ozet(hata)}"); time.sleep(20 * (i + 1)); continue
            raise RuntimeError(f"YZ {e.code}: {_ozet(hata)}")
        except (urllib.error.URLError, TimeoutError) as e:
            hata = str(e); _kayit(f"bağlantı sorunu, tekrar denenecek · {hata[:200]}"); time.sleep(15 * (i + 1))
    raise RuntimeError("YZ yanıt vermedi: " + hata)
