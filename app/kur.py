#!/usr/bin/env python3
"""Tüm kaynakları yerel veritabanına indirir. Devam ettirilebilir: yarıda kesilirse kaldığı yerden sürer.
Kullanım:
  python kur.py                    # her şey
  python kur.py --asama meal,tefsir --sureler 1,68,112
Aşamalar: arapca, morfoloji, lane, meal, tefsir, hadis, eslestir
"""
import argparse, concurrent.futures as cf, glob, html, json, os, re, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(__file__))
import veri as V

def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)

def durum(c, asama, bilgi):
    with V._kilit:
        c.execute("INSERT OR REPLACE INTO durum(asama,bilgi,tarih) VALUES(?,?,datetime('now'))", (asama, bilgi)); c.commit()

# ---------------- Lane's Lexicon ----------------
def lane_html(xml):
    t = re.sub(r"<orth[^>]*>\*</orth>", "", xml)
    t = re.sub(r'<(?:foreign|orth)[^>]*lang="ar"[^>]*>(.*?)</(?:foreign|orth)>',
               lambda m: f'<span class="ar">{re.sub(r"[0-9]", "", V.bw2ar(html.unescape(m[1])))}</span>', t, flags=re.S)
    t = re.sub(r'<hi rend="ital"[^>]*>(.*?)</hi>', r"<i>\1</i>", t, flags=re.S)
    t = re.sub(r"<entryFree[^>]*>", "<p>", t).replace("</entryFree>", "</p>")
    t = re.sub(r"<(?!/?(?:p|i|span)\b)[^>]+>", "", t)
    t = re.sub(r"-b\d+-", "", t).replace("―", " — ")
    return re.sub(r"\s+", " ", t).strip()

def lane_kur(c):
    if c.execute("SELECT 1 FROM lane LIMIT 1").fetchone(): log("lane: zaten var"); return
    d = tempfile.mkdtemp()
    log("lane: indiriliyor (git)")
    subprocess.run(["git", "clone", "-q", "--depth", "1", "https://github.com/laneslexicon/xml", d + "/lane"], check=True)
    satir = []
    for f in sorted(glob.glob(d + "/lane/*.xml")):
        t = open(f, encoding="utf-8").read()
        for m in re.finditer(r'<div2 n="([^"]*)" type="root"[^>]*>(.*?)</div2>', t, re.S):
            bw = html.unescape(m[1]); h = lane_html(m[2])
            if not h: continue
            for alt in set(re.split(r"\s*(?:or|and|,|:|&amp;c\.|&c\.)\s*", bw)):
                if alt.strip(): satir.append((V.lane_anahtari(alt), bw, h))
    with V._kilit:
        c.executemany("INSERT INTO lane VALUES(?,?,?)", satir); c.commit()
    log(f"lane: {len(satir)} kök"); durum(c, "lane", f"{len(satir)} kök")

