"""lemma.json'u Kur'an veritabanından (kelime tablosu) üretir: python lemma_kur.py /veri/kuran.db"""
import sqlite3, re, json, sys, os, collections
def sade(x): return re.sub(r'[ً-ٰٟۖ-ۭـ]', '', x).replace('ٱ','ا').replace('أ','ا').replace('إ','ا').replace('آ','ا')
c = sqlite3.connect(sys.argv[1] if len(sys.argv) > 1 else '/veri/kuran.db')
L = collections.defaultdict(set); R = collections.defaultdict(set)
for s, a, lem, kok in c.execute('select s,a,lemma,kok from kelime'):
    if lem: L[f"{s}:{a}"].add(sade(lem))
    if kok: R[f"{s}:{a}"].add(kok)
json.dump({'L': {k: sorted(v) for k, v in L.items()}, 'R': {k: sorted(v) for k, v in R.items()}},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lemma.json'), 'w'), ensure_ascii=False)
