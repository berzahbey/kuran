"""Dedplay Kur'an Çalışma — API sunucusu."""
import concurrent.futures as cf, json, os, re, subprocess, sys, threading, urllib.request
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import FileResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
sys.path.insert(0, os.path.dirname(__file__))
import veri as V, kitap

app = FastAPI(title="Dedplay Kur'an Çalışma")
BURASI = os.path.dirname(os.path.abspath(__file__))
c = V.baglan(); V.sema_kur(c)
c.executescript("""
CREATE TABLE IF NOT EXISTS yalin_meal(s INT, a INT, metin TEXT, dipnotlar TEXT, durum TEXT DEFAULT 'taslak', guncelleme TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(s,a));
CREATE TABLE IF NOT EXISTS sure_bilgi(s INT PRIMARY KEY, ad_ar TEXT, nuzul TEXT);
""")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("KURAN_MODEL", "claude-sonnet-4-5")
VARSAYILAN_MEAL = os.environ.get("KURAN_MEAL", "tur-elmalilihamdiya")

def satirlar(sql, *p): return [dict(r) for r in c.execute(sql, p).fetchall()]
def tek(sql, *p):
    r = c.execute(sql, p).fetchone(); return dict(r) if r else None

def ilk_kurulum():
    """Uygulama ilk açıldığında olmazsa olmazları indir (Arapça, morfoloji)."""
    V.arapca_yukle(c); V.morfoloji_yukle(c); V.meal_kaynaklari_yukle(c); V.tefsir_kaynaklari_yukle(c)
    if not c.execute("SELECT 1 FROM sure_bilgi LIMIT 1").fetchone():
        t = V.indir(V.MEAL_URL + "/info.json")
        if t:
            with V._kilit:
                c.executemany("INSERT OR REPLACE INTO sure_bilgi VALUES(?,?,?)",
                              [(x["chapter"], x["arabicname"], x["revelation"]) for x in json.loads(t)["chapters"]]); c.commit()
    # onaylı pilot mealleri (Kalem 1-7) ilk açılışta içeri al
    if not c.execute("SELECT 1 FROM yalin_meal LIMIT 1").fetchone():
        for f in sorted(os.listdir(os.path.join(BURASI, "..", "ornek"))) if os.path.isdir(os.path.join(BURASI, "..", "ornek")) else []:
            subprocess.run([sys.executable, os.path.join(BURASI, "pilot_yukle.py"), os.path.join(BURASI, "..", "ornek", f)])
    # tüm külliyat henüz inmediyse arka planda indirmeye başla
    if os.environ.get("KURAN_OTOMATIK_INDIR", "1") == "1" and not c.execute("SELECT 1 FROM durum WHERE asama='eslestir'").fetchone():
        kur_baslat()
threading.Thread(target=lambda: (__import__("time").sleep(2), ilk_kurulum()), daemon=True).start()

# ---------------- Sureler / ayetler ----------------
@app.get("/api/sureler")
def sureler():
    notsay = {r["s"]: r["n"] for r in satirlar("SELECT s, count(*) n FROM notlar GROUP BY s")}
    yalin = {r["s"]: r["n"] for r in satirlar("SELECT s, count(*) n FROM yalin_meal GROUP BY s")}
    bilgi = {r["s"]: r for r in satirlar("SELECT * FROM sure_bilgi")}
    return [{"s": i + 1, "ad": V.SURE_ADLARI[i], "ad_ar": bilgi.get(i + 1, {}).get("ad_ar", ""), "nuzul": bilgi.get(i + 1, {}).get("nuzul", ""),
             "ayet": V.AYET_SAYILARI[i], "not": notsay.get(i + 1, 0), "yalin": yalin.get(i + 1, 0)} for i in range(114)]

