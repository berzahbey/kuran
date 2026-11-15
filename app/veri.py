"""Veri katmanı: her şey yerel SQLite'tan okunur; yerelde yoksa internetten çekilir ve kaydedilir."""
import json, os, re, sqlite3, threading, urllib.request, zlib, unicodedata

DB_YOL = os.environ.get("KURAN_DB", os.path.join(os.path.dirname(__file__), "..", "veri", "kuran.db"))
RAW = "https://raw.githubusercontent.com"
MEAL_URL = RAW + "/fawazahmed0/quran-api/1"
TEFSIR_URL = RAW + "/spa5k/tafsir_api/main/tafsir"
HADIS_URL = RAW + "/fawazahmed0/hadith-api/1"
MORF_URL = RAW + "/mustafa0x/quran-morphology/master/quran-morphology.txt"

AYET_SAYILARI = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,11,8,3,9,5,4,7,3,6,3,5,4,5,6]

SURE_ADLARI = ["Fâtiha","Bakara","Âl-i İmrân","Nisâ","Mâide","En'âm","A'râf","Enfâl","Tevbe","Yûnus","Hûd","Yûsuf","Ra'd","İbrâhîm","Hicr","Nahl","İsrâ","Kehf","Meryem","Tâhâ","Enbiyâ","Hac","Mü'minûn","Nûr","Furkân","Şuarâ","Neml","Kasas","Ankebût","Rûm","Lokmân","Secde","Ahzâb","Sebe'","Fâtır","Yâsîn","Sâffât","Sâd","Zümer","Mü'min","Fussilet","Şûrâ","Zuhruf","Duhân","Câsiye","Ahkâf","Muhammed","Fetih","Hucurât","Kâf","Zâriyât","Tûr","Necm","Kamer","Rahmân","Vâkıa","Hadîd","Mücâdele","Haşr","Mümtehine","Saf","Cuma","Münâfikûn","Teğâbün","Talâk","Tahrîm","Mülk","Kalem","Hâkka","Meâric","Nûh","Cin","Müzzemmil","Müddessir","Kıyâme","İnsân","Mürselât","Nebe'","Nâziât","Abese","Tekvîr","İnfitâr","Mutaffifîn","İnşikâk","Bürûc","Târık","A'lâ","Gâşiye","Fecr","Beled","Şems","Leyl","Duhâ","İnşirâh","Tîn","Alak","Kadr","Beyyine","Zilzâl","Âdiyât","Kâria","Tekâsür","Asr","Hümeze","Fîl","Kureyş","Mâûn","Kevser","Kâfirûn","Nasr","Tebbet","İhlâs","Felak","Nâs"]

# Kıraat farklılıklarını göstermek için Arapça metin edisyonları
KIRAATLER = {"ara-quranuthmanihaf": "Hafs (Âsım)", "ara-quranshouba": "Şu'be (Âsım)", "ara-quranwarsh": "Verş (Nâfi')",
             "ara-quranqaloon": "Kâlûn (Nâfi')", "ara-quranbazzi": "Bezzî (İbn Kesîr)", "ara-quranqumbul": "Kunbul (İbn Kesîr)",
             "ara-qurandoori": "Dûrî (Ebû Amr)", "ara-quransoosi": "Sûsî (Ebû Amr)"}

