"""Onaylanmış Kalem 1-7 pilotunu yalın meal tablosuna aktarır (her ayette dipnotlar 1'den numaralanır)."""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(__file__)); import veri as V
d = json.load(open(sys.argv[1])); c = V.baglan()
c.execute("CREATE TABLE IF NOT EXISTS yalin_meal(s INT, a INT, metin TEXT, dipnotlar TEXT, durum TEXT DEFAULT 'taslak', guncelleme TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(s,a))")
for ay in d["ayetler"]:
    notlar = []
    def f(m): notlar.append(d["dipnotlar"][m[1]]); return f"[{len(notlar)}]"
    metin = re.sub(r"\[(\d+)\]", f, ay["meal"])
    c.execute("INSERT OR REPLACE INTO yalin_meal(s,a,metin,dipnotlar,durum) VALUES(?,?,?,?,'onayli')", (d["sure"], ay["no"], metin, json.dumps(notlar, ensure_ascii=False)))
c.commit(); print("aktarıldı:", len(d["ayetler"]))