@app.get("/api/sure/{s}")
def sure(s: int, meal: str = VARSAYILAN_MEAL):
    V.arapca_yukle(c); V.meal_sure_yukle(c, meal, s)
    ar = {r["a"]: r["metin"] for r in satirlar("SELECT a, metin FROM ayet WHERE s=? AND kaynak='ara-quranuthmanihaf'", s)}
    ml = {r["a"]: r["metin"] for r in satirlar("SELECT a, metin FROM meal WHERE id=? AND s=?", meal, s)}
    yl = {r["a"]: r for r in satirlar("SELECT a, metin, durum FROM yalin_meal WHERE s=?", s)}
    ns = {r["a"]: r["n"] for r in satirlar("SELECT a, count(*) n FROM notlar WHERE s=? GROUP BY a", s)}
    return {"s": s, "ad": V.SURE_ADLARI[s - 1], "ayetler": [
        {"a": a, "arapca": ar.get(a, ""), "meal": ml.get(a, ""), "yalin": (yl.get(a) or {}).get("metin"),
         "yalin_durum": (yl.get(a) or {}).get("durum"), "not": ns.get(a, 0)} for a in range(1, V.AYET_SAYILARI[s - 1] + 1)]}

@app.get("/api/ayet/{s}/{a}")
def ayet(s: int, a: int):
    hafs = tek("SELECT metin FROM ayet WHERE s=? AND a=? AND kaynak='ara-quranuthmanihaf'", s, a)
    kir = satirlar("SELECT kaynak, metin FROM ayet WHERE s=? AND a=? AND kaynak LIKE 'ara-quran%' AND kaynak NOT IN ('ara-quransimple')", s, a)
    hafs_sade = V.sadelestir(hafs["metin"]) if hafs else ""
    kiraat = [{"ravi": V.KIRAATLER[k["kaynak"]], "metin": k["metin"], "farkli": V.sadelestir(k["metin"]) != hafs_sade}
              for k in kir if k["kaynak"] in V.KIRAATLER]
    seg = satirlar("SELECT k, p, form, tur, etiket, kok, lemma FROM kelime WHERE s=? AND a=? ORDER BY k, p", s, a)
    kelimeler = {}
    for x in seg:
        w = kelimeler.setdefault(x["k"], {"k": x["k"], "form": "", "parcalar": [], "kok": None, "lemma": None})
        w["form"] += x["form"]; w["parcalar"].append({"form": x["form"], "tur": x["tur"], "etiket": x["etiket"]})
        if x["kok"]: w["kok"] = x["kok"]; w["lemma"] = x["lemma"]
        elif x["lemma"] and not w["kok"]: w["lemma"] = x["lemma"]
    for w in kelimeler.values():
        if w["kok"]:
            w["kok_sayisi"] = c.execute("SELECT count(DISTINCT s||':'||a||':'||k) FROM kelime WHERE kok=?", (w["kok"],)).fetchone()[0]
            w["lane_var"] = V.lane_bul(c, w["kok"]) is not None
    return {"s": s, "a": a, "sure": V.SURE_ADLARI[s - 1], "arapca": hafs["metin"] if hafs else "", "kiraat": kiraat,
            "kelimeler": list(kelimeler.values()),
            "yalin": tek("SELECT * FROM yalin_meal WHERE s=? AND a=?", s, a),
            "notlar": satirlar("SELECT * FROM notlar WHERE s=? AND a=? ORDER BY id DESC", s, a)}

# ---------------- Mealler ----------------
@app.get("/api/ayet/{s}/{a}/mealler")
def mealler(s: int, a: int, dil: str = ""):
    V.meal_kaynaklari_yukle(c)
    kaynak = satirlar("SELECT * FROM meal_kaynak" + (" WHERE dil=?" if dil else ""), *([dil] if dil else []))
    eksik = [k["id"] for k in kaynak if not c.execute("SELECT 1 FROM meal_sure WHERE id=? AND s=?", (k["id"], s)).fetchone()]
    if eksik:  # yerelde olmayanları internetten çek
        with cf.ThreadPoolExecutor(24) as ex: list(ex.map(lambda i: V.meal_sure_yukle(c, i, s), eksik))
    sonuc = {}
    for r in satirlar("SELECT m.id, m.metin, k.dil, k.yazar, k.yon FROM meal m JOIN meal_kaynak k ON k.id=m.id WHERE m.s=? AND m.a=?"
                      + (" AND k.dil=?" if dil else ""), s, a, *([dil] if dil else [])):
        if r["id"].endswith("-la") and r["dil"] != "Turkish": continue  # Latin harf çevriyazı kopyaları
        if r["id"].endswith("-la") and r["dil"] == "Turkish": continue
        sonuc.setdefault(r["dil"], []).append(r)
    sira = ["Turkish", "Arabic", "English", "Azerbaijani", "Persian", "Urdu", "French", "German", "Bosnian"]
    return [{"dil": d, "mealler": sonuc[d]} for d in sorted(sonuc, key=lambda d: (sira.index(d) if d in sira else 99, d))]

