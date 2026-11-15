"""Dedplay Kur'an Çalışma — API sunucusu."""
import concurrent.futures as cf, json, os, re, subprocess, sys, threading, urllib.request, urllib.parse
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import FileResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
sys.path.insert(0, os.path.dirname(__file__))
import veri as V, kitap, yz, hashlib

app = FastAPI(title="Dedplay Kur'ân-ı Kerîm Çalışma")
BURASI = os.path.dirname(os.path.abspath(__file__))
c = V.baglan(); V.sema_kur(c)
c.executescript("""
CREATE TABLE IF NOT EXISTS yalin_meal(s INT, a INT, metin TEXT, dipnotlar TEXT, durum TEXT DEFAULT 'taslak', guncelleme TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(s,a));
CREATE TABLE IF NOT EXISTS sure_bilgi(s INT PRIMARY KEY, ad_ar TEXT, nuzul TEXT);
""")
for _sutun in ("metin_osm TEXT", "dipnotlar_osm TEXT"):
    try: c.execute(f"ALTER TABLE yalin_meal ADD COLUMN {_sutun}"); c.commit()
    except Exception: pass
VARSAYILAN_MEAL = os.environ.get("KURAN_MEAL", "tur-elmalilihamdiya")
TEMEL_MEAL = os.environ.get("KURAN_TEMEL_MEAL", "zahir")   # yalın meali henüz olmayan ayetlerde gösterilen meal

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
    if not c.execute("SELECT 1 FROM durum WHERE asama='yalin_kaldir'").fetchone():   # bir kerelik: eski taslak/onaylı kayıtlar silinir; meal yalnız Zahir'in meali
        with V._kilit:
            c.execute("DELETE FROM yalin_meal"); c.execute("INSERT OR REPLACE INTO durum(asama, bilgi) VALUES('yalin_kaldir','')"); c.commit()
    ozel_yukle(); osm_eksikleri_tamamla()
    # tüm külliyat henüz inmediyse arka planda indirmeye başla
    if os.environ.get("KURAN_OTOMATIK_INDIR", "1") == "1" and not c.execute("SELECT 1 FROM durum WHERE asama='eslestir'").fetchone():
        kur_baslat()
threading.Thread(target=lambda: (__import__("time").sleep(2), ilk_kurulum()), daemon=True).start()

# ---------------- Osmanlıca çevirici (Zahir'in osmanlica-cevirici servisi) ----------------
OSM_URL = os.environ.get("OSM_CEVIRICI_URL", "http://host.docker.internal:8089").rstrip("/")
_osm_kilit = threading.Lock()

def osm_cevir_toplu(metinler):
    """Metin listesini çeviriciye tek iş olarak gönderir; aynı sırayla Osmanlıca döner. Dipnot işaretleri [n] korunur."""
    import time as _t, urllib.parse as _up
    if not metinler: return []
    ayrac = "\n"
    giris = ayrac.join(re.sub(r"\[(\d+)\]", lambda m: f" QQ{m.group(1)} ", x.replace("\n", " ")) for x in metinler)
    veri = _up.urlencode({"text": giris, "turkce": "false"}).encode()
    with urllib.request.urlopen(urllib.request.Request(OSM_URL + "/api/upload-text", data=veri, method="POST"), timeout=60) as r:
        is_id = json.loads(r.read())["job_id"]
    for _ in range(600):
        with urllib.request.urlopen(f"{OSM_URL}/api/status/{is_id}", timeout=30) as r: d = json.loads(r.read())
        if d.get("ready"): break
        if d.get("error"): raise RuntimeError("çevirici: " + str(d["error"]))
        _t.sleep(1)
    with urllib.request.urlopen(f"{OSM_URL}/api/download/{is_id}", timeout=60) as r: cikti = r.read().decode("utf-8")
    satirlar_ = [x for x in cikti.replace("\r", "").split("\n")]
    if len(satirlar_) < len(metinler): raise RuntimeError(f"çevirici {len(metinler)} satır yerine {len(satirlar_)} döndürdü")
    hane = "٠١٢٣٤٥٦٧٨٩"
    def geri(o):
        o = re.sub(r"\s*ق([١٢٣٤٥٦٧٨٩٠]+)\s*", lambda m: "[" + "".join(str(hane.index(ch)) for ch in m.group(1)) + "] ", o)
        return re.sub(r"\]\s+([.،؛:!؟,])", r"]\1", o).replace(" [", "[").strip()
    return [geri(x) for x in satirlar_[:len(metinler)]]

