# -*- coding: utf-8 -*-
import os, re, json, sys
BURADA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURADA)
from motor import isim, et_fiil, uyum, bas_ses, UNLU, son_unlu

LEM = json.load(open(os.path.join(BURADA, 'lemma.json')))
def lem(sa): return set(LEM['L'].get(sa, []))
def kok(sa): return set(LEM['R'].get(sa, []))

def isim2(yeni, ek, eski_unlu_son=False, **kw):
    """eski ünlüyle biten → yeni ünsüzle biten için kaynaştırma/iyelik düzeltmesi."""
    if eski_unlu_son and yeni[-1] not in UNLU and ek:
        if re.match(r'^s[ıiuü]n(ız|iz|uz|üz)?$', ek) or re.match(r'^s[ıiuü]z', ek):
            pass                                   # -sın (şahıs) / -sız (yokluk)
        elif re.match(r'^n[ıiuü]n', ek):
            ek = ek[1:]                            # ilgi: süre-nin → müddet-in
        elif ek[0] in 'mn':
            ek = 'ı' + ek                          # iyelik: bilgi-m → ilm-im, elçi-me → resul-üme
        elif ek[0] == 'y' and len(ek) > 1 and (ek[1] in UNLU or ek[1] in 'ldm'):
            ek = ek[1:]                            # y kaynaştırma: süre-ye, bilgi-yle
        elif ek[0] == 's' and len(ek) > 1 and ek[1] in UNLU:
            ek = ek[1:]                            # 3. iyelik: süre-si → müddet-i
        return isim(yeni, ek, eski_unlu_son=False, **kw)
    return isim(yeni, ek, eski_unlu_son=eski_unlu_son, **kw)

# ---------- KÖK KURALLARI: (eski önekler, fonksiyon(ek, sa) -> yeni | None, hariç kelimeler, koşul(sa)) ----------
KOK = []
def N(eskiler, yeni, haric=(), kosul=None, eski_unlu_son=None, izin=None, **kw):
    if isinstance(eskiler, str): eskiler = [eskiler]
    for e in eskiler:
        eus = eski_unlu_son if eski_unlu_son is not None else (e[-1] in UNLU)
        def f(ek, sa, yeni=yeni, eus=eus, kw=kw, izin=izin):
            if izin is not None and not re.fullmatch(izin, ek): return None
            return isim2(yeni, ek, eus, **kw)
        KOK.append((e, f, set(haric), kosul))

def V(eski, on_ek, haric=(), kosul=None):
    eus = eski[-1] in UNLU
    KOK.append((eski, (lambda ek, sa, on_ek=on_ek, eus=eus: et_fiil(on_ek, ek, eus)), set(haric), kosul))
    if eus:   # -yor daralması: yalanlıyor
        for v in 'ıiuü':
            KOK.append((eski[:-1] + v + 'yor', (lambda ek, sa, on_ek=on_ek, v=v: et_fiil(on_ek, v + 'yor' + ek, True)), set(), kosul))

def var(*lemler):
    return lambda sa: bool(lem(sa) & set(lemler))
def kokte(*kokler):
    return lambda sa: bool(kok(sa) & set(kokler))
def yok(f):
    return lambda sa: not f(sa)