@app.get("/api/meal-kaynaklari")
def meal_kaynaklari():
    V.meal_kaynaklari_yukle(c)
    return satirlar("SELECT * FROM meal_kaynak WHERE id NOT LIKE '%-la' ORDER BY dil, yazar")

# ---------------- Tefsirler ----------------
def tefsir_sure_hazirla(s):
    V.tefsir_kaynaklari_yukle(c)
    eksik = [r[0] for r in c.execute("SELECT slug FROM tefsir_kaynak WHERE slug NOT IN (SELECT slug FROM tefsir_sure WHERE s=?)", (s,))]
    if eksik:
        with cf.ThreadPoolExecutor(24) as ex: list(ex.map(lambda sl: V.tefsir_sure_yukle(c, sl, s), eksik))

def tefsir_meta(slug, k):
    yil, tur, ad = V.TEFSIR_BILGI.get(slug, (9999, "diger", k.get("ad") or slug))
    return {"slug": slug, "ad": ad, "yazar": k.get("yazar"), "dil": k.get("dil"), "yil": yil, "tur": tur, "tur_ad": V.TUR_ADI.get(tur, "Diğer")}

@app.get("/api/ayet/{s}/{a}/tefsirler")
def tefsirler(s: int, a: int):
    tefsir_sure_hazirla(s)
    kay = {r["slug"]: r for r in satirlar("SELECT * FROM tefsir_kaynak")}
    sonuc = []
    for r in satirlar("SELECT slug, metin FROM tefsir WHERE s=? AND a=?", s, a):
        m = tefsir_meta(r["slug"], kay.get(r["slug"], {})); t = V.ac(r["metin"])
        m["uzunluk"] = len(t); m["ozet"] = re.sub(r"\s+", " ", t)[:260]; sonuc.append(m)
    # bu ayet için metni olmayan (önceki ayetle birlikte açıklanan) tefsirler
    return sorted(sonuc, key=lambda x: (x["yil"], x["dil"] != "arabic", x["ad"]))

@app.get("/api/tefsir/{slug}/{s}/{a}")
def tefsir_metin(slug: str, s: int, a: int):
    V.tefsir_sure_yukle(c, slug, s)
    r = tek("SELECT metin FROM tefsir WHERE slug=? AND s=? AND a=?", slug, s, a)
    if not r: raise HTTPException(404, "Bu tefsirde bu ayet için ayrı metin yok (önceki ayetle birlikte açıklanmış olabilir).")
    k = tek("SELECT * FROM tefsir_kaynak WHERE slug=?", slug) or {}
    return {**tefsir_meta(slug, k), "metin": V.ac(r["metin"])}

# ---------------- Hadisler ----------------
@app.get("/api/ayet/{s}/{a}/hadisler")
def hadisler(s: int, a: int):
    if not c.execute("SELECT 1 FROM hadis LIMIT 1").fetchone():
        raise HTTPException(409, "Hadis külliyatı henüz indirilmedi. 'Kaynaklar' bölümünden indirin.")
    sonuc = []
    for h in satirlar("SELECT kol, no, skor FROM hadis_ayet WHERE s=? AND a=? ORDER BY skor DESC, kol", s, a)[:150]:
        metinler = {r["dil"]: r for r in satirlar("SELECT dil, metin, derece FROM hadis WHERE kol=? AND no=?", h["kol"], h["no"])}
        sonuc.append({"kol": h["kol"], "kol_ad": V.HADIS_ADLARI.get(h["kol"], h["kol"]), "no": h["no"], "skor": h["skor"],
                      "ara": (metinler.get("ara") or {}).get("metin"), "tur": (metinler.get("tur") or {}).get("metin"),
                      "eng": (metinler.get("eng") or {}).get("metin"),
                      "derece": json.loads((metinler.get("eng") or metinler.get("ara") or {}).get("derece") or "[]")})
    return sonuc