def osm_eksikleri_tamamla():
    """Osmanlıcası olmayan yalın meal ayetlerini çeviriciden geçirir (meal + dipnotlar)."""
    with _osm_kilit:
        eksik = satirlar("SELECT s, a, metin, dipnotlar FROM yalin_meal WHERE metin_osm IS NULL OR metin_osm=''")
        if not eksik: return 0
        try:
            metinler = []
            for r in eksik: metinler += [r["metin"]] + json.loads(r["dipnotlar"] or "[]")
            sonuc = osm_cevir_toplu(metinler)
        except Exception as e:
            print("Osmanlıca çevirici kullanılamadı:", e, flush=True); return 0
        i = 0
        with V._kilit:
            for r in eksik:
                n = len(json.loads(r["dipnotlar"] or "[]"))
                c.execute("UPDATE yalin_meal SET metin_osm=?, dipnotlar_osm=? WHERE s=? AND a=?",
                          (sonuc[i], json.dumps(sonuc[i + 1:i + 1 + n], ensure_ascii=False), r["s"], r["a"]))
                i += 1 + n
            c.commit()
        print(f"Osmanlıca çevirici: {len(eksik)} ayet çevrildi", flush=True)
        return len(eksik)

# ---------------- Özel mealler (sunucudaki /veri/ozel klasörü; GitHub'a girmez) ----------------
OZEL_KLASOR = os.path.join(os.path.dirname(os.path.abspath(V.DB_YOL)), "ozel")
c.execute("CREATE TABLE IF NOT EXISTS ozel_sayfa(id TEXT, s INT, a INT, sayfa INT, PRIMARY KEY(id,s,a))")
c.execute("CREATE TABLE IF NOT EXISTS ozel_meal(id TEXT PRIMARY KEY, pdf TEXT, ozet TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS ozel_kesit(id TEXT, s INT, a INT, kesit TEXT, PRIMARY KEY(id,s,a))")
c.execute("CREATE TABLE IF NOT EXISTS meal_dipnot(id TEXT, s INT, a INT, dipnotlar TEXT, PRIMARY KEY(id,s,a))")

DEPO_MEALLER = os.path.join(BURASI, "..", "mealler")

RESIM = "\u27e6resim\u27e7"   # resimli meallerde metin yerine konan işaret

def ozel_yukle():
    """Depodaki mealler/*.json ve sunucudaki /veri/ozel/*.json → meal tablosuna (içerik değişince yeniden).
    Biçim: {"id","dil","yazar","yon","pdf","ayetler":{"1":{"1":{"metin","sayfa"}}}}"""
    dosyalar = []
    for k in (DEPO_MEALLER, OZEL_KLASOR):
        if os.path.isdir(k): dosyalar += [os.path.join(k, f) for f in sorted(os.listdir(k)) if f.endswith(".json")]
    for yol in dosyalar:
        ad = os.path.basename(yol)
        ham = open(yol, "rb").read(); ozet = hashlib.sha1(ham).hexdigest()
        d = json.loads(ham); mid = d["id"]
        if c.execute("SELECT 1 FROM ozel_meal WHERE id=? AND ozet=?", (mid, ozet)).fetchone(): continue
        with V._kilit:
            for tablo in ("meal", "meal_sure", "ozel_sayfa", "meal_dipnot", "ozel_kesit"): c.execute(f"DELETE FROM {tablo} WHERE id=?", (mid,))
            c.execute("INSERT OR REPLACE INTO meal_kaynak VALUES(?,?,?,?)", (mid, d.get("dil", "Ottoman"), d.get("yazar", mid), d.get("yon", "rtl")))
            for s, ayetler in d["ayetler"].items():
                for a, x in ayetler.items():
                    if x.get("kesit"):  # resimli meal: metin yerine kitaptan kesilmiş ayet resmi
                        c.execute("INSERT OR REPLACE INTO ozel_kesit VALUES(?,?,?,?)", (mid, int(s), int(a), json.dumps(x["kesit"])))
                        c.execute("INSERT OR REPLACE INTO meal VALUES(?,?,?,?)", (mid, int(s), int(a), RESIM))
                    elif x.get("metin"): c.execute("INSERT OR REPLACE INTO meal VALUES(?,?,?,?)", (mid, int(s), int(a), x["metin"]))
                    if x.get("sayfa"): c.execute("INSERT OR REPLACE INTO ozel_sayfa VALUES(?,?,?,?)", (mid, int(s), int(a), int(x["sayfa"])))
                    if x.get("dipnotlar"): c.execute("INSERT OR REPLACE INTO meal_dipnot VALUES(?,?,?,?)", (mid, int(s), int(a), json.dumps(x["dipnotlar"], ensure_ascii=False)))
            c.executemany("INSERT OR REPLACE INTO meal_sure VALUES(?,?)", [(mid, s) for s in range(1, 115)])  # internetten aranmasın
            c.execute("INSERT OR REPLACE INTO ozel_meal VALUES(?,?,?)", (mid, d.get("pdf"), ozet)); c.commit()
        print(f"özel meal yüklendi: {mid} ({ad})", flush=True)

