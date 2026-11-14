#!/usr/bin/env python3
"""Bir seferlik YALIN MEAL üreticisi.

Her ayet için kök/lügat + klasik ve modern tefsirler + Türkçe ve İngilizce mealler bir pakette toplanır,
yapay zekâ Zahir'in kurallarıyla (ve onaylı Kalem 1-7 üslubuyla) en yalın Türkçe meali ve gerekli dipnotları yazar.
- Sure sure, 5'er ayetlik bölümler hâlinde; önceki ayetlerin meali bağlam olarak verilir.
- Devam ettirilebilir: meali olan ayet atlanır (onaylı veya elle düzeltilmiş ayetlere asla dokunulmaz).
- Sonuçlar 'taslak' olarak kaydedilir.

Kullanım:
  python uret.py                       # tüm Kur'an (1-114)
  python uret.py --sureler 68,112-114  # seçili sureler
  python uret.py --sureler 1 --kuru    # sadece paketi göster, yapay zekâya gönderme
"""
import argparse, concurrent.futures as cf, json, os, re, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import veri as V

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("KURAN_URETIM_MODEL") or os.environ.get("KURAN_MODEL", "claude-sonnet-4-5")

# Pakete giren kaynaklar (seçici: hem isabet hem maliyet için)
LUGAT = [("asseraj-fi-bayan-gharib-alquran", 900), ("al-muyassar-fi-al-gharib", 900)]
TEFSIR = [("ar-tafsir-al-tabari", 3000), ("al-kashshaf-al-zamakhshari", 1500), ("tafsir-al-razi", 1500),
          ("ar-tafseer-al-qurtubi", 1200), ("tafsir-al-baydawi", 900), ("ar-tafsir-ibn-kathir", 1200),
          ("ar-tafsir-al-jalalayn", 500), ("ar-tafseer-tahrir-al-tanwir", 2000), ("ar-tafsir-muyassar", 500)]
TR_MEAL = ["tur-diyanetisleri", "tur-elmalilihamdiya", "tur-elmallsadelesti", "tur-alibulac", "tur-hasanbasricanta",
           "tur-suleymanates", "tur-muhammedesed", "tur-abdulbakigolpin", "tur-celalyldrm", "tur-alifikriyavuz",
           "tur-yasarnuriozturk", "tur-edipyuksel", "tur-diyanetvakfi"]
EN_MEAL = ["eng-ummmuhammad", "eng-muhammadasad", "eng-abdelhaleem", "eng-mohammedmarmadu"]

SISTEM = """Sen Kur'an'ı Arapça aslından Türkçeye çeviren, klasik Arap dili, lügat ve tefsir usulünde derin bilgili, tarafsız bir mütercimsin.

KURALLAR (kesin):
1. Esas, kelimenin kökü ve klasik lügat anlamıdır. Tefsirler ve mealler, en doğru karşılığı bulmak ve ayrışmaları görmek içindir; hiçbir meali kopyalama.
2. Meal EN YALIN hâlde olur: akıcı, sade, doğal Türkçe. Parantez içi açıklama, ekleme, yorum YOK. Ayetin söylemediğini ekleme.
3. Modern Türkçe bir kelime kökün anlamını tam karşılamıyorsa terim Arapça bırakılır (ör. ecir, mecnun, takva gibi yerleşik kelimeler).
4. Uzun açıklama KAÇINILMAZSA ilgili kelimenin hemen arkasına [1], [2] konur, açıklama dipnota yazılır. Dipnot sadece gerçekten gerekiyorsa: çok anlamlı kök, hurûf-u mukattaa, ciddi müfessir ihtilafı, yanlış anlaşılmaya açık terim. Dipnotlar kısa, bilgi yoğun; gerektiğinde kökü ve hangi müfessirin ne dediğini anar.
5. Ayet numarası yazma. Her ayetin meali kendi içinde okunabilir olsun ama cümle bir sonraki ayete taşıyorsa doğal biçimde taşısın.
6. Allah'ın isimlerinde (Rahmân, Rahîm, Rab) yerleşik Türkçe kullanım korunur.

ÜSLUP ÖRNEĞİ (onaylanmış, Kalem 1-7):
Nûn[1]. Kaleme ve satır satır yazdıklarına[2] andolsun ki,
Sen, Rabbinin nimeti sayesinde mecnun[1] değilsin.
Ve senin için kesintisiz[1] bir ecir vardır.
Ve sen, elbette yüce bir ahlâk üzerindesin.
Yakında sen de göreceksin, onlar da görecekler:
Hanginizin aklı çelinmiş[1] olduğunu.
Şüphesiz Rabbin, kendi yolundan sapanı en iyi bilendir; doğru yolu bulanları da en iyi O bilir.
Örnek dipnot: "Memnûn kelimesi m-n-n kökünden iki anlama gelir: (1) kesilmiş, tükenmiş; (2) başa kakılmış. Celâleyn ve Taberî'nin çoğunluk rivayeti birinci anlamı tercih eder; Râzî ve Kurtubî ikinciyi de kabul eder."

ÇIKTI: Yalnızca geçerli JSON, başka hiçbir şey:
{"ayetler":[{"a":<ayet no>,"meal":"...","dipnotlar":["[1]'in metni","[2]'nin metni"]}]}
Dipnot numaraları her ayette 1'den başlar."""