@app.get("/api/hadis-ara")
def hadis_ara(q: str, dil: str = "tur", limit: int = 100):
    if V.re.search(r"[؀-ۿ]", q):
        qs = V.sadelestir(q)
        rows = [r for r in satirlar("SELECT kol, no, metin FROM hadis WHERE dil='ara'") if qs in V.sadelestir(r["metin"])][:limit]
    else:
        rows = satirlar("SELECT kol, no, metin FROM hadis WHERE dil=? AND metin LIKE ? LIMIT ?", dil, f"%{q}%", limit)
    for r in rows: r["kol_ad"] = V.HADIS_ADLARI.get(r["kol"], r["kol"])
    return rows

# ---------------- Kök / lügat ----------------
@app.get("/api/kok/{kok}")
def kok(kok: str, meal: str = VARSAYILAN_MEAL):
    lane = V.lane_bul(c, kok)
    gecis = satirlar("SELECT s, a, group_concat(form,'') form, lemma FROM kelime WHERE kok=? GROUP BY s,a,k ORDER BY s,a,k", kok)
    lemmalar = {}
    for g in gecis: lemmalar[g["lemma"]] = lemmalar.get(g["lemma"], 0) + 1
    sureler_ = sorted({g["s"] for g in gecis})
    with cf.ThreadPoolExecutor(16) as ex: list(ex.map(lambda s: V.meal_sure_yukle(c, meal, s), sureler_))
    for g in gecis:
        r = tek("SELECT metin FROM meal WHERE id=? AND s=? AND a=?", meal, g["s"], g["a"])
        g["meal"] = r["metin"] if r else ""; g["sure"] = V.SURE_ADLARI[g["s"] - 1]
    tr = tek("SELECT metin FROM ceviri_onbellek WHERE anahtar=?", "lane:" + kok)
    return {"kok": kok, "lane": lane, "lane_tr": tr["metin"] if tr else None, "lemmalar": lemmalar, "gecisler": gecis}

# ---------------- Notlar ----------------
@app.get("/api/notlar")
def notlar(s: int = 0, a: int = -1, q: str = ""):
    sql = "SELECT * FROM notlar WHERE 1=1"; p = []
    if s: sql += " AND s=?"; p.append(s)
    if a >= 0: sql += " AND a=?"; p.append(a)
    if q: sql += " AND (metin LIKE ? OR etiket LIKE ?)"; p += [f"%{q}%"] * 2
    r = satirlar(sql + " ORDER BY s, a, id", *p)
    for x in r: x["sure"] = V.SURE_ADLARI[x["s"] - 1] if x["s"] else ""
    return r

@app.post("/api/notlar")
def not_ekle(d: dict = Body(...)):
    with V._kilit:
        cur = c.execute("INSERT INTO notlar(s,a,metin,etiket) VALUES(?,?,?,?)", (d.get("s"), d.get("a"), d["metin"], d.get("etiket", ""))); c.commit()
    return tek("SELECT * FROM notlar WHERE id=?", cur.lastrowid)

@app.put("/api/notlar/{nid}")
def not_guncelle(nid: int, d: dict = Body(...)):
    with V._kilit:
        c.execute("UPDATE notlar SET metin=?, etiket=?, guncelleme=datetime('now') WHERE id=?", (d["metin"], d.get("etiket", ""), nid)); c.commit()
    return tek("SELECT * FROM notlar WHERE id=?", nid)

@app.delete("/api/notlar/{nid}")
def not_sil(nid: int):
    with V._kilit: c.execute("DELETE FROM notlar WHERE id=?", (nid,)); c.commit()
    return {"ok": True}