# Tefsirler: (vefat yılı M., tür). Tür: rivayet / dirayet / lugat (lügat-i'râb) / isari / kiraat / modern-ozet
TEFSIR_BILGI = {
 "en-tafsir-ibn-abbas": (687, "rivayet", "İbn Abbas'a nispet edilen Tenvîru'l-Mikbâs (İng.)"),
 "ar-tafseer-tanwir-al-miqbas": (687, "rivayet", "Tenvîru'l-Mikbâs (İbn Abbas'a nispet)"),
 "en-tafsir-al-tustari": (896, "isari", "Tüsterî"), "ar-tafsir-al-tabari": (923, "rivayet", "Taberî — Câmiu'l-Beyân"),
 "tafsir-ibn-abi-hatim": (938, "rivayet", "İbn Ebî Hâtim"), "tafsir-al-samarqandi": (983, "rivayet", "Semerkandî — Bahru'l-Ulûm"),
 "tafsir-ibn-abi-zamanin": (1008, "rivayet", "İbn Ebî Zemenîn"), "tafsir-makhi": (1045, "dirayet", "Mekkî b. Ebî Tâlib — el-Hidâye"),
 "tafsir-al-mawardi": (1058, "dirayet", "Mâverdî — en-Nüket ve'l-Uyûn"), "en-al-qushairi-tafsir": (1072, "isari", "Kuşeyrî — Letâifü'l-İşârât"),
 "al-basit": (1076, "lugat", "Vâhidî — el-Basît"), "al-wajiz-wahidi": (1076, "dirayet", "Vâhidî — el-Vecîz"),
 "en-asbab-al-nuzul-by-al-wahidi": (1076, "rivayet", "Vâhidî — Esbâbü'n-Nüzûl"), "tafsir-al-sam-ani": (1096, "rivayet", "Sem'ânî"),
 "ar-tafsir-al-baghawi": (1122, "rivayet", "Begavî — Meâlimü't-Tenzîl"), "en-kashf-al-asrar-tafsir": (1126, "isari", "Meybüdî — Keşfü'l-Esrâr"),
 "al-kashshaf-al-zamakhshari": (1144, "lugat", "Zemahşerî — el-Keşşâf"), "al-muharrar-al-wajiz-ibn-atiyyah": (1147, "dirayet", "İbn Atıyye — el-Muharrer"),
 "tafsir-ibn-al-jawzi": (1201, "dirayet", "İbnü'l-Cevzî — Zâdü'l-Mesîr"), "tafsir-al-razi": (1210, "dirayet", "Fahreddin Râzî — Mefâtîhu'l-Gayb"),
 "ar-tafseer-al-qurtubi": (1273, "dirayet", "Kurtubî — el-Câmi' li-Ahkâmi'l-Kur'ân"), "tafsir-al-baydawi": (1286, "dirayet", "Beydâvî — Envâru't-Tenzîl"),
 "tafsir-al-nasafi": (1310, "dirayet", "Nesefî — Medârik"), "en-kashani-tafsir": (1330, "isari", "Abdürrezzâk Kâşânî"),
 "tafsir-ibn-juzay": (1340, "dirayet", "İbn Cüzey — et-Teshîl"), "al-bahr-al-muhit": (1344, "lugat", "Ebû Hayyân — el-Bahru'l-Muhît"),
 "tafsir-ibn-al-qayyim": (1350, "dirayet", "İbn Kayyim"), "al-dur-al-masun-lil-samin-al-halabi": (1355, "lugat", "Semîn el-Halebî — ed-Dürrü'l-Masûn"),
 "ar-tafsir-ibn-kathir": (1373, "rivayet", "İbn Kesîr"), "en-tafisr-ibn-kathir": (1373, "rivayet", "İbn Kesîr (İng.)"),
 "tr-tafsir-ibne-kathir": (1373, "rivayet", "İbn Kesîr (Türkçe)"), "ru-tafsir-ibne-kahtir": (1373, "rivayet", "İbn Kesîr (Rusça)"),
 "ur-tafseer-ibn-e-kaseer": (1373, "rivayet", "İbn Kesîr (Urduca)"), "tafseer-ibn-e-kaseer-urdu": (1373, "rivayet", "İbn Kesîr (Urduca)"),
 "bn-tafseer-ibn-e-kaseer": (1373, "rivayet", "İbn Kesîr (Bengalce)"),
 "al-nashr-li-ibn-al-jazari": (1429, "kiraat", "İbnü'l-Cezerî — en-Neşr"), "ar-tafsir-al-tha-alibi": (1471, "rivayet", "Seâlibî — el-Cevâhir"),
 "ar-tafsir-al-tha-alibi-527": (1471, "rivayet", "Seâlibî (2. nüsha)"), "al-lubab-fi-ulum-al-kitab": (1475, "lugat", "İbn Âdil — el-Lübâb"),
 "nazam-al-durar-al-biqa-i": (1480, "dirayet", "Bikâî — Nazmü'd-Dürer"), "jamia-al-bayan-aliji": (1501, "dirayet", "Îcî — Câmiu'l-Beyân"),
 "ar-tafsir-al-jalalayn": (1505, "dirayet", "Celâleyn"), "en-al-jalalayn": (1505, "dirayet", "Celâleyn (İng.)"), "tafsir-al-jalalayn": (1505, "dirayet", "Celâleyn (İng.)"),
 "in-tafsir-jalalayn": (1505, "dirayet", "Celâleyn (Endonezce)"), "al-durr-al-manthur": (1505, "rivayet", "Süyûtî — ed-Dürrü'l-Mensûr"),
 "tafsir-abi-al-su-ood": (1574, "dirayet", "Ebüssuûd — İrşâdü'l-Akli's-Selîm"), "fath-al-qadir-al-shawkani": (1834, "dirayet", "Şevkânî — Fethu'l-Kadîr"),
 "tafsir-al-alusi": (1854, "dirayet", "Âlûsî — Rûhu'l-Meânî"), "fath-al-bayan-li-al-qanuji": (1890, "dirayet", "Kannevcî — Fethu'l-Beyân"),
 "mahasin-al-ta-wil-al-qasimi": (1914, "dirayet", "Kâsımî — Mehâsinü't-Te'vîl"), "al-jadwal-fi-i-rab-al-quran": (1955, "lugat", "Mahmûd Sâfî — el-Cedvel fî İ'râbi'l-Kur'ân"),
 "ar-tafsir-as-saadi": (1956, "dirayet", "Sa'dî"), "ar-tafseer-al-saddi": (1956, "dirayet", "Sa'dî"), "turkish-tafsir-as-saadi-turkish": (1956, "dirayet", "Sa'dî (Türkçe)"),
 "sq-saadi": (1956, "dirayet", "Sa'dî (Arnavutça)"), "tafsir-as-saadi-russian": (1956, "dirayet", "Sa'dî (Rusça)"), "ru-tafseer-al-saddi": (1956, "dirayet", "Sa'dî (Rusça)"),
 "ur-tafsir-as-saadi-urdu": (1956, "dirayet", "Sa'dî (Urduca)"), "id-tafsir-as-saadi": (1956, "dirayet", "Sa'dî (Endonezce)"), "fr-tafsir-as-saadi": (1956, "dirayet", "Sa'dî (Farsça)"),
 "ur-tafsir-fe-zalul-quran-syed-qatab": (1966, "dirayet", "Seyyid Kutub — Fî Zılâl (Urduca)"), "tafsir-fe-zalul-quran-syed-qatab": (1966, "dirayet", "Seyyid Kutub — Fî Zılâl"),
 "adwa-al-bayan": (1973, "dirayet", "Şinkîtî — Edvâü'l-Beyân"), "ar-tafseer-tahrir-al-tanwir": (1973, "dirayet", "İbn Âşûr — et-Tahrîr ve't-Tenvîr"),
 "en-tafsir-maarif-ul-quran": (1976, "dirayet", "Müfti Muhammed Şefî — Maârifü'l-Kur'ân"), "i-rab-al-quran-li-al-darwish": (1982, "lugat", "Dervîş — İ'râbü'l-Kur'ân"),
 "tafsir-ibn-uthaymeen": (2001, "dirayet", "İbn Useymîn"), "ar-tafsir-al-wasit": (2010, "dirayet", "Tantâvî — el-Vasît"),
 "ur-tafsir-bayan-ul-quran": (2010, "dirayet", "İsrâr Ahmed — Beyânü'l-Kur'ân"), "tafsir-bayan-ul-quran": (2010, "dirayet", "İsrâr Ahmed — Beyânü'l-Kur'ân"),
 "mawsoo-at-al-tafsir-al-ma-thoor": (2017, "rivayet", "Mevsûatü't-Tefsîri'l-Me'sûr"), "abu-bakr-jabir-al-jazairi": (2018, "dirayet", "Ebû Bekir el-Cezâirî — Eyseru't-Tefâsîr"),
 "al-i-rab-al-muyassar": (2020, "lugat", "el-İ'râbü'l-Müyesser"), "alrab-al-quran-li-da-as": (2020, "lugat", "Da'âs — İ'râbü'l-Kur'ân"),
 "asseraj-fi-bayan-gharib-alquran": (2020, "lugat", "es-Sirâc fî Beyâni Garîbi'l-Kur'ân"), "al-muyassar-fi-al-gharib": (2020, "lugat", "el-Müyesser fi'l-Garîb"),
 "tahlil-kalimat-al-qur-an": (2020, "lugat", "Tahlîlü Kelimâti'l-Kur'ân"), "ayah-dependency-graphs": (2020, "lugat", "Ayet bağımlılık grafikleri"),
 "ar-tafsir-muyassar": (2020, "modern-ozet", "et-Tefsîru'l-Müyesser"), "ar-tafsir-al-mukhtasar": (2020, "modern-ozet", "el-Muhtasar fi't-Tefsîr"),
 "tadabbur-wa-amal": (2020, "modern-ozet", "Tedebbür ve Amel"), "ar-tafsir-al-jami-al-wajiz": (2020, "modern-ozet", "el-Câmiu'l-Vecîz"),
 "turkish-mokhtasar": (2020, "modern-ozet", "el-Muhtasar (Türkçe)"),
}
TUR_ADI = {"rivayet": "Rivâyet", "dirayet": "Dirâyet", "lugat": "Lügat / İ'râb", "isari": "İşârî", "kiraat": "Kıraat", "modern-ozet": "Modern / Özet"}