# ---------------- Hadis ↔ ayet eşleştirme ----------------
def eslestir(c, n=4, esik=300):
    """Ayetin Arapça metninden ardışık n kelimelik parçalar hadis metinlerinde aranır."""
    log("eşleştirme: hadis dizini kuruluyor")
    dizin = {}
    hadisler = c.execute("SELECT kol,no,metin FROM hadis WHERE dil='ara'").fetchall()
    for i, h in enumerate(hadisler):
        k = V.sadelestir(h["metin"]).split()
        for j in range(len(k) - n + 1):
            dizin.setdefault(" ".join(k[j:j+n]), set()).add(i)
    ayetler = c.execute("SELECT s,a,metin FROM ayet WHERE kaynak='ara-quranuthmanihaf'").fetchall()
    sonuc = []
    for ay in ayetler:
        k = V.sadelestir(ay["metin"]).split()
        parcalar = [" ".join(k[j:j+n]) for j in range(len(k) - n + 1)] if len(k) >= n else []
        sayac = {}
        for p in parcalar:
            eşler = dizin.get(p, ())
            if len(eşler) > esik: continue  # çok yaygın kalıp (besmele vb.)
            for i in eşler: sayac[i] = sayac.get(i, 0) + 1
        for i, say in sayac.items():
            h = hadisler[i]
            sonuc.append((h["kol"], h["no"], ay["s"], ay["a"], round(say / max(1, len(parcalar)), 3)))
    with V._kilit:
        c.execute("DELETE FROM hadis_ayet")
        c.executemany("INSERT OR REPLACE INTO hadis_ayet VALUES(?,?,?,?,?)", sonuc); c.commit()
    log(f"eşleştirme: {len(sonuc)} hadis-ayet bağlantısı"); durum(c, "eslestir", f"{len(sonuc)} bağlantı")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asama", default="arapca,morfoloji,lane,meal,tefsir,hadis,eslestir")
    ap.add_argument("--sureler", default="1-114")
    ap.add_argument("--meal-dilleri", default="", help="örn: Turkish,English,Arabic (boş = hepsi)")
    ap.add_argument("--paralel", type=int, default=24)
    a = ap.parse_args()
    asamalar = a.asama.split(",")
    sureler = []
    for p in a.sureler.split(","):
        if "-" in p: x, y = map(int, p.split("-")); sureler += range(x, y + 1)
        else: sureler.append(int(p))
    c = V.baglan(); V.sema_kur(c)

    if "arapca" in asamalar:
        for k in V.KIRAATLER: log("arapça:", k, V.arapca_yukle(c, k))
        V.arapca_yukle(c, "ara-quransimple"); durum(c, "arapca", "tamam")
    if "morfoloji" in asamalar:
        V.morfoloji_yukle(c); log("morfoloji: tamam"); durum(c, "morfoloji", "tamam")
    if "lane" in asamalar: lane_kur(c)
    if "meal" in asamalar:
        V.meal_kaynaklari_yukle(c)
        q = "SELECT id FROM meal_kaynak"
        diller = [d for d in a.meal_dilleri.split(",") if d]
        ids = [r[0] for r in c.execute(q).fetchall() if not diller or
               c.execute("SELECT dil FROM meal_kaynak WHERE id=?", (r[0],)).fetchone()[0] in diller]
        isler = [(i, s) for i in ids for s in sureler]
        log(f"meal: {len(ids)} meal × {len(sureler)} sure = {len(isler)} dosya")
        biten = 0
        with cf.ThreadPoolExecutor(a.paralel) as ex:
            for _ in ex.map(lambda x: V.meal_sure_yukle(c, *x), isler):
                biten += 1
                if biten % 500 == 0: log(f"meal: {biten}/{len(isler)}")
        durum(c, "meal", f"{len(ids)} meal")
    if "tefsir" in asamalar:
        V.tefsir_kaynaklari_yukle(c)
        slugs = [r[0] for r in c.execute("SELECT slug FROM tefsir_kaynak").fetchall()]
        isler = [(sl, s) for sl in slugs for s in sureler]
        log(f"tefsir: {len(slugs)} tefsir × {len(sureler)} sure = {len(isler)} dosya")
        biten = 0
        with cf.ThreadPoolExecutor(a.paralel) as ex:
            for _ in ex.map(lambda x: V.tefsir_sure_yukle(c, *x), isler):
                biten += 1
                if biten % 500 == 0: log(f"tefsir: {biten}/{len(isler)}")
        durum(c, "tefsir", f"{len(slugs)} tefsir")
    if "hadis" in asamalar:
        for kol in V.HADIS_KOLLAR:
            for dil in ("ara", "tur", "eng"):
                log("hadis:", dil, kol, V.hadis_kol_yukle(c, kol, dil))
        for kol in V.HADIS_EK: log("hadis (ek):", kol, V.hadis_json_yukle(c, kol))
        durum(c, "hadis", "tamam")
    if "eslestir" in asamalar: eslestir(c)
    log("BİTTİ")

if __name__ == "__main__":
    main()