@app.get("/api/notlar/disa-aktar", response_class=PlainTextResponse)
def not_disa_aktar():
    out = ["# Kur'an Çalışma Notlarım\n"]; son = None
    for n in notlar():
        if n["s"] != son: out.append(f"\n## {n['s']}. {n['sure']} Sûresi\n"); son = n["s"]
        yer = f"Ayet {n['a']}" if n["a"] else "Sure geneli"
        out.append(f"**{yer}**" + (f" · _{n['etiket']}_" if n["etiket"] else "") + f"  \n{n['metin']}\n")
    return "\n".join(out)

# ---------------- Yalın meal + kitap ----------------
@app.put("/api/yalin/{s}/{a}")
def yalin_kaydet(s: int, a: int, d: dict = Body(...)):
    with V._kilit:
        c.execute("INSERT OR REPLACE INTO yalin_meal(s,a,metin,dipnotlar,durum,guncelleme) VALUES(?,?,?,?,?,datetime('now'))",
                  (s, a, d["metin"], json.dumps(d.get("dipnotlar", []), ensure_ascii=False), d.get("durum", "taslak"))); c.commit()
    return tek("SELECT * FROM yalin_meal WHERE s=? AND a=?", s, a)

@app.get("/api/kitap.epub")
def kitap_indir(sureler: str = "", sadece_onayli: bool = False):
    secili = [int(x) for x in sureler.split(",") if x] or sorted({r["s"] for r in satirlar("SELECT DISTINCT s FROM yalin_meal")})
    bilgi = {r["s"]: r["ad_ar"] for r in satirlar("SELECT * FROM sure_bilgi")}
    kitap_s = []
    for s in secili:
        ar = {r["a"]: r["metin"] for r in satirlar("SELECT a, metin FROM ayet WHERE s=? AND kaynak='ara-quranuthmanihaf'", s)}
        yl = {r["a"]: r for r in satirlar("SELECT * FROM yalin_meal WHERE s=?" + (" AND durum='onayli'" if sadece_onayli else ""), s)}
        if not yl: continue
        ayetler, dipnot, no = [], {}, 0
        for a in range(1, V.AYET_SAYILARI[s - 1] + 1):
            if a not in yl: continue
            metin = yl[a]["metin"]; notlar_ = json.loads(yl[a]["dipnotlar"] or "[]")
            def numarala(m):  # ayet içi [1],[2] → sure geneli sıra numarası
                nonlocal no
                i = int(m[1]) - 1
                if i < len(notlar_): no += 1; dipnot[str(no)] = notlar_[i]; return f"[{no}]"
                return ""
            metin = re.sub(r"\[(\d+)\]", numarala, metin)
            ayetler.append({"a": a, "arapca": ar.get(a, ""), "meal": metin})
        kitap_s.append({"s": s, "ad": V.SURE_ADLARI[s - 1], "ad_ar": bilgi.get(s, ""), "ayetler": ayetler, "dipnotlar": dipnot})
    if not kitap_s: raise HTTPException(404, "Kitaba girecek yalın meal yok.")
    ad = "Yalin_Meal_" + "-".join(str(x["s"]) for x in kitap_s)[:60] + ".epub"
    return Response(kitap.epub_yap(kitap_s), media_type="application/epub+zip", headers={"Content-Disposition": f'attachment; filename="{ad}"'})

# ---------------- Yapay zekâ: görüş analizi, yalın meal önerisi, Lane çevirisi ----------------
def claude(sistem, mesaj, max_tokens=4000):
    if not API_KEY: raise HTTPException(400, "ANTHROPIC_API_KEY tanımlı değil (docker-compose.yml içine ekleyin).")
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", method="POST",
        data=json.dumps({"model": MODEL, "max_tokens": max_tokens, "system": sistem, "messages": [{"role": "user", "content": mesaj}]}).encode(),
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r: d = json.loads(r.read())
    except urllib.error.HTTPError as e: raise HTTPException(502, "Claude API: " + e.read().decode()[:400])
    return "".join(b.get("text", "") for b in d["content"])