@app.get("/api/ozel/{mid}/sayfa/{n}.png")
def ozel_sayfa(mid: str, n: int):
    """Özel mealin kaynak PDF'inden sayfa görüntüsü (önbellekli)."""
    r = tek("SELECT pdf FROM ozel_meal WHERE id=?", mid)
    if not r or not r["pdf"]: raise HTTPException(404, "Bu meal için PDF tanımlı değil.")
    pdf = os.path.join(OZEL_KLASOR, os.path.basename(r["pdf"]))
    if not os.path.exists(pdf): raise HTTPException(404, f"PDF bulunamadı: {os.path.basename(pdf)} dosyasını {OZEL_KLASOR} içine koyun.")
    onb = os.path.join(OZEL_KLASOR, "onbellek"); os.makedirs(onb, exist_ok=True)
    hedef = os.path.join(onb, f"{mid}_{n:04d}")
    if not os.path.exists(hedef + ".png"):
        subprocess.run(["pdftoppm", "-f", str(n), "-l", str(n), "-r", "150", "-png", "-singlefile", pdf, hedef], check=True, timeout=60)
    return FileResponse(hedef + ".png", media_type="image/png")

def _pdf_sayfa(mid, pdf, n, dpi=200):
    onb = os.path.join(OZEL_KLASOR, "onbellek"); os.makedirs(onb, exist_ok=True)
    hedef = os.path.join(onb, f"{mid}_{dpi}_{n:04d}")
    if not os.path.exists(hedef + ".png"):
        subprocess.run(["pdftoppm", "-f", str(n), "-l", str(n), "-r", str(dpi), "-gray", "-png", "-singlefile", pdf, hedef], check=True, timeout=60)
    return hedef + ".png"

@app.get("/api/resim/{mid}/{s}/{a}.png")
def ayet_resmi(mid: str, s: int, a: int):
    """Resimli mealde ayetin kitaptan kesilmiş görüntüsü (kesit: [sayfa, x0, y0, x1, y1] oranları, sağa yaslı alt alta)."""
    hazir = os.path.join(DEPO_MEALLER, os.path.basename(mid), f"{s:03d}_{a:03d}.webp")   # depoda hazır kesilmiş resim (PDF gerekmez)
    if os.path.exists(hazir): return FileResponse(hazir, media_type="image/webp", headers={"Cache-Control": "max-age=604800"})
    r = tek("SELECT pdf FROM ozel_meal WHERE id=?", mid); k = tek("SELECT kesit FROM ozel_kesit WHERE id=? AND s=? AND a=?", mid, s, a)
    if not r or not k: raise HTTPException(404, "Bu ayetin resmi yok.")
    pdf = os.path.join(OZEL_KLASOR, os.path.basename(r["pdf"] or ""))
    if not os.path.exists(pdf): raise HTTPException(404, f"PDF bulunamadı: {os.path.basename(pdf)} dosyasını sunucuda {OZEL_KLASOR} içine koyun.")
    onb = os.path.join(OZEL_KLASOR, "onbellek", mid); os.makedirs(onb, exist_ok=True)
    hedef = os.path.join(onb, f"{s:03d}_{a:03d}_{hashlib.sha1(k['kesit'].encode()).hexdigest()[:8]}.png")
    if not os.path.exists(hedef):
        from PIL import Image
        parca = []
        for p, x0, y0, x1, y1 in json.loads(k["kesit"]):
            im = Image.open(_pdf_sayfa(mid, pdf, p)).convert("L"); W, H = im.size
            parca.append(im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))))
        w = max(x.width for x in parca); h = sum(x.height for x in parca)
        out = Image.new("L", (w, h), 255); y = 0
        for x in parca: out.paste(x, (w - x.width, y)); y += x.height
        out.save(hedef, optimize=True)
    return FileResponse(hedef, media_type="image/png", headers={"Cache-Control": "max-age=604800"})

# ---------------- Meal dosyası içe aktarma ----------------
c.execute("CREATE TABLE IF NOT EXISTS yuklenen_dosya(ad TEXT, ozet TEXT, tarih TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(ad, ozet))")

def meal_json_yukle(d, durum_varsayilan="onayli"):
    """{"sure":68,"ayetler":[{"a":1,"meal":"...[1]...","dipnotlar":["..."]}]} biçimindeki dosyayı içeri alır."""
    s = int(d["sure"]); n = 0
    with V._kilit:
        for x in d["ayetler"]:
            if not (x.get("meal") or "").strip(): continue
            c.execute("INSERT OR REPLACE INTO yalin_meal(s,a,metin,dipnotlar,durum,guncelleme,metin_osm,dipnotlar_osm) VALUES(?,?,?,?,?,datetime('now'),?,?)",
                      (s, int(x["a"]), x["meal"].strip(), json.dumps(x.get("dipnotlar", []), ensure_ascii=False), x.get("durum", durum_varsayilan),
                       (x.get("meal_osm") or "").strip() or None, json.dumps(x["dipnotlar_osm"], ensure_ascii=False) if x.get("dipnotlar_osm") is not None else None))
            n += 1
        c.commit()
    return n

# ---------------- Sureler / ayetler ----------------
@app.get("/api/sureler")
def sureler():
    notsay = {r["s"]: r["n"] for r in satirlar("SELECT s, count(*) n FROM notlar GROUP BY s")}
    yalin = {r["s"]: r["n"] for r in satirlar("SELECT s, count(*) n FROM yalin_meal GROUP BY s")}
    bilgi = {r["s"]: r for r in satirlar("SELECT * FROM sure_bilgi")}
    return [{"s": i + 1, "ad": V.SURE_ADLARI[i], "ad_ar": bilgi.get(i + 1, {}).get("ad_ar", ""), "nuzul": bilgi.get(i + 1, {}).get("nuzul", ""),
             "ayet": V.AYET_SAYILARI[i], "sira": V.NUZUL_SIRASI[i], "not": notsay.get(i + 1, 0), "yalin": yalin.get(i + 1, 0)} for i in range(114)]