_kilit = threading.Lock()

class _IpligeOzelBaglanti:
    """Her iş parçacığına ayrı SQLite bağlantısı (paralel okuma/yazma güvenli)."""
    def __init__(self): self._yerel = threading.local()
    def _c(self):
        if not hasattr(self._yerel, "c"): self._yerel.c = _yeni_baglanti()
        return self._yerel.c
    def __getattr__(self, ad): return getattr(self._c(), ad)

def baglan(): return _IpligeOzelBaglanti()

def _yeni_baglanti():
    os.makedirs(os.path.dirname(os.path.abspath(DB_YOL)), exist_ok=True)
    c = sqlite3.connect(DB_YOL, timeout=60, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

SEMA = """
CREATE TABLE IF NOT EXISTS ayet(s INT, a INT, metin TEXT, kaynak TEXT, PRIMARY KEY(s,a,kaynak));
CREATE TABLE IF NOT EXISTS kelime(s INT, a INT, k INT, p INT, form TEXT, tur TEXT, etiket TEXT, kok TEXT, lemma TEXT);
CREATE INDEX IF NOT EXISTS kelime_sa ON kelime(s,a); CREATE INDEX IF NOT EXISTS kelime_kok ON kelime(kok);
CREATE TABLE IF NOT EXISTS lane(anahtar TEXT, kok_bw TEXT, html TEXT); CREATE INDEX IF NOT EXISTS lane_a ON lane(anahtar);
CREATE TABLE IF NOT EXISTS meal_kaynak(id TEXT PRIMARY KEY, dil TEXT, yazar TEXT, yon TEXT);
CREATE TABLE IF NOT EXISTS meal(id TEXT, s INT, a INT, metin TEXT, PRIMARY KEY(id,s,a));
CREATE TABLE IF NOT EXISTS meal_sure(id TEXT, s INT, PRIMARY KEY(id,s));
CREATE TABLE IF NOT EXISTS tefsir_kaynak(slug TEXT PRIMARY KEY, dil TEXT, yazar TEXT, ad TEXT);
CREATE TABLE IF NOT EXISTS tefsir(slug TEXT, s INT, a INT, metin BLOB, PRIMARY KEY(slug,s,a));
CREATE TABLE IF NOT EXISTS tefsir_sure(slug TEXT, s INT, PRIMARY KEY(slug,s));
CREATE TABLE IF NOT EXISTS hadis(kol TEXT, dil TEXT, no TEXT, kitap INT, metin TEXT, derece TEXT, PRIMARY KEY(kol,dil,no));
CREATE TABLE IF NOT EXISTS hadis_kol(kol TEXT, dil TEXT, ad TEXT, kitaplar TEXT, PRIMARY KEY(kol,dil));
CREATE TABLE IF NOT EXISTS hadis_ayet(kol TEXT, no TEXT, s INT, a INT, skor REAL, PRIMARY KEY(kol,no,s,a));
CREATE INDEX IF NOT EXISTS hadis_ayet_sa ON hadis_ayet(s,a);
CREATE TABLE IF NOT EXISTS notlar(id INTEGER PRIMARY KEY AUTOINCREMENT, s INT, a INT, metin TEXT, etiket TEXT, olusturma TEXT DEFAULT CURRENT_TIMESTAMP, guncelleme TEXT);
CREATE INDEX IF NOT EXISTS notlar_sa ON notlar(s,a);
CREATE TABLE IF NOT EXISTS analiz(s INT, a INT, tur TEXT, metin TEXT, tarih TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(s,a,tur));
CREATE TABLE IF NOT EXISTS ceviri_onbellek(anahtar TEXT PRIMARY KEY, metin TEXT);
CREATE TABLE IF NOT EXISTS durum(asama TEXT PRIMARY KEY, bilgi TEXT, tarih TEXT DEFAULT CURRENT_TIMESTAMP);
"""

def sema_kur(c):
    c.executescript(SEMA); c.commit()

def indir(url, deneme=3, zaman=60):
    hata = None
    for _ in range(deneme):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dedplay-kuran/1.0"})
            with urllib.request.urlopen(req, timeout=zaman) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            hata = e
        except Exception as e:
            hata = e
    return None

def sikistir(t): return zlib.compress(t.encode("utf-8"), 6)
def ac(b): return zlib.decompress(b).decode("utf-8") if isinstance(b, (bytes, memoryview)) else b

# ---------- Arapça normalizasyonu ----------
_HAREKE = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ࣓-ࣿـ]")
def sadelestir(t):
    t = unicodedata.normalize("NFC", t)
    t = _HAREKE.sub("", t)
    t = re.sub("[أإآٱ]", "ا", t); t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي").replace("ء", "")
    t = re.sub(r"[^ء-ي\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

# ---------- Kök anahtarı (morfoloji ile Lane'i eşlemek için) ----------
BW = {"A":"ا","b":"ب","t":"ت","v":"ث","j":"ج","H":"ح","x":"خ","d":"د","*":"ذ","r":"ر","z":"ز","s":"س","$":"ش","S":"ص","D":"ض","T":"ط","Z":"ظ","E":"ع","g":"غ","f":"ف","q":"ق","k":"ك","l":"ل","m":"م","n":"ن","h":"ه","w":"و","y":"ي","Y":"ى","'":"ء",">":"أ","<":"إ","&":"ؤ","}":"ئ","|":"آ","p":"ة","{":"ٱ","a":"َ","u":"ُ","i":"ِ","o":"ْ","~":"ّ","F":"ً","N":"ٌ","K":"ٍ","`":"ٰ","_":"ـ","^":"ٔ"}
def bw2ar(t): return "".join(BW.get(ch, ch) for ch in t)

def kok_anahtari(kok_ar):
    k = re.sub("[أإآءؤئٱا]", "ء", kok_ar).replace("ى", "ي")
    k = re.sub(r"[^ء-ي]", "", k)
    if len(k) == 3 and k[1] == k[2]: k = k[:2]
    return k

def lane_anahtari(bw):
    b = bw.replace("^", "").replace("Y", "y")
    b = re.sub(r"[^A-Za-z'$*]", "", b)
    k = "".join("ء" if ch in "A'" else BW.get(ch, "") for ch in b)
    if len(k) == 3 and k[1] == k[2]: k = k[:2]
    return k

# ---------- Yerelde yoksa internetten çek ----------
def morfoloji_yukle(c):
    if c.execute("SELECT 1 FROM kelime LIMIT 1").fetchone(): return
    t = indir(MORF_URL)
    if not t: return
    satirlar = []
    for l in t.splitlines():
        p = l.split("\t")
        if len(p) < 4 or ":" not in p[0]: continue
        s, a, k, seg = map(int, p[0].split(":"))
        kok = re.search(r"ROOT:([^|]+)", p[3]); lem = re.search(r"LEM:([^|]+)", p[3])
        satirlar.append((s, a, k, seg, p[1], p[2], p[3], kok[1] if kok else None, lem[1] if lem else None))
    with _kilit:
        c.executemany("INSERT INTO kelime VALUES(?,?,?,?,?,?,?,?,?)", satirlar); c.commit()

def meal_kaynaklari_yukle(c):
    if c.execute("SELECT 1 FROM meal_kaynak LIMIT 1").fetchone(): return
    d = json.loads(indir(MEAL_URL + "/editions.json"))
    with _kilit:
        c.executemany("INSERT OR REPLACE INTO meal_kaynak VALUES(?,?,?,?)",
                      [(v["name"], v["language"], v["author"], v.get("direction", "ltr")) for v in d.values()]); c.commit()

def meal_sure_yukle(c, mid, s):
    if c.execute("SELECT 1 FROM meal_sure WHERE id=? AND s=?", (mid, s)).fetchone(): return True
    t = indir(f"{MEAL_URL}/editions/{mid}/{s}.json")
    if not t: return False
    ch = json.loads(t)["chapter"]
    with _kilit:
        c.executemany("INSERT OR REPLACE INTO meal VALUES(?,?,?,?)", [(mid, s, x["verse"], x["text"]) for x in ch])
        c.execute("INSERT OR REPLACE INTO meal_sure VALUES(?,?)", (mid, s)); c.commit()
    return True

def tefsir_kaynaklari_yukle(c):
    if c.execute("SELECT 1 FROM tefsir_kaynak LIMIT 1").fetchone(): return
    d = json.loads(indir(TEFSIR_URL + "/editions.json"))
    with _kilit:
        c.executemany("INSERT OR REPLACE INTO tefsir_kaynak VALUES(?,?,?,?)",
                      [(e["slug"], e.get("language_name"), e.get("author_name"), e.get("name")) for e in d]); c.commit()

def tefsir_sure_yukle(c, slug, s):
    if c.execute("SELECT 1 FROM tefsir_sure WHERE slug=? AND s=?", (slug, s)).fetchone(): return True
    t = indir(f"{TEFSIR_URL}/{slug}/{s}.json")
    if not t: return False
    try: d = json.loads(t)
    except Exception: return False
    ayetler = d.get("ayahs", d) if isinstance(d, dict) else d
    satir = []
    for x in ayetler:
        a = x.get("ayah") or x.get("ayah_number") or x.get("verse")
        if a and x.get("text"): satir.append((slug, s, int(a), sikistir(x["text"])))
    with _kilit:
        c.executemany("INSERT OR REPLACE INTO tefsir VALUES(?,?,?,?)", satir)
        c.execute("INSERT OR REPLACE INTO tefsir_sure VALUES(?,?)", (slug, s)); c.commit()
    return True

HADIS_KOLLAR = ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah", "malik", "nawawi", "qudsi", "dehlawi"]
HADIS_ADLARI = {"bukhari": "Buhârî", "muslim": "Müslim", "abudawud": "Ebû Dâvûd", "tirmidhi": "Tirmizî", "nasai": "Nesâî",
                "ibnmajah": "İbn Mâce", "malik": "Muvatta", "nawawi": "Nevevî — Kırk Hadis", "qudsi": "Kudsî Hadisler", "dehlawi": "Dehlevî — Kırk Hadis"}

# fawazahmed0/hadith-api'de olmayan ek hadis kitapları (AhmedBaset/hadith-json; Arapça + İngilizce)
HADIS_JSON_URL = RAW + "/AhmedBaset/hadith-json/main/db/by_book"
HADIS_EK = {"darimi": ("the_9_books/darimi.json", "Dârimî — Sünen"), "ahmed": ("the_9_books/ahmed.json", "Ahmed b. Hanbel — Müsned (seçme)"),
            "mishkat": ("other_books/mishkat_almasabih.json", "Mişkâtü'l-Mesâbîh"), "riyad": ("other_books/riyad_assalihin.json", "Riyâzü's-Sâlihîn"),
            "bulugh": ("other_books/bulugh_almaram.json", "Bulûğu'l-Merâm"), "shamail": ("other_books/shamail_muhammadiyah.json", "Tirmizî — Şemâil"),
            "adab": ("other_books/aladab_almufrad.json", "Buhârî — el-Edebü'l-Müfred")}
HADIS_ADLARI.update({k: v[1] for k, v in HADIS_EK.items()})

def hadis_json_yukle(c, kol):
    if c.execute("SELECT 1 FROM hadis_kol WHERE kol=? AND dil='ara'", (kol,)).fetchone(): return True
    t = indir(f"{HADIS_JSON_URL}/{HADIS_EK[kol][0]}", zaman=240)
    if not t: return False
    d = json.loads(t); ara, eng = [], []
    for h in d["hadiths"]:
        no = str(h.get("idInBook") or h["id"])
        if h.get("arabic"): ara.append((kol, "ara", no, h.get("chapterId"), h["arabic"], "[]"))
        e = h.get("english") or {}
        et = (e.get("narrator", "") + " " + e.get("text", "")).strip() if isinstance(e, dict) else str(e)
        if et: eng.append((kol, "eng", no, h.get("chapterId"), re.sub(r"\s+", " ", et), "[]"))
    with _kilit:
        c.executemany("INSERT OR REPLACE INTO hadis VALUES(?,?,?,?,?,?)", ara + eng)
        for dil in ("ara", "eng"): c.execute("INSERT OR REPLACE INTO hadis_kol VALUES(?,?,?,?)", (kol, dil, HADIS_EK[kol][1], "{}"))
        c.commit()
    return True

def hadis_kol_yukle(c, kol, dil):
    if c.execute("SELECT 1 FROM hadis_kol WHERE kol=? AND dil=?", (kol, dil)).fetchone(): return True
    t = indir(f"{HADIS_URL}/editions/{dil}-{kol}.min.json", zaman=180)
    if not t: return False
    d = json.loads(t)
    satir = [(kol, dil, str(h["hadithnumber"]), (h.get("reference") or {}).get("book"), h.get("text") or "",
              json.dumps(h.get("grades") or [], ensure_ascii=False)) for h in d["hadiths"] if h.get("text")]
    with _kilit:
        c.executemany("INSERT OR REPLACE INTO hadis VALUES(?,?,?,?,?,?)", satir)
        c.execute("INSERT OR REPLACE INTO hadis_kol VALUES(?,?,?,?)", (kol, dil, d["metadata"].get("name"),
                  json.dumps(d["metadata"].get("sections", {}), ensure_ascii=False))); c.commit()
    return True

def arapca_yukle(c, kaynak="ara-quranuthmanihaf"):
    if c.execute("SELECT 1 FROM ayet WHERE kaynak=? LIMIT 1", (kaynak,)).fetchone(): return True
    t = indir(f"{MEAL_URL}/editions/{kaynak}.min.json", zaman=180) or indir(f"{MEAL_URL}/editions/{kaynak}.json", zaman=180)
    if not t: return False
    q = json.loads(t)["quran"]
    with _kilit:
        c.executemany("INSERT OR REPLACE INTO ayet VALUES(?,?,?,?)", [(x["chapter"], x["verse"], x["text"], kaynak) for x in q]); c.commit()
    return True

def lane_bul(c, kok_ar):
    """Kökün Lane maddesini bulur; zayıf harf (و/ي) ve tekrarlı kök (زلزل→زل) varyantlarını da dener."""
    k = kok_anahtari(kok_ar); aday = [k]
    if k and k[-1] in "وي": aday.append(k[:-1] + ("ي" if k[-1] == "و" else "و"))
    if len(k) == 4 and k[:2] == k[2:]: aday.append(k[:2])
    if len(k) >= 2 and k[1] in "وي": aday.append(k[0] + ("ي" if k[1] == "و" else "و") + k[2:])
    for a in aday:
        r = c.execute("SELECT kok_bw, html FROM lane WHERE anahtar=? LIMIT 1", (a,)).fetchone()
        if r: return {"kok_bw": r["kok_bw"], "html": r["html"]}
    return None

# Nüzul (iniş) sırası — Tanzil / Ezher sıralaması
NUZUL_SIRASI = [5,87,89,92,112,55,39,88,113,51,52,53,96,72,54,70,50,69,44,45,73,103,74,102,42,47,48,49,85,84,57,75,90,58,43,41,56,38,59,60,61,62,63,64,65,66,95,111,106,34,67,76,23,37,97,46,94,105,101,91,109,110,104,108,99,107,77,2,78,79,71,40,3,4,31,98,33,80,81,24,7,82,86,83,27,36,8,68,10,35,26,9,11,12,28,1,25,100,93,14,30,16,13,32,19,29,17,15,18,114,6,22,20,21]
# Sebeb-i nüzûl ararken bakılacak rivâyet ağırlıklı tefsirler
ESBAB_TEFSIRLER = ["ar-tafsir-al-tabari", "tafsir-ibn-abi-hatim", "al-wajiz-wahidi", "al-basit", "ar-tafsir-al-baghawi", "ar-tafseer-al-qurtubi",
                   "ar-tafsir-ibn-kathir", "al-durr-al-manthur", "tafsir-al-samarqandi", "tafsir-ibn-al-jawzi", "ar-tafsir-al-jalalayn"]

# Meal yazar adlarının düzgün Türkçe yazımı (kaynak verideki bozuk ASCII adlar için)
YAZAR_ADI = {"tur-abdulbakigolpin": "Abdülbâki Gölpınarlı", "tur-ademugur": "Adem Uğur", "tur-alibulac": "Ali Bulaç",
 "tur-alifikriyavuz": "Ali Fikri Yavuz", "tur-celalyldrm": "Celal Yıldırım", "tur-diyanetisleri": "Diyanet İşleri",
 "tur-diyanetisleri1": "Diyanet İşleri (yeni)", "tur-diyanetvakfi": "Diyanet Vakfı", "tur-edipyuksel": "Edip Yüksel",
 "tur-elmalilihamdiya": "Elmalılı Hamdi Yazır", "tur-elmallsadelesti": "Elmalılı (sadeleştirilmiş)", "tur-elmallsadelesti1": "Elmalılı (sadeleştirilmiş 2)",
 "tur-fizilalilkuran": "Fî Zılâli'l-Kur'an", "tur-gultekinonan": "Gültekin Onan", "tur-hasanbasricanta": "Hasan Basri Çantay",
 "tur-ibnikesir": "İbn Kesir", "tur-iskenderalimihr": "İskender Ali Mihr", "tur-muhammedesed": "Muhammed Esed",
 "tur-muhammetabay": "Muhammet Abay", "tur-muslimshahin": "Müslim Şahin", "tur-sabanpiris": "Şaban Piriş",
 "tur-shabanbritch": "Şaban Britch", "tur-suatyildirim": "Suat Yıldırım", "tur-suleymanates": "Süleyman Ateş",
 "tur-tefhimulkuran": "Tefhîmu'l-Kur'an (Mevdûdî)", "tur-wwwislamhouseco": "IslamHouse", "tur-yasarnuriozturk": "Yaşar Nuri Öztürk",
 "tur-yasarnuriozturk1": "Yaşar Nuri Öztürk (2)", "tur-ynozturk": "Yaşar Nuri Öztürk (3)",
 "nld-fredleemhuis": "Fred Leemhuis", "nld-sofianssiregar": "Sofian S. Siregar", "nld-salomokeyzer": "Salomo Keyzer (1860)",
 "nld-unknown": "Anoniem (Van De Taal)"}

def _sade_ad(x):
    x = x.replace("İ", "i").replace("I", "ı").lower()
    x = unicodedata.normalize("NFKD", x)
    x = "".join(ch for ch in x if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", x.translate(str.maketrans("çğıöşü", "cgiosu")))

def sure_listesi_coz(metin):
    """'68', '78-114', '1,2,112', 'ihlas', 'Felak, Nâs', 'kalem-mülk' → sure numaraları. Anlaşılmayan parça için ValueError."""
    adlar = {_sade_ad(a): i + 1 for i, a in enumerate(SURE_ADLARI)}
    def tek(p):
        p = p.strip()
        if p.isdigit():
            n = int(p)
            if 1 <= n <= 114: return n
            raise ValueError(f"'{p}' geçerli sure numarası değil (1-114)")
        s = adlar.get(_sade_ad(p))
        if not s:
            aday = [n for a, n in adlar.items() if a.startswith(_sade_ad(p))]
            if len(aday) == 1: s = aday[0]
        if not s: raise ValueError(f"'{p}' sure adı anlaşılamadı")
        return s
    sonuc = []
    for parca in [x for x in re.split(r"[,;]", metin or "1-114") if x.strip()]:
        m = re.match(r"^\s*([^-–]+?)\s*[-–]\s*([^-–]+?)\s*$", parca)
        if m and _sade_ad(parca) not in adlar:
            a, b = tek(m[1]), tek(m[2]); sonuc += range(min(a, b), max(a, b) + 1)
        else: sonuc.append(tek(parca))
    return list(dict.fromkeys(sonuc))