def kaynak_paketi(s, a, tefsir_siniri=2500, toplam=90000):
    ay = ayet(s, a); tefsir_sure_hazirla(s)
    kok = "; ".join(f'{w["form"]} (kök: {w["kok"] or "-"}, lemma: {w["lemma"] or "-"})' for w in ay["kelimeler"])
    tr = [m for g in mealler(s, a, "Turkish") for m in g["mealler"]][:25]
    en = [m for g in mealler(s, a, "English") for m in g["mealler"]][:10]
    kay = {r["slug"]: r for r in satirlar("SELECT * FROM tefsir_kaynak")}
    parca, boy = [], 0
    for r in sorted(satirlar("SELECT slug, metin FROM tefsir WHERE s=? AND a=?", s, a), key=lambda r: V.TEFSIR_BILGI.get(r["slug"], (9999,))[0]):
        m = tefsir_meta(r["slug"], kay.get(r["slug"], {}))
        if m["dil"] not in ("arabic", "turkish", "english"): continue
        t = re.sub(r"\s+", " ", V.ac(r["metin"]))[:tefsir_siniri]
        if boy + len(t) > toplam: break
        parca.append(f"### {m['ad']} (ö. {m['yil']}, {m['tur_ad']})\n{t}"); boy += len(t)
    return (f"AYET {s}:{a} ({ay['sure']})\nArapça: {ay['arapca']}\nKelimeler: {kok}\n\n"
            "## Türkçe mealler\n" + "\n".join(f"- {m['yazar']}: {m['metin']}" for m in tr) +
            "\n\n## İngilizce mealler\n" + "\n".join(f"- {m['yazar']}: {m['metin']}" for m in en) +
            "\n\n## Tefsirler (kronolojik)\n" + "\n\n".join(parca))

@app.get("/api/ayet/{s}/{a}/analiz")
def analiz_getir(s: int, a: int):
    return {r["tur"]: r["metin"] for r in satirlar("SELECT tur, metin FROM analiz WHERE s=? AND a=?", s, a)}

@app.post("/api/ayet/{s}/{a}/analiz")
def analiz_yap(s: int, a: int):
    sistem = ("Sen klasik Arap dili, tefsir usulü ve Kur'an ilimlerinde uzman, tarafsız bir araştırmacısın. Sana verilen kaynaklara dayan; "
              "kaynakta olmayanı uydurma, emin olmadığını belirt. Türkçe yaz.")
    mesaj = kaynak_paketi(s, a) + """

GÖREV: Bu ayet hakkında müfessirlerin AYNI ve AYRI görüşlerini çıkar. Markdown ile şu başlıklar:
## Ortak görüşler
(müfessirlerin ittifak ettiği noktalar; her maddede hangi müfessirler olduğunu yaz)
## Farklı görüşler
(her ihtilaf noktası için: mesele → görüş A (kimler) / görüş B (kimler) …)
## Kelime ve lügat notları
(kök anlamları, kelime tercihleri, meallerin ayrıştığı kelimeler)
## Mealler arasındaki farklar
(Türkçe meallerin hangi kelimelerde ve neden ayrıştığı)
## Kronolojik gelişim
(ilk dönemden günümüze yorumun nasıl değiştiği, kısaca)"""
    t = claude(sistem, mesaj, 5000)
    with V._kilit: c.execute("INSERT OR REPLACE INTO analiz(s,a,tur,metin) VALUES(?,?,?,?)", (s, a, "gorusler", t)); c.commit()
    return {"gorusler": t}

@app.post("/api/ayet/{s}/{a}/yalin-oneri")
def yalin_oneri(s: int, a: int):
    sistem = ("Sen Kur'an'ı Arapça aslından Türkçeye çeviren titiz bir mütercimsin. Kurallar: (1) Esas kök ve klasik lügat anlamıdır; "
              "tefsir ve mealler en doğru karşılığı bulmak ve ayrışmaları görmek içindir. (2) Meal EN YALIN hâlde olur, parantez içi açıklama yok. "
              "(3) Modern Türkçe kelime kökün anlamını tam karşılamıyorsa terim Arapça bırakılır. (4) Uzun açıklama kaçınılmazsa ilgili yere [1], [2] konur; "
              "açıklama dipnotta verilir. Dipnot yalnızca gerçekten gerekiyorsa. (5) Ayet numarası yazma.")
    mesaj = kaynak_paketi(s, a) + '\n\nÇIKTI: Sadece JSON: {"meal": "...", "dipnotlar": ["1. dipnot metni", ...], "gerekce": "kısa gerekçe"}'
    t = claude(sistem, mesaj, 2500)
    m = re.search(r"\{.*\}", t, re.S)
    try: d = json.loads(m[0])
    except Exception: raise HTTPException(502, "Model geçerli JSON döndürmedi: " + t[:300])
    with V._kilit: c.execute("INSERT OR REPLACE INTO analiz(s,a,tur,metin) VALUES(?,?,?,?)", (s, a, "yalin_oneri", json.dumps(d, ensure_ascii=False))); c.commit()
    return d