# öz Türkçe / yeni kelimeler
N('toplum', 'kavim', dusen='kavm')
N(['topluluk', 'topluluğ'], 'cemaat', unlu='e')
N(['ödül'], 'mükâfat')
N('süre', 'müddet', haric={'süren','süregelen','sürenler','süreriz','sürer','sürecek','sürerler','süreceğim','sürece','sürekli','süreklidir','süreklidirler'})
N('durum', 'hal', unlu='e', haric={'durumca'})
N('esenlik', 'selâmet', unlu='e')
N(['egemenlik','egemenliğ'], 'hâkimiyet')
N('egemen', 'hâkim', haric={'egemenliği','egemenliğini'})
N(['sorumluluk','sorumluluğ'], 'mesuliyet')
N('sorumlu', 'mesul', unlu='ü', haric={'sorumluluk','sorumluluğunuzu'})
N('ilişki', 'münasebet')
N('bilgi', 'ilim', dusen='ilm', haric={'bilgin','bilginiz','bilgisizce','bilgisizlikleri'})
N('yasa', 'kanun', haric={'yasamızda'}, kosul=None)
KOK[-1] = (KOK[-1][0], KOK[-1][1], KOK[-1][2], None)  # yasak* ayrı tutulur
N('barış', 'sulh', unlu='a', haric={'barışmak'})
N('kuşku', 'şüphe')
N('ülke', 'memleket')
N('çaba', 'gayret', haric={'çabaladığını','çabaladıkça','çabalamaktasın'})
N('yetki', 'salâhiyet', haric={'yetkin'})
N('saygı', 'hürmet', haric={'saygısızlık','saygın'})
N('ilişki', 'münasebet')
N(['kulluk','kulluğ'], 'ibadet')
N('elçi', 'resul', unlu='ü', haric={'elçilik'})
N('öğüt', 'nasihat', unlu='e', haric={'öğütle','öğütlüyor','öğütlüyorum','öğütçüyüm'})
N('müjdeleyici', 'beşîr')
N(['bozgunculuk','bozgunculuğ'], 'fesat', yumusak='fesad')
N('bozguncu', 'müfsit', yumusak='müfsid', haric={'bozgunculuk','bozgunculuğu','bozgunculuğa','bozgunculuktan','bozgunculuğun'})
N(['sapıklık','sapıklığ'], 'dalâlet', unlu='e')
N(['azgınlık','azgınlığ'], 'tuğyan')
N(['nankörlük','nankörlüğ'], 'inkâr', unlu='a', kosul=yok(kokte('شكر')))
V('yalanla', 'tekzip', haric={'yalanlar','yalanlayıcılar','yalanlayıcılardan','yalanlayıcıları'})
V('uygula', 'tatbik')
V('kutsa', 'takdis')
# uyarmak yalnız ن ذ ر kökü varsa
_nzr = kokte('نذر')
N('uyarıcı', 'nezîr', kosul=_nzr)
V('uyar', 'inzar', haric={'uyarlar','uyarız','uyarım','uyarlardı','uyarıcı','uyarıcıyım','uyarıcılar','uyarıcıdır','uyarıcısın',
      'uyarıcılardan','uyarıcıları','uyarıcılardanım','uyarıcıyız','uyarıları','uyarılarım','uyarılarımı'}, kosul=_nzr)
# kurtuluş: köke göre
N('kurtuluş', 'felâh', unlu='a', kosul=kokte('فلح'))
N('kurtuluş', 'necat', unlu='a', kosul=lambda sa: 'نجو' in kok(sa) and 'فلح' not in kok(sa))
N('kurtuluş', 'saadet', unlu='e', kosul=lambda sa: 'فوز' in kok(sa) and 'فلح' not in kok(sa) and 'نجو' not in kok(sa))
# güç → kuvvet/kudret (yet- kalıbı IFADE'de)
N('güçlü', 'kuvvetli')
N('güçsüz', 'zayıf', haric={'güçsüzlük','güçsüzlüğün','güçsüzlükten'})
N(['güçsüzlük','güçsüzlüğ'], 'zaaf', yumusak='zaaf')

