# Dedplay Kur'an Çalışma

Türkçe yalın Kur'an meali ve Kur'an çalışma uygulaması (kişisel, ticari olmayan proje).

Kur'an üzerinde çalışma uygulaması. Bir ayeti ya da sureyi açtığınızda tek ekranda şunları görürsünüz:

| Sekme | İçerik |
|---|---|
| **Arapça & Kıraat** | Hafs mushaf metni + 7 rivayet (Şu'be, Verş, Kâlûn, Bezzî, Kunbul, Dûrî, Sûsî). Farklı okunan yerler işaretli. |
| **Kelime & Kök** | Her kelimenin kökü, kalıbı ve i'râbı (Türkçe gramer terimleriyle). Köke tıklayınca Lane lügat maddesi (Lisânü'l-Arab, Tâc, Kâmûs, Sıhâh derlemesi) ve kökün Kur'an'daki tüm geçişleri açılır. |
| **Karşılaştır** | Tüm mealler yan yana: ortak anlam, ayrışan kelime tercihleri (kaç meal hangi kelimeyi seçmiş), benzer çizgideki meal grupları. Yapay zekâ gerekmez. |
| **İniş** | Mekkî/Medenî, iniş sırası; Vâhidî'nin Esbâbü'n-Nüzûl'ü ve rivâyet tefsirlerinde iniş sebebiyle ilgili kısımlar. |
| **Mealler** | ~90 dilde 492 meal (60 Türkçe). Dile göre süzülebilir. |
| **Tefsirler** | ~120 tefsir, en eskiden günümüze (Tenvîru'l-Mikbâs, Taberî … İbn Âşûr, Muhtasar). Tür (rivâyet, dirâyet, lügat/i'râb, işârî, kıraat, modern) ve dile göre süzülebilir. |
| **Hadisler** | Kütüb-i Sitte + Muvatta (Arapça + Türkçe + İngilizce, ~100 bin metin). Ayetin metnini içeren rivayetler otomatik bağlanır. |
| **Görüşler** | Yapay zekâ tüm tefsir ve mealleri okur: ortak görüşler, farklı görüşler (kim ne demiş), kelime notları, kronolojik gelişim. Sonuç kaydedilir. |
| **Yalın Meal** | E-kitaba girecek meal + dipnotlar; taslak/onaylı durumu. Yapay zekâ önerisi alınabilir. |
| **Notlar** | Ayet veya sure bazında etiketli notlar. Tüm notlar aranabilir, Markdown olarak dışa aktarılabilir. |

**E-Kitap:** Seçilen sureler EPUB3 olarak indirilir. Her ayette Arapça aslı (Amiri Quran fontu gömülü) + yalın meal. Dipnot numarasına dokununca açıklama açılır.

## Yalın meal üretimi (bir seferlik)
`Kaynaklar` → **Yalın meali üret** (veya `python app/uret.py --sureler 1-114`). Her ayet için kök/lügat, 11 klasik ve modern tefsir, 13 Türkçe ve 4 İngilizce meal okunur. Onaylı Kalem 1-7 üslubuyla yazılır ve 'taslak' olarak kaydedilir. Meali olan ayete dokunulmaz. `ANTHROPIC_API_KEY` gerekir.

## Kaynaklar yerelde, eksikler internetten
- İlk açılışta tüm külliyat arka planda `/veri/kuran.db` içine iner (~15–20 dk). Sonrasında internetsiz çalışır.
- İnmemiş bir şey açılırsa o an internetten çekilir ve kaydedilir.
- "Kaynaklar" penceresinden durum takip edilir; "Tüm kaynakları indir / güncelle" ile yeniden çalıştırılabilir.

## Kurulum (dedplay / ZimaOS)
1. ZimaOS → App Store → **Custom Install** → **Import** → bu depodaki `docker-compose.yml` içeriğini yapıştırın → Install.
   Komut satırından: `curl -O https://raw.githubusercontent.com/berzahbey/kuran/main/docker-compose.yml && docker compose up -d`
2. Tarayıcıda `http://dedplay:8120` açın. İlk açılışta tüm külliyat arka planda iner (~20 dk, ~2.3 GB).
3. Yapay zekâ özellikleri için `ANTHROPIC_API_KEY` değerini girin.

**Güncelleme:** Her `main` gönderiminde GitHub Actions yeni imajı `ghcr.io/berzahbey/kuran:latest` olarak derler.
Sunucuda: `docker compose pull && docker compose up -d` (ZimaOS'ta uygulamanın ayarlarından "Update"). Veriler `/DATA/AppData/kuran-calisma/veri` içinde kalır.

## Elle veri kurulumu
```bash
python app/kur.py                                  # her şey
python app/kur.py --asama tefsir --sureler 68      # sadece Kalem tefsirleri
```

## Veri kaynakları
- Arapça metin, kıraatler, mealler: github.com/fawazahmed0/quran-api
- Morfoloji/kök: github.com/mustafa0x/quran-morphology (Quranic Arabic Corpus tabanlı)
- Lügat: Lane, *An Arabic-English Lexicon*: github.com/laneslexicon/xml (kamu malı)
- Tefsirler: github.com/spa5k/tafsir_api
- Hadisler: github.com/fawazahmed0/hadith-api
- Font: Amiri Quran (SIL OFL)

Mealler ve modern tefsirlerin bir kısmı telif hakkına tabidir. Uygulama kişisel çalışma içindir.

## Depo yapısı
- `app/` uygulama (FastAPI + SQLite + web arayüzü)
- `ornek/` onaylı yalın mealler (ilk açılışta içeri alınır)
- `araclar/` komut satırı araçları (sure verisi toplama, EPUB)