def _tr_gram(etiket):
    m = {"N": "isim", "V": "fiil", "P": "edat"}
    return etiket

def ayet_paketi(c, s, a):
    ar = c.execute("SELECT metin FROM ayet WHERE s=? AND a=? AND kaynak='ara-quranuthmanihaf'", (s, a)).fetchone()
    kel = {}
    for r in c.execute("SELECT k, form, tur, etiket, kok, lemma FROM kelime WHERE s=? AND a=? ORDER BY k, p", (s, a)):
        w = kel.setdefault(r["k"], {"form": "", "kok": None, "lemma": None, "etiket": []})
        w["form"] += r["form"]; w["etiket"].append(re.sub(r"\|?(ROOT|LEM|FAM|SP):[^|]+", "", r["etiket"]).strip("|"))
        if r["kok"]: w["kok"], w["lemma"] = r["kok"], r["lemma"]
    kelimeler = "; ".join(f'{w["form"]} [kök {w["kok"]}, {w["lemma"]}, {"+".join(x for x in w["etiket"] if x)}]' if w["kok"]
                         else f'{w["form"]} [{"+".join(x for x in w["etiket"] if x)}]' for w in kel.values())
    def tef(slug, n):
        V.tefsir_sure_yukle(c, slug, s)
        r = c.execute("SELECT metin FROM tefsir WHERE slug=? AND s=? AND a=?", (slug, s, a)).fetchone()
        return re.sub(r"\s+", " ", V.ac(r["metin"]))[:n] if r else None
    out = [f"=== AYET {s}:{a} ===", f"Arapça: {ar['metin'] if ar else ''}", f"Kelimeler: {kelimeler}"]
    for slug, n in LUGAT:
        t = tef(slug, n)
        if t: out.append(f"[Garîb/lügat: {V.TEFSIR_BILGI.get(slug, (0, 0, slug))[2]}] {t}")
    for slug, n in TEFSIR:
        t = tef(slug, n)
        if t: out.append(f"[{V.TEFSIR_BILGI.get(slug, (0, 0, slug))[2]}] {t}")
    for grup, ids in (("Türkçe mealler", TR_MEAL), ("İngilizce mealler", EN_MEAL)):
        satir = []
        for mid in ids:
            V.meal_sure_yukle(c, mid, s)
            r = c.execute("SELECT m.metin, k.yazar FROM meal m JOIN meal_kaynak k ON k.id=m.id WHERE m.id=? AND m.s=? AND m.a=?", (mid, s, a)).fetchone()
            if r: satir.append(f"- {r['yazar']}: {r['metin']}")
        out.append(f"{grup}:\n" + "\n".join(satir))
    return "\n".join(out)

def claude(mesaj, max_tokens=4000, deneme=4):
    govde = json.dumps({"model": MODEL, "max_tokens": max_tokens, "system": SISTEM,
                        "messages": [{"role": "user", "content": mesaj}]}).encode()
    for i in range(deneme):
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=govde, method="POST",
                headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                d = json.loads(r.read())
            return "".join(b.get("text", "") for b in d["content"]), d.get("usage", {})
        except urllib.error.HTTPError as e:
            hata = e.read().decode()[:300]
            if e.code in (429, 500, 502, 503, 529): time.sleep(20 * (i + 1)); continue
            raise RuntimeError(f"API {e.code}: {hata}")
        except Exception as e:
            time.sleep(10 * (i + 1)); hata = str(e)
    raise RuntimeError("API yanıt vermedi: " + hata)

def bolumle(ayetler, n=5):
    for i in range(0, len(ayetler), n): yield ayetler[i:i + n]