# ---------- TEK KELİME TABLOSU (küçük harf) ----------
TEK = {
 # ad → isim
 'adıyla':'ismiyle','adıyladır':'ismiyledir','adı':'ismi','adını':'ismini','adının':'isminin','adlı':'isimli',
 'adlarını':'isimlerini','adına':'namına','adınıza':'namınıza','adlanmak':'anılmak',
 'yargılanacağız':'muhakeme edileceğiz',
 'sürece':'müddetçe','sürekli':'daimî','süreklidir':'daimîdir','süreklidirler':'devam ederler',
 'durumca':'mevkice',
 'güven':'emniyet','güvene':'emniyete','güvenini':'emniyetini','güvenle':'emniyetle','güvende':'emniyette',
 'güvendedirler':'emniyettedirler','güvenli':'emin','güvenliğe':'emniyete','güvenilir':'emin','güvenilirdir':'emindir',
 'sonuç':'âkıbet','sonuçlar':'âkıbetler',
 'kesinlikle':'muhakkak','kesin':'kat’î','kesindir':'kat’îdir','kesinleşmiş':'kat’îleşmiş','kesinliğiyle':'yakîniyle',
 'eşit':'müsavi','eşitlendiği':'denkleştiği','cinsel':'cinsî',
 'konusunda':'hususunda','konuda':'hususta','konusu':'mevzuu',
 'bilgim':'ilmim','bilgimiz':'ilmimiz','bilginiz':'ilminiz','bilgisizce':'ilimsizce','bilgisizlikleri':'cehaletleri',
 'niteliklerden':'vasıflardan','ölümsüz':'ebedî','ölümsüzlük':'ebedîlik','duygusu':'hissi',
 'uyum':'ahenk','uyumu':'ahengi','seçkin':'güzide','içtenlikle':'samimiyetle',
 'uygulamalar':'âdetler','uygulama':'tatbik',
 'kanıt':'delil','tanık':'şahit','kutsal':'mukaddes',
 'yasamızda':'kanunumuzda',
 'yaratıklara':'mahlûklara',
 'önder':'imam','önderler':'imamlar','önderleriyle':'imamlarıyla','önderlikten':'imamlıktan',
 'yöntem':'usul','olayların':'hadiselerin','olaylar':'hadiseler',
 'yetkin':'salâhiyetin','amaç':'maksat','dönem':'devir','dönemde':'devirde',
 'saygısızlık':'hürmetsizlik','saygın':'muhterem','seçenek':'tercih hakkı','yanılgı':'dalâlet','övgü':'senâ',
 'anlamını':'manasını','anlam':'mana','anlamda':'manada','anlamına':'manasına','anlamıyla':'manasıyla','anlamlar':'manalar','anlamı':'manası','anlamsız':'manasız',
 'görevini':'vazifesini','göreviniz':'vazifeniz','görevlendirildikleri':'vazifelendirildikleri','görevleri':'vazifeleri',
 'görev':'vazife','görevlendirilen':'vazifelendirilen','görevim':'vazifem','görevli':'vazifeli',
 'bölgeye':'diyara','konukseverlerin':'misafirperverlerin','tüm':'bütün',
 'özgürlüğü':'hürriyeti','özgürlükleri':'hürriyetleri','özgürlük':'hürriyet','özgürce':'serbestçe',
 'önemli':'mühim','önemsiz':'ehemmiyetsiz','önleminizi':'tedbirinizi','önlemlerini':'tedbirlerini',
 'uğraş':'meşguliyet','denetleyici':'rakîb','inançla':'itikatla',
 'elçilik':'risalet','öğütle':'nasihatle','öğütlüyor':'tavsiye ediyor','öğütlüyorum':'tavsiye ediyorum','öğütçüyüm':'nâsıhım',
 'grup':'taife','gruplar':'taifeler','gruplara':'taifelere','gruptan':'taifeden','gruplardan':'taifelerden','gruptur':'taifedir',
 'grubu':'taifeyi','gruba':'taifeye','grubun':'taifenin',
 'yalanlayıcılar':'mükezzibler','yalanlayıcılardan':'mükezziblerden','yalanlayıcıları':'mükezzibleri',
 'uyarıcı':'nezîr','uyarıcıyım':'nezîrim','uyarıcılar':'nezîrler','uyarıcıdır':'nezîrdir','uyarıcısın':'nezîrsin',
 'uyarıcılardan':'nezîrlerden','uyarıcıları':'nezîrleri','uyarıcılardanım':'nezîrlerdenim','uyarıcıyız':'nezîriz',
 'uyarıları':'inzarları','uyarılar':'inzarlar','uyarımın':'inzarımın','toplumuz':'kavimiz','uyarılarım':'inzarlarım','uyarılarımı':'inzarlarımı',
 'güçlük':'meşakkat','güçlükle':'meşakkatle','güçlükten':'meşakkatten',
 'güçlendireceğiz':'takviye edeceğiz','güçlendirdik':'takviye ettik','güçlendirmiş':'takviye etmiş',
 'sakınanlar':'müttakîler','sakınanları':'müttakîleri','sakınanlarla':'müttakîlerle','sakınanlardan':'müttakîlerden',
 'sakınanlara':'müttakîlere','sakınanlardır':'müttakîlerdir','sakınanların':'müttakîlerin',
 'sakınasınız':'takvaya eresiniz',
 'nankörler':'inkâr edenler','nankörlerin':'inkâr edenlerin','nankörlere':'inkâr edenlere','nankörleri':'inkâr edenleri',
 'nankörlerden':'inkâr edenlerden','nankörlerle':'inkâr edenlerle','nankörlerdensin':'inkâr edenlerdensin',
}
# 'nankör' tekil: كفور/كفار (çok nankör) ya da şükür varsa kalır
NANKOR_TEKIL = {'nankör':'inkâr eden','nankördür':'inkâr edendir','nankörü':'inkâr edeni','nanköre':'inkâr edene',
                'nankördü':'inkâr ederdi','nankörce':'inkârla','nankörleşir':'inkâra düşer'}
