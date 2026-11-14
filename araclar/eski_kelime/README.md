# Eski kelime tercihleri

Zahir'in mealindeki yeni ve öz Türkçe kelimeleri, Hayrat Osmanlıca meali çizgisindeki Arapça kökenli karşılıklarıyla değiştirir.
Örnekler: andolsun → yemin olsun, ad → isim, toplum → kavim, elçi → resul, çok bağışlayandır → Gafûr'dur.

- `kurallar.py`: kelime ve kök tabloları. Yeni bir tercih buraya eklenir.
- `motor.py`: ek uyumu (ünlü uyumu, kaynaştırma, "X et-" fiilleri).
- `donustur.py`: ifade kuralları (yemin, esmâ, ortak koşanlar...) ve çalıştırıcı.
- `lemma.json`: her ayetin Arapça lemma ve kökleri. Koşullu kurallar bunlara bakar (yoksul → miskin/fakir, dost → velî, uyarmak → inzar). `python lemma_kur.py /veri/kuran.db` ile yeniden üretilir.

Çalıştırma: `python donustur.py` → `degisen.json` ve `ciftler.txt` (eski → yeni kelime çiftleri) yazar; mealler/zahir.json'u değiştirmez.

## Şedde kuralı (Osmanlıca)

Kelime sonundaki çift ünsüz (hakk, rabb, tamm, hacc…) yalnızca ardından ünlüyle başlayan bir ek gelince
okunur ve şedde ancak o zaman yazılır: حقّی، حقّنده، ربّڭ، ربّم. Ek yoksa ya da ek ünsüzle başlıyorsa
şedde yazılmaz: حق، رب، تام، ربلری، حقدر، عفودر (Hayrat Osmanlıca meali de böyle yazar).
Kelime içindeki şeddeler (جنّت، شدّت، دقّت، امّت، قوّت) ve اللّه olduğu gibi kalır.
`sedde_duzelt.py` dönüştürücü çıktısına bu kuralı uygular.
"Hayy'dır" gibi "Haydar" diye okunabilecek yerlerde ek ZWNJ ile ayrılır: حی‌در.