@app.post("/api/kok/{kok}/turkce")
def lane_turkce(kok: str):
    l = V.lane_bul(c, kok)
    if not l: raise HTTPException(404, "Lane'de bu kök yok")
    t = claude("Klasik Arapça sözlük çevirmenisin. Lane's Lexicon maddesini Türkçeye çevir. Arapça kelimeleri aynen bırak, kaynak kısaltmalarını (S, K, TA, Msb…) at. "
               "Önce 3-5 maddelik 'Temel anlamlar' özeti, sonra tam çeviri. Markdown.", re.sub(r"<[^>]+>", " ", l["html"])[:30000], 6000)
    with V._kilit: c.execute("INSERT OR REPLACE INTO ceviri_onbellek VALUES(?,?)", ("lane:" + kok, t)); c.commit()
    return {"metin": t}

# ---------------- Arama ----------------
@app.get("/api/ara")
def ara(q: str, meal: str = VARSAYILAN_MEAL, limit: int = 200):
    if re.search(r"[؀-ۿ]", q):
        qs = V.sadelestir(q)
        r = [x for x in satirlar("SELECT s, a, metin FROM ayet WHERE kaynak='ara-quranuthmanihaf'") if qs in V.sadelestir(x["metin"])][:limit]
    else:
        r = satirlar("SELECT s, a, metin FROM meal WHERE id=? AND metin LIKE ? ORDER BY s, a LIMIT ?", meal, f"%{q}%", limit)
    for x in r: x["sure"] = V.SURE_ADLARI[x["s"] - 1]
    return r

# ---------------- Kaynak durumu / toplu indirme ----------------
_kurulum = {"surec": None, "log": os.path.join(os.path.dirname(V.DB_YOL), "kurulum.log")}

@app.get("/api/durum")
def durum():
    say = lambda t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    calisiyor = _kurulum["surec"] is not None and _kurulum["surec"].poll() is None
    log = ""
    if os.path.exists(_kurulum["log"]): log = "".join(open(_kurulum["log"], encoding="utf-8").readlines()[-15:])
    return {"ayet_metni": say("ayet"), "kelime": say("kelime"), "lane_kok": say("lane"),
            "meal_kaynak": say("meal_kaynak"), "meal_sure": say("meal_sure"), "meal_sure_hedef": say("meal_kaynak") * 114,
            "tefsir_kaynak": say("tefsir_kaynak"), "tefsir_sure": say("tefsir_sure"), "tefsir_sure_hedef": say("tefsir_kaynak") * 114,
            "hadis": say("hadis"), "hadis_ayet": say("hadis_ayet"), "not": say("notlar"), "yalin": say("yalin_meal"),
            "db_mb": round(os.path.getsize(V.DB_YOL) / 1e6), "kurulum_calisiyor": calisiyor, "log": log, "yapay_zeka": bool(API_KEY)}

@app.post("/api/kur")
def kur_baslat():
    if _kurulum["surec"] is not None and _kurulum["surec"].poll() is None: return {"durum": "zaten çalışıyor"}
    _kurulum["surec"] = subprocess.Popen([sys.executable, os.path.join(BURASI, "kur.py")],
                                         stdout=open(_kurulum["log"], "w"), stderr=subprocess.STDOUT)
    return {"durum": "başladı"}

app.mount("/static", StaticFiles(directory=os.path.join(BURASI, "static")), name="static")

@app.get("/")
def ana(): return FileResponse(os.path.join(BURASI, "static", "index.html"))
