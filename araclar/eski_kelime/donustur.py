# -*- coding: utf-8 -*-
import os, re, json, sys, collections
BURADA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURADA)
from motor import uyum, bas_ses, UNLU, son_unlu
from kurallar import *

AP = "’"
def buyuk(s):
    if not s: return s
    f = s[0]
    f = 'İ' if f == 'i' else ('I' if f == 'ı' else f.upper())
    return f + s[1:]
def kucuk(s):
    return s.replace('İ', 'i').replace('I', 'ı').lower()

# ---- Esmâ ----
ESMA = [
 (r'tövbeleri çokça kabul eden', [('تواب', 'Tevvâb')]),
 (r'çok bağışlayan', [('غفور', 'Gafûr'), ('غفار', 'Gaffâr')]),
 (r'(?:çok )?merhamet eden', [('رحيم', 'Rahîm')]),
 (r'hakkıyla işiten', [('سميع', 'Semî’')]),
 (r'hakkıyla bilen', [('عليم', 'Alîm'), ('خبير', 'Habîr')]),
 (r'(?:hüküm ve )?hikmet sahibi', [('حكيم', 'Hakîm')]),
 (r'(?:hakkıyla )?gören', [('بصير', 'Basîr')]),
 (r'(?:hakkıyla )?haberdar', [('خبير', 'Habîr')]),
 (r'mutlak güç sahibi', [('عزيز', 'Azîz')]),
 (r'(?:\(?lütfu\)? )?geniş olan', [('واسع', 'Vâsi’')]),
 (r'çok affeden', [('عفو', 'Afüvv')]),
 (r'(?:mutlak )?zengin(?: olan)?', [('غني', 'Ganî')]),
 (r'(?:hamda|övülmeye) layık(?: olan)?', [('حميد', 'Hamîd')]),
 (r'çok şefkatli', [('رءوف', 'Raûf')]),
]
_ON = ['Allah','O','O,','Rabbin','Rabbim','Rabbiniz','Rabbimiz','Rableri','Rabbi','Sen','Ben','Biz','şüphesiz','Şüphesiz','ki','ve','çünkü','zira','Sen,','Rabbin,','Allah,']
ONCE = '(?:(?<=^)|' + '|'.join('(?<=%s\\s)' % re.escape(w) for w in _ON) + '|(?<=[,;:.!?"(]\\s))'
SON = r'(?P<ek>dır|dir|dur|dür|tır|tir|tur|tür|sın|sin|sun|sün|dırlar)?(?=[\s,.;:!?"’\')]|$)'

def esma(t, sa):
    L = lem(sa)
    for kal, adlar in ESMA:
        ad = None
        for l, a in adlar:
            if l in L: ad = a; break
        if not ad: continue
        def rep(m, ad=ad):
            ek = m.group('ek')
            if not ek:
                return m.group(0)
            gov = m.group(0)[:m.start('ek') - m.start()]
            # 'eden-dir' → ek sadece -dır kısmı; 'haberdar-dır'
            u = son_unlu(ad.rstrip(AP))
            e2 = bas_ses(uyum(ek, u), ad.rstrip(AP))
            return ad + ('' if ad.endswith(AP) else AP) + e2
        # kalıp + (an|en) son ekleri: '...eden' + 'dir'
        t = re.sub(ONCE + '(' + kal + ')' + SON, rep, t)
    return t

def kibir(m):
    ek = m.group(1)
    # tasla- (ünlü) → kibirlen- (ünsüz, ön)
    if ek.startswith(('ıyor', 'ıyo')): ek = 'iyor' + ek[4:]
    elif ek[:1] == 'r': ek = 'ir' + ek[1:]
    elif len(ek) >= 2 and ek[0] == 'y' and ek[1] in UNLU: ek = ek[1:]
    e2 = uyum(ek, 'e')
    if e2 and e2[0] not in UNLU: e2 = bas_ses(e2, 'kibirlen')
    return 'kibirlen' + e2

TAKAT = {'ü':'i','ünün':'inin','ümüz':'imiz','ünüz':'iniz','üm':'im','ün':'in','ümüzün':'imizin'}