def nankor_kalsin(sa):
    return bool(lem(sa) & {'كفور','كفار'}) or ('شكر' in kok(sa))

# yoksul → miskin / fakir
def yoksul(w, sa):
    L = lem(sa)
    if w.startswith('yoksulluk'):
        if 'مسكنة' in L: return 'meskenet' + w[len('yoksulluk'):]
        return None
    ek = w[len('yoksul'):]
    if L & {'مسكين'}: return isim('miskin', ek)
    if L & {'فقير'}: return isim('fakir', ek)
    return None

# dost → velî (و ل ي kökü)
DOST = {'dost':'velî','dostlar':'veliler','dostları':'velileri','dostudur':'velîsidir','dostunuz':'velîniz','dostu':'velîsi',
        'dostlarıdır':'velileridir','dostun':'velînin','dostum':'velîm','dosta':'velîye','dostuydu':'velîsiydi',
        'dostlarını':'velilerini','dostlarıyla':'velileriyle','dostlarına':'velilerine','dostların':'velilerin',
        'dostlarınız':'velileriniz','dostlarınızdır':'velilerinizdir','dostlarınıza':'velilerinize','dostumuz':'velîmiz',
        'dostlarınızız':'velilerinizi̇z'.replace('i̇','i'),'dostluk':'velâyet','dostluğun':'velâyetin'}
def dost(w, sa):
    if 'ولي' not in kok(sa): return None
    return DOST.get(w)

# ayet bazlı özel düzeltmeler (s:a, eski ifade, yeni)
AYET = [
 ('5:12','on iki önder','on iki nakîb'),
 ('76:18','adına "Selsebîl"','ismine "Selsebîl"'),
 ('46:21','sizin adınıza','sizin hakkınızda'),
 ('86:5','neden yaratıldığına','neyden yaratıldığına'),
 ('19:31','Nerede olursam olayım','Nerede olursam olayım'),
 ('2:282','iki şahidi de tanık tutun','iki şahit tutun'),
 ('5:108','Bu (yöntem)','Bu (usul)'),
 ('12:8','apaçık bir yanılgı','apaçık bir dalâlet'),
 ('12:30','apaçık bir yanılgı','apaçık bir dalâlet'),
 ('38:75','Büyüklük mü tasladın','Kibirlendin mi'),
]
# IFADE kuralları (regex, yeni) — kelime kurallarından ÖNCE
IFADE = [
 (r'\b([Aa])ndolsun ki\b', lambda m: ('Y' if m.group(1)=='A' else 'y') + 'emin olsun ki'),
 (r'\b([Aa])ndolsun(?=,? )', None),   # aşağıda özel
 (r'büyüklük tasla(\w*)', 'KIBIR'),
 (r'\b(G|g)üç yetiremeyen', lambda m: ('T' if m.group(1)=='G' else 't') + 'akat getiremeyen'),
 (r'\b(G|g)üc(ü|ünün|ümüz|ünüz|üm|ün|ümüzün)( (?:\w+ )?yet)', None),  # takat
 (r'\bneden\b', 'NEDEN'),
]

_gfr = kokte('غفر')
N('bağışlanma', 'mağfiret', kosul=_gfr, izin=r'(|ya|yı|sı|sını|sına|sından|nın|dır|yla|dan|da|lar|ları|larını)')
V('bağışla', 'mağfiret', kosul=_gfr)
N('öfke', 'gazap', yumusak='gazab', kosul=kokte('غضب'), haric={'öfkeli'}, izin=r'(?!l[ei]n).*')
N('aşağılanma', 'zillet', kosul=kokte('ذلل'), izin=r'(|ya|yı|sı|nın|dan)')
N('suçlu', 'mücrim', kosul=kokte('جرم'))
N('antlaşma', 'ahit', yumusak='ahd', kosul=kokte('عهد'))
TEK.update({'alçaltıcı':'zillet verici','alçaltıcıdır':'zillet vericidir','aşağılayıcı':'zillet verici','aşağılık':'zelil'})