def sure_uret(c, s, bolum=5, kuru=False, log=print):
    sure_ad = V.SURE_ADLARI[s - 1]
    mevcut = {r["a"] for r in c.execute("SELECT a FROM yalin_meal WHERE s=?", (s,))}
    eksik = [a for a in range(1, V.AYET_SAYILARI[s - 1] + 1) if a not in mevcut]
    if not eksik: return 0, {}
    toplam = {"input_tokens": 0, "output_tokens": 0}; yapilan = 0
    for grup in bolumle(eksik, bolum):
        onceki = c.execute("SELECT a, metin FROM yalin_meal WHERE s=? AND a<? ORDER BY a DESC LIMIT 4", (s, grup[0])).fetchall()
        baglam = "\n".join(f"{r['a']}: {r['metin']}" for r in reversed(onceki))
        mesaj = (f"SURE: {s}. {sure_ad}\n" + (f"Önceki ayetlerin yalın meali (bağlam için):\n{baglam}\n\n" if baglam else "")
                 + "\n\n".join(ayet_paketi(c, s, a) for a in grup)
                 + f"\n\nGÖREV: {', '.join(f'{s}:{a}' for a in grup)} ayetlerinin yalın mealini yaz.")
        if kuru:
            print(mesaj); print(f"\n--- paket: {len(mesaj)} karakter (~{len(mesaj)//3} token) ---"); return 0, {}
        metin, kullanim = claude(mesaj)
        for k in toplam: toplam[k] += kullanim.get(k, 0)
        m = re.search(r"\{.*\}", metin, re.S)
        try: sonuc = json.loads(m[0])["ayetler"]
        except Exception: log(f"  {s}:{grup} JSON okunamadı, atlandı"); continue
        with V._kilit:
            for x in sonuc:
                a = int(x["a"])
                if a not in grup: continue
                c.execute("INSERT OR IGNORE INTO yalin_meal(s,a,metin,dipnotlar,durum,guncelleme) VALUES(?,?,?,?,'taslak',datetime('now'))",
                          (s, a, x["meal"].strip(), json.dumps([d.strip() for d in x.get("dipnotlar", []) if d.strip()], ensure_ascii=False)))
                yapilan += 1
            c.commit()
    return yapilan, toplam

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sureler", default="1-114")
    ap.add_argument("--paralel", type=int, default=3, help="aynı anda kaç sure")
    ap.add_argument("--bolum", type=int, default=5, help="bir istekte kaç ayet")
    ap.add_argument("--kuru", action="store_true", help="yapay zekâya göndermeden ilk paketi göster")
    a = ap.parse_args()
    sureler = []
    for p in a.sureler.split(","):
        if "-" in p: x, y = map(int, p.split("-")); sureler += range(x, y + 1)
        else: sureler.append(int(p))
    c = V.baglan(); V.sema_kur(c)
    c.execute("CREATE TABLE IF NOT EXISTS yalin_meal(s INT, a INT, metin TEXT, dipnotlar TEXT, durum TEXT DEFAULT 'taslak', guncelleme TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(s,a))")
    V.arapca_yukle(c); V.morfoloji_yukle(c); V.meal_kaynaklari_yukle(c); V.tefsir_kaynaklari_yukle(c)
    if a.kuru: sure_uret(c, sureler[0], a.bolum, kuru=True); return
    if not API_KEY: sys.exit("ANTHROPIC_API_KEY tanımlı değil.")
    log = lambda *x: print(time.strftime("%H:%M:%S"), *x, flush=True)
    log(f"Yalın meal üretimi başladı: {len(sureler)} sure, model {MODEL}")
    genel = {"input_tokens": 0, "output_tokens": 0}
    def is_(s):
        try:
            n, k = sure_uret(c, s, a.bolum, log=log)
            for x in genel: genel[x] += k.get(x, 0)
            log(f"{s}. {V.SURE_ADLARI[s-1]}: {n} ayet yazıldı · toplam token girdi {genel['input_tokens']:,} / çıktı {genel['output_tokens']:,}")
        except Exception as e:
            log(f"{s}. {V.SURE_ADLARI[s-1]}: HATA {e}")
    with cf.ThreadPoolExecutor(a.paralel) as ex: list(ex.map(is_, sureler))
    hazir = c.execute("SELECT count(*) FROM yalin_meal").fetchone()[0]
    log(f"BİTTİ · yalın meal hazır: {hazir}/6236 ayet")

if __name__ == "__main__":
    main()