def ifade(t, sa):
    for s_a, eski, yeni in AYET:
        if s_a == sa: t = t.replace(eski, yeni)
    t = re.sub(r'\b([Aa])ndolsun ki\b', lambda m: ('Y' if m.group(1) == 'A' else 'y') + 'emin olsun ki', t)
    # "X'e andolsun" (yemin edilen şeyden sonra) → yemin olsun
    t = re.sub(r'([\wâîû’]+(?:a|e|ya|ye)) andolsun(?=[,.;:!"])', r'\1 yemin olsun', t)
    t = re.sub(r'\b([Aa])ndolsun,?(?= )', lambda m: ('Y' if m.group(1) == 'A' else 'y') + 'emin olsun ki', t)
    t = re.sub(r'\b([Aa])ndolsun\b', lambda m: ('Y' if m.group(1) == 'A' else 'y') + 'emin olsun', t)
    t = re.sub(r'([Bb])üyüklük tasl([aı]\w*)', lambda m: (buyuk if m.group(1) == 'B' else (lambda x: x))(kibir(re.match(r'a?(.*)', m.group(2)) if m.group(2)[0]=='a' else re.match(r'(.*)', m.group(2)))), t)
    t = re.sub(r'\b([Gg])üç yetir(\w*)', lambda m: ('T' if m.group(1) == 'G' else 't') + 'akat getir' + m.group(2), t)
    t = re.sub(r'\b([Gg])üc(ü|ünün|ümüz|ünüz|üm|ün|ümüzün)(?= (?:\w+ )?yet)', lambda m: ('T' if m.group(1) == 'G' else 't') + 'akat' + TAKAT[m.group(2)], t)
    # neden → niçin (soru)
    def ned(m):
        rest = t[m.end():]
        cumle = re.split(r'[.!]', rest, maxsplit=1)[0]
        if '?' in cumle: return ('N' if m.group(1) == 'N' else 'n') + 'için'
        return m.group(0)
    t = re.sub(r'\b([Nn])eden\b', ned, t)
    t = esma(t, sa)
    t = re.sub(r'\b([Oo])rtak koşanlar(\w*)', lambda m: ('M' if m.group(1)=='O' else 'm') + 'üşrikler' + m.group(2), t)
    if 'فسق' in kok(sa):
        t = re.sub(r'\b([Yy])oldan çıkanlar(\w*)', lambda m: ('F' if m.group(1)=='Y' else 'f') + 'âsıklar' + m.group(2), t)
    if 'حسن' in kok(sa):
        t = re.sub(r'\b([İi])yilik edenler(\w*)', lambda m: ('M' if m.group(1)=='İ' else 'm') + 'uhsinler' + m.group(2), t)
    return t

KOK_S = sorted(KOK, key=lambda r: -len(r[0]))
def kelime(w, sa, kayit):
    """w: orijinal kelime (kesme dahil olabilir)"""
    base, ap = (w.split(AP, 1) + [None])[:2] if AP in w else (w, None)
    if ap is not None: ap_ek = ap
    lw = kucuk(base)
    full = lw + (ap if ap is not None else '')
    yeni = None
    if lw in TEK and ap is None:
        yeni = TEK[lw]
    elif lw in NANKOR_TEKIL and ap is None:
        if not nankor_kalsin(sa): yeni = NANKOR_TEKIL[lw]
    elif lw.startswith('yoksul') and ap is None:
        yeni = yoksul(lw, sa)
    elif lw.startswith('dost') and ap is None:
        yeni = dost(lw, sa)
    if yeni is None and not (lw in TEK or lw in NANKOR_TEKIL):
        for eski, f, haric, kosul in KOK_S:
            if lw.startswith(eski) and lw not in haric and not (eski == 'yasa' and lw.startswith(('yasak','yasağ'))):
                if kosul and not kosul(sa): continue
                if ap is None:
                    yeni = f(lw[len(eski):], sa)
                else:
                    if lw != eski: break
                    k0 = f('', sa); k1 = f(ap, sa)
                    if k0 and k1:
                        yeni = k0 + AP + k1[len(k0):] if k1.startswith(k0) else k1
                break
    if yeni is None: return w
    if ap is not None and AP not in yeni and lw in TEK: pass
    if base[:1].isupper(): yeni = buyuk(yeni)
    kayit[(full, yeni)] += 1
    return yeni

KEL = re.compile(r"[\wâîûÂÎÛ]+(?:’[\wâîû]+)?")
def donustur(t, sa, kayit):
    t = ifade(t, sa)
    return KEL.sub(lambda m: kelime(m.group(0), sa, kayit), t)

if __name__ == '__main__':
    d = json.load(open(os.path.join(BURADA, '..', '..', 'mealler', 'zahir.json')))
    kayit = collections.Counter()
    deg = 0
    cikti = {}
    for s, ss in d['ayetler'].items():
        for a, v in ss.items():
            yeni = donustur(v['metin'], f'{s}:{a}', kayit)
            if yeni != v['metin']:
                deg += 1
                cikti[f'{s}:{a}'] = (v['metin'], yeni)
    json.dump(cikti, open(os.path.join(BURADA, 'degisen.json'), 'w'), ensure_ascii=False, indent=0)
    with open(os.path.join(BURADA, 'ciftler.txt'), 'w') as f:
        for (e, y), n in sorted(kayit.items(), key=lambda x: x[0]):
            f.write(f'{n}\t{e}\t→ {y}\n')
    print('değişen ayet', deg, 'farklı çift', len(kayit))
