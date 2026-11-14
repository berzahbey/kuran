"""Osmanlıca metinde kelime sonu / ünsüz ek önündeki gereksiz şeddeyi kaldırır.
Kullanım: python3 sedde_duzelt.py dosya.json [...]"""
import json, re, sys
SH = 'ّ'
AR = '؀-ۿّ‌'
KOK = r'^(ربّ|حقّ|عفوّ|تامّ|حدّ|ردّ|شرّ|سرّ|حجّ(?!ت)|حسّ|حرّ|ظنّ|حلّ|مهمّ|حیّ|رسّ|شحّ)(?=[دتلجچسزكگ])'
KORU = {'امّ', 'علیّ'}

def duzelt(t):
    def f(m):
        w = m.group(0)
        if w.startswith('الل') or w in KORU:
            return w
        w = re.sub(SH + r'$', '', w)
        return re.sub(KOK, lambda q: q.group(1)[:-1], w)
    return re.sub('[' + AR + ']+', f, t)

def gez(x):
    if isinstance(x, dict): return {k: gez(v) for k, v in x.items()}
    if isinstance(x, list): return [gez(v) for v in x]
    if isinstance(x, str): return duzelt(x)
    return x

if __name__ == '__main__':
    for f in sys.argv[1:]:
        raw = open(f).read()
        d = json.loads(raw)
        ind = 1 if raw.startswith('{\n "') else (2 if raw.startswith('{\n  ') else None)
        open(f, 'w').write(json.dumps(gez(d), ensure_ascii=False, indent=ind) + ('\n' if raw.endswith('\n') else ''))