def temel_dipnot(s, a=None):
    """Temel mealin (ve Osmanlıcasının) dipnotları: {a: (dipnotlar_json, dipnotlar_osm_json)}"""
    q = "SELECT id, a, dipnotlar FROM meal_dipnot WHERE id IN (?,?) AND s=?" + (" AND a=?" if a else "")
    d = {}
    for r in satirlar(q, TEMEL_MEAL, TEMEL_MEAL + "-osm", s, *([a] if a else [])):
        x = d.setdefault(r["a"], ["[]", "[]"]); x[0 if r["id"] == TEMEL_MEAL else 1] = r["dipnotlar"]
    return d

@app.get("/api/sure/{s}")
def sure(s: int, meal: str = ""):
    """Okuma görünümü: Arapça + yalın meal (ana metin). meal verilirse karşılaştırma meali de eklenir."""
    V.arapca_yukle(c)
    if meal: V.meal_sure_yukle(c, meal, s)
    ar = {r["a"]: r["metin"] for r in satirlar("SELECT a, metin FROM ayet WHERE s=? AND kaynak='ara-quranuthmanihaf'", s)}
    ml = {r["a"]: r["metin"] for r in satirlar("SELECT a, metin FROM meal WHERE id=? AND s=?", meal, s)} if meal else {}
    yl = {r["a"]: r for r in satirlar("SELECT a, metin, dipnotlar, durum, metin_osm, dipnotlar_osm FROM yalin_meal WHERE s=?", s)}
    tm = {r["a"]: r["metin"] for r in satirlar("SELECT a, metin FROM meal WHERE id=? AND s=?", TEMEL_MEAL, s)}
    tm_osm = {r["a"]: r["metin"] for r in satirlar("SELECT a, metin FROM meal WHERE id=? AND s=?", TEMEL_MEAL + "-osm", s)}
    tdn = temel_dipnot(s)
    for a in range(1, V.AYET_SAYILARI[s - 1] + 1):
        if a not in yl:
            if a in tm: yl[a] = {"metin": tm[a], "dipnotlar": tdn.get(a, ["[]"])[0], "durum": "temel", "metin_osm": tm_osm.get(a), "dipnotlar_osm": tdn.get(a, ["[]", "[]"])[1]}
            elif a - 1 in tm or (a - 1 in yl and yl[a - 1].get("durum") in ("temel", "birlesik")):
                yl[a] = {"metin": "", "dipnotlar": "[]", "durum": "birlesik"}
    ns = {r["a"]: r["n"] for r in satirlar("SELECT a, count(*) n FROM notlar WHERE s=? GROUP BY a", s)}
    yon = (tek("SELECT yon FROM meal_kaynak WHERE id=?", meal) or {}).get("yon", "ltr") if meal else "ltr"
    sayfa = {r["a"]: r["sayfa"] for r in satirlar("SELECT a, sayfa FROM ozel_sayfa WHERE id=? AND s=?", meal, s)} if meal else {}
    resimli = any(v == RESIM for v in ml.values())
    if resimli: ml = {a_: f"/api/resim/{meal}/{s}/{a_}.png" for a_ in ml}
    return {"s": s, "ad": V.SURE_ADLARI[s - 1], "meal_yon": yon, "meal_sayfa": sayfa, "meal_resim": resimli, "ayetler": [
        {"a": a, "arapca": ar.get(a, ""), "meal": ml.get(a, ""), "yalin": (yl.get(a) or {}).get("metin"),
         "dipnotlar": json.loads((yl.get(a) or {}).get("dipnotlar") or "[]"),
         "yalin_osm": (yl.get(a) or {}).get("metin_osm"), "dipnotlar_osm": json.loads((yl.get(a) or {}).get("dipnotlar_osm") or "[]"),
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
            "yalin": tek("SELECT * FROM yalin_meal WHERE s=? AND a=?", s, a) or
                     ({"metin": r["metin"], "dipnotlar": temel_dipnot(s, a).get(a, ["[]"])[0], "durum": "temel", "metin_osm": (tek("SELECT metin FROM meal WHERE id=? AND s=? AND a=?", TEMEL_MEAL + "-osm", s, a) or {}).get("metin"), "dipnotlar_osm": temel_dipnot(s, a).get(a, ["[]", "[]"])[1]}
                      if (r := tek("SELECT metin FROM meal WHERE id=? AND s=? AND a=?", TEMEL_MEAL, s, a)) else None),
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
        r["yazar"] = V.YAZAR_ADI.get(r["id"], r["yazar"])
        if r["metin"] == RESIM: r["metin"] = ""; r["resim"] = f"/api/resim/{r['id']}/{s}/{a}.png"
        sp = tek("SELECT sayfa FROM ozel_sayfa WHERE id=? AND s=? AND a=?", r["id"], s, a)
        if sp: r["sayfa"] = sp["sayfa"]
        sonuc.setdefault(r["dil"], []).append(r)
    sira = ["Turkish", "Ottoman", "Arabic", "English", "Azerbaijani", "Persian", "Urdu", "French", "German", "Bosnian"]
    return [{"dil": d, "mealler": sonuc[d]} for d in sorted(sonuc, key=lambda d: (sira.index(d) if d in sira else 99, d))]

@app.get("/api/meal-kaynaklari")
def meal_kaynaklari():
    V.meal_kaynaklari_yukle(c)
    r = satirlar("SELECT * FROM meal_kaynak WHERE id NOT LIKE '%-la' ORDER BY dil, yazar")
    for x in r: x["yazar"] = V.YAZAR_ADI.get(x["id"], x["yazar"])
    return r

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
        r = tek("SELECT metin FROM yalin_meal WHERE s=? AND a=?", g["s"], g["a"]) or tek("SELECT metin FROM meal WHERE id=? AND s=? AND a=?", meal, g["s"], g["a"])
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
    threading.Thread(target=osm_eksikleri_tamamla, daemon=True).start()   # Türkçe değişti → Osmanlıcası yeniden
    return tek("SELECT * FROM yalin_meal WHERE s=? AND a=?", s, a)

@app.get("/api/yalin/disa-aktar/{s}")
def yalin_disa(s: int):
    """İnceleme için sure dosyası: Arapça + mevcut meal + dipnotlar + durum."""
    ar = {r["a"]: r["metin"] for r in satirlar("SELECT a, metin FROM ayet WHERE s=? AND kaynak='ara-quranuthmanihaf'", s)}
    yl = {r["a"]: r for r in satirlar("SELECT * FROM yalin_meal WHERE s=?", s)}
    d = {"sure": s, "ad": V.SURE_ADLARI[s - 1], "ayetler": [
        {"a": a, "arapca": ar.get(a, ""), "meal": (yl.get(a) or {}).get("metin", ""),
         "dipnotlar": json.loads((yl.get(a) or {}).get("dipnotlar") or "[]"),
         "yalin_osm": (yl.get(a) or {}).get("metin_osm"), "dipnotlar_osm": json.loads((yl.get(a) or {}).get("dipnotlar_osm") or "[]"), "durum": (yl.get(a) or {}).get("durum", "yok")}
        for a in range(1, V.AYET_SAYILARI[s - 1] + 1)]}
    return Response(json.dumps(d, ensure_ascii=False, indent=1), media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename=\"sure_{s:03d}.json\"; filename*=UTF-8''{urllib.parse.quote(f'sure_{s:03d}_{V.SURE_ADLARI[s-1]}.json')}"})

@app.post("/api/yalin/ice-aktar")
def yalin_ice(d: dict = Body(...)):
    return {"ayet": meal_json_yukle(d)}

@app.get("/api/kitap.epub")
def kitap_indir(sureler: str = "", sadece_onayli: bool = False, arapca: bool = False, temel: bool = True, dil: str = "tr"):
    try: secili = V.sure_listesi_coz(sureler) if sureler.strip() else (list(range(1, 115)) if temel else sorted({r["s"] for r in satirlar("SELECT DISTINCT s FROM yalin_meal")}))
    except ValueError as e: raise HTTPException(400, str(e))
    bilgi = {r["s"]: r["ad_ar"] for r in satirlar("SELECT * FROM sure_bilgi")}
    kitap_s = []
    for s in secili:
        ar = {r["a"]: r["metin"] for r in satirlar("SELECT a, metin FROM ayet WHERE s=? AND kaynak='ara-quranuthmanihaf'", s)}
        yl = {r["a"]: r for r in satirlar("SELECT * FROM yalin_meal WHERE s=?" + (" AND durum='onayli'" if sadece_onayli else ""), s)}
        if temel and not sadece_onayli:
            osm_t = {r["a"]: r["metin"] for r in satirlar("SELECT a, metin FROM meal WHERE id=? AND s=?", TEMEL_MEAL + "-osm", s)}
            tdn = temel_dipnot(s)
            for r in satirlar("SELECT a, metin FROM meal WHERE id=? AND s=?", TEMEL_MEAL, s):
                yl.setdefault(r["a"], {"metin": r["metin"], "dipnotlar": tdn.get(r["a"], ["[]"])[0], "metin_osm": osm_t.get(r["a"]), "dipnotlar_osm": tdn.get(r["a"], ["[]", "[]"])[1]})
        if not yl: continue
        ayetler, dipnot, no = [], {}, 0
        for a in range(1, V.AYET_SAYILARI[s - 1] + 1):
            if a not in yl: continue
            if dil == "osm":
                if not yl[a].get("metin_osm"): continue
                metin = yl[a]["metin_osm"]; notlar_ = json.loads(yl[a].get("dipnotlar_osm") or "[]")
            else:
                metin = yl[a]["metin"]; notlar_ = json.loads(yl[a]["dipnotlar"] or "[]")
            def numarala(m):  # ayet içi [1],[2] → sure geneli sıra numarası
                nonlocal no
                i = int(m[1]) - 1
                if i < len(notlar_): no += 1; dipnot[str(no)] = notlar_[i]; return f"[{no}]"
                return ""
            metin = re.sub(r"\[(\d+)\]", numarala, metin)
            ayetler.append({"a": a, "arapca": ar.get(a, ""), "meal": metin})
        kitap_s.append({"s": s, "ad": V.SURE_ADLARI[s - 1], "ad_ar": bilgi.get(s, ""), "ayetler": ayetler, "dipnotlar": dipnot})
    kitap_s = [k for k in kitap_s if k["ayetler"]]
    if not kitap_s: raise HTTPException(404, "Kitaba girecek meal yok (Osmanlıca için: denetlenmiş sure yok).")
    ad = "Kuran_Yalin_Meal.epub" if len(kitap_s) == 114 else "Yalin_Meal_" + "-".join(str(x["s"]) for x in kitap_s)[:60] + ".epub"
    if dil == "osm": ad = ad.replace(".epub", "_Osmanlica.epub")
    return Response(kitap.epub_yap(kitap_s, arapca=arapca, osmanlica=(dil == "osm")), media_type="application/epub+zip", headers={"Content-Disposition": f'attachment; filename="{ad}"'})

# ---------------- Yapay zekâ: görüş analizi, yalın meal önerisi, Lane çevirisi ----------------
def claude(sistem, mesaj, max_tokens=4000):
    if not yz.hazir(): raise HTTPException(400, "Yapay zekâ tanımlı değil (docker-compose.yml içinde YZ_ANAHTAR).")
    try: return yz.sohbet(sistem, mesaj, max_tokens)
    except yz.KotaDoldu: raise HTTPException(429, "Yapay zekânın günlük ücretsiz kotası doldu; yarın tekrar deneyin.")
    except RuntimeError as e: raise HTTPException(502, str(e))

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
        r = satirlar("SELECT s, a, metin FROM yalin_meal WHERE metin LIKE ? ORDER BY s, a LIMIT ?", f"%{q}%", limit)
        if meal:
            gorulen = {(x["s"], x["a"]) for x in r}
            r += [x for x in satirlar("SELECT s, a, metin FROM meal WHERE id=? AND metin LIKE ? ORDER BY s, a LIMIT ?", meal, f"%{q}%", limit)
                  if (x["s"], x["a"]) not in gorulen]
    for x in r: x["sure"] = V.SURE_ADLARI[x["s"] - 1]
    return r

# ---------------- Kaynak durumu / toplu indirme ----------------
_kurulum = {"surec": None, "log": os.path.join(os.path.dirname(V.DB_YOL), "kurulum.log")}

@app.get("/api/ayarlar")
def ayarlar(): return {"yapay_zeka": yz.hazir(), **yz.bilgi()}

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
            "db_mb": round(os.path.getsize(V.DB_YOL) / 1e6), "kurulum_calisiyor": calisiyor, "log": log, "yapay_zeka": yz.hazir()}

@app.post("/api/kur")
def kur_baslat():
    if _kurulum["surec"] is not None and _kurulum["surec"].poll() is None: return {"durum": "zaten çalışıyor"}
    _kurulum["surec"] = subprocess.Popen([sys.executable, os.path.join(BURASI, "kur.py")],
                                         stdout=open(_kurulum["log"], "w"), stderr=subprocess.STDOUT)
    return {"durum": "başladı"}

# Yapay zekâyla meal üretimi kaldırıldı: meal Zahir'in mealidir; yapay zekâ yalnız çeviri (nüzul vb.) için kullanılır.

app.mount("/static", StaticFiles(directory=os.path.join(BURASI, "static")), name="static")

@app.get("/favicon.ico")
def favicon(): return FileResponse(os.path.join(BURASI, "static", "favicon.png"), media_type="image/png")

@app.get("/")
def ana(): return FileResponse(os.path.join(BURASI, "static", "index.html"))

# ---------------- Meal karşılaştırma (yapay zekâsız): aynı / farklı tercihler ----------------
_DUR = set("ve bir bu şu o da de ki ile için gibi ne ya hem ise ama fakat çünkü artık işte en daha çok her hiç olan olarak onlar onları onların onlara onu onun ona sen seni senin sana siz sizi sizin size biz bizi bizim bize ben beni benim bana kendi şey şeyi diye ancak eğer şüphesiz muhakkak gerçekten elbette kuşkusuz doğrusu hani".split())
_TR_KUCUK = str.maketrans("İIÂÎÛ", "iıâîû")
_DUR_DIL = {
 "Dutch": set("jou je jij mij me ik ons onze uw eene den der des hen hun zich zichzelf de het een en van in is die dat niet zijn voor op met te hij zij ze wij jullie u gij hem haar hun tot aan er als maar ook dan zal zullen zult werd worden door bij uit naar om over of al wat wie waar hoe dit deze zo noch nog geen heeft hebben had was waren wordt want waarlijk voorwaar zeker".split()),
 "English": set("the a an and of to in is are was were be been for on with that this it he she they them his her their you your we our not by from as at but or which who whom will shall has have had do does did so no nor then there these those indeed verily truly unto thee thou thy ye".split()),
}

def _kelimeler(metin, dil="Turkish"):
    dur = _DUR_DIL.get(dil, _DUR)
    out, parantez = [], 0
    for m in re.finditer(r"[\(\)\[\]]|[^\s\(\)\[\]]+", metin):
        p = m[0]
        if p in "([": parantez += 1; continue
        if p in ")]": parantez = max(0, parantez - 1); continue
        temiz = re.sub(r"[^\wâîûçğıöşü'’]", "", p.translate(_TR_KUCUK).lower()).replace("’", "'")
        kok = re.split("'", temiz)[0]
        kok = kok.replace("â", "a").replace("î", "i").replace("û", "u")
        out.append({"t": p, "kok": kok[:5] if len(kok) > 2 and kok not in dur else "", "ek": parantez > 0})
    return out

@app.get("/api/ayet/{s}/{a}/karsilastir")
def karsilastir(s: int, a: int, dil: str = "Turkish"):
    gruplar = mealler(s, a, dil)
    liste = [m for g in gruplar for m in g["mealler"] if not m["id"].startswith("tur-latinalphabet") and not m.get("resim")]
    yalin = tek("SELECT metin FROM yalin_meal WHERE s=? AND a=?", s, a)
    if yalin and dil == "Turkish":
        liste = [{"id": "yalin", "yazar": "★ Yalın meal", "metin": re.sub(r"\[\d+\]", "", yalin["metin"])}] + liste
    gorulen, tekil = set(), []
    for m in liste:  # aynı metnin kopyalarını ayıkla
        k = re.sub(r"\W", "", m["metin"].lower())
        if k in gorulen: continue
        gorulen.add(k); tekil.append(m)
    n = len(tekil)
    for m in tekil:
        m["kelimeler"] = _kelimeler(m["metin"], dil); m["koklar"] = {w["kok"] for w in m["kelimeler"] if w["kok"]}
    sayac = {}
    for m in tekil:
        for k in m["koklar"]: sayac.setdefault(k, []).append(m["id"])
    for m in tekil:
        for w in m["kelimeler"]:
            w["oran"] = round(len(sayac.get(w["kok"], [])) / n, 3) if w["kok"] else None
    ornek = {}
    for m in tekil:
        for w in m["kelimeler"]:
            if w["kok"]: ornek.setdefault(w["kok"], re.sub(r"[^\wâîûçğıöşüÇĞİÖŞÜÂÎÛ'’-]", "", w["t"]))
    ortak = sorted([k for k, v in sayac.items() if len(v) / n >= 0.6], key=lambda k: -len(sayac[k]))
    ayrisan = sorted([k for k, v in sayac.items() if 2 <= len(v) and len(v) / n < 0.6], key=lambda k: -len(sayac[k]))
    # benzer meal grupları (kök kümesi benzerliği, açgözlü kümeleme)
    def benzer(x, y): return len(x & y) / max(1, len(x | y))
    kalan = list(tekil); kumeler = []
    while kalan:
        m = kalan.pop(0); kume = [m]
        for o in kalan[:]:
            if benzer(m["koklar"], o["koklar"]) >= 0.45: kume.append(o); kalan.remove(o)
        kumeler.append([x["id"] for x in kume])
    for m in tekil: m.pop("koklar")
    return {"sayi": n, "mealler": tekil,
            "ortak": [{"kok": k, "ornek": ornek[k], "sayi": len(sayac[k])} for k in ortak],
            "ayrisan": [{"kok": k, "ornek": ornek[k], "sayi": len(sayac[k]), "mealler": sayac[k]} for k in ayrisan],
            "gruplar": kumeler}


# ---------------- İniş: nerede/ne zaman indi, sebeb-i nüzûl ----------------
_NUZUL_TR = re.compile(r"(n[üuû]z[uûü]l|nazil ol|hakkında in|üzerine in|indirildi[ğg]i|bu âyet[^.]{0,40}(indi|nazil))", re.I)
_SURE_BASI = re.compile(r"\((Mekke|Medine)[’']?de inmiştir\. ?\d+ âyettir\)", re.I)
TR_ESBAB = [("turkish-tafsir-as-saadi-turkish", "Sa'dî Tefsiri (Türkçe)"), ("turkish-mokhtasar", "el-Muhtasar (Türkçe)"), ("tr-tafsir-ibne-kathir", "İbn Kesîr (Türkçe özet)")]

_NUZUL_RE = re.compile(r"(سبب\s*نزول|نزلت|أنزلت|نزل(?:ت)?\s+(?:هذه|فيه|في)|فأنزل\s+الله)")

@app.get("/api/ayet/{s}/{a}/inis")
def inis(s: int, a: int):
    bilgi = tek("SELECT * FROM sure_bilgi WHERE s=?", s) or {}
    sonuc = {"sure": V.SURE_ADLARI[s - 1], "yer": {"Mecca": "Mekke", "Medina": "Medine", "Madina": "Medine"}.get(bilgi.get("nuzul"), bilgi.get("nuzul")),
             "sira": V.NUZUL_SIRASI[s - 1], "vahidi": None, "rivayetler": []}
    tefsir_sure_hazirla(s)
    r = tek("SELECT metin FROM tefsir WHERE slug='en-asbab-al-nuzul-by-al-wahidi' AND s=? AND a=?", s, a)
    if r:
        t = V.ac(r["metin"])
        # Kaynaktaki Vâhidî dosyasına Keşfü'l-Esrâr metinleri karışmış: gerçek Vâhidî kaydı ayet künyesiyle başlar ("(…) [3:61]. … informed us")
        if re.search(r"\[\d+:\d+", t[:400]): sonuc["vahidi"] = t.replace("\ufffd", "ʿ")
    for slug in V.ESBAB_TEFSIRLER:
        r = tek("SELECT metin FROM tefsir WHERE slug=? AND s=? AND a=?", slug, s, a)
        if not r: continue
        metin = re.sub(r"\s+", " ", V.ac(r["metin"])); parca, son = [], -1
        for m in _NUZUL_RE.finditer(metin):
            if m.start() < son: continue
            bas = max(0, metin.rfind(" ", 0, max(0, m.start() - 220)) + 1); bit = metin.find(" ", min(len(metin), m.end() + 380))
            bit = len(metin) if bit < 0 else bit
            parca.append(("…" if bas else "") + metin[bas:bit] + ("…" if bit < len(metin) else "")); son = bit
            if len(parca) >= 4: break
        if parca:
            yil, tur, ad = V.TEFSIR_BILGI.get(slug, (9999, "", slug))
            sonuc["rivayetler"].append({"slug": slug, "ad": ad, "yil": yil, "parcalar": parca})
    sonuc["rivayetler"].sort(key=lambda x: x["yil"])
    # Türkçe kaynaklar
    sonuc["turkce"] = []
    for slug, ad in TR_ESBAB:
        r = tek("SELECT metin FROM tefsir WHERE slug=? AND s=? AND a=?", slug, s, a)
        if not r: continue
        metin = _SURE_BASI.sub("", re.sub(r"\s+", " ", V.ac(r["metin"]))); parca, son = [], -1
        for m in _NUZUL_TR.finditer(metin):
            if m.start() < son: continue
            bas = max(0, max(metin.rfind(".", 0, m.start()), metin.rfind("!", 0, m.start()), metin.rfind("?", 0, m.start())) + 1)
            bit = metin.find(".", min(len(metin), m.end() + 420)); bit = len(metin) if bit < 0 else bit + 1
            parca.append(metin[bas:bit].strip()); son = bit
            if len(parca) >= 3: break
        if parca: sonuc["turkce"].append({"ad": ad, "parcalar": parca})
    # daha önce yapılmış Türkçe çeviri
    tr = tek("SELECT metin FROM ceviri_onbellek WHERE anahtar=?", f"nuzul:{s}:{a}")
    sonuc["ceviri"] = tr["metin"] if tr else None
    return sonuc

@app.post("/api/ayet/{s}/{a}/inis-cevir")
def inis_cevir(s: int, a: int):
    """Vâhidî ve rivâyet tefsirlerindeki iniş sebebi kısımlarını Türkçeye çevirir (bir kez, önbellekli)."""
    d = inis(s, a)
    kaynak = ([f"[Vâhidî, Esbâbü'n-Nüzûl]\n{d['vahidi']}"] if d["vahidi"] else []) + \
             [f"[{r['ad']}]\n" + "\n".join(r["parcalar"]) for r in d["rivayetler"]]
    if not kaynak: raise HTTPException(404, "Bu ayet için çevrilecek iniş sebebi rivayeti yok.")
    t = claude("Klasik Arapça ve İngilizce tefsir metinlerini sade, doğru Türkçeye çeviren bir uzmansın. Senet zincirlerini (haddesenâ… an…) kısalt: sadece ilk ravi ve sahâbîyi yaz. "
               "Yalnız ayetin nüzul sebebini (hangi olay üzerine, kim hakkında indiğini) anlatan kısımları çevir; nüzul sebebiyle ilgisi olmayan tefsir açıklamalarını atla. "
               "Kaynak adlarını başlık olarak koru. Uydurma ekleme yapma. Sonunda iki üç cümlelik 'Özet' ver: rivayetler ne diyor, ayrıştıkları nokta var mı. Metinlerde nüzul sebebi yoksa yalnızca 'Bu ayet için nüzul sebebi rivayeti yok.' yaz.",
               f"Ayet {s}:{a} ({V.SURE_ADLARI[s-1]}) için iniş sebebi rivayetleri:\n\n" + "\n\n".join(kaynak)[:24000], 3500)
    with V._kilit: c.execute("INSERT OR REPLACE INTO ceviri_onbellek VALUES(?,?)", (f"nuzul:{s}:{a}", t)); c.commit()
    return {"metin": t}
