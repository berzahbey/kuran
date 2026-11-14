# Dedplay Kur'an Çalışma

Merkezinde Kur'an-ı Kerîm'in olduğu, tüm meal, tefsir, hadis ve lügat çalışmalarına ulaşılabilen kişisel kaynak ve çalışma platformu (ticari olmayan proje).

## Ana gövde: yalın meal
Uygulama açılınca okunan metin **en yalın Türkçe meal**dir. Uzun açıklama gereken yerlerde numara vardır, numaraya dokununca dipnot açılır. Arapça aslı üstteki **ع Arapça** düğmesiyle açılıp kapanır (tercih hatırlanır). E-kitap (EPUB) da aynı meali verir; istenirse Arapça aslı eklenir.

## Bir ayete tıklayınca: çalışma paneli
Panelde ayetin Arapçası ve yalın meali (✎ ile düzenlenir), altında 5 bölüm:

| Bölüm | İçerik |
|---|---|
| **Kelime & Lügat** | Her kelimenin kökü, kalıbı ve i'râbı Türkçe terimlerle. Köke tıklayınca Lane lügat maddesi (Lisânü'l-Arab, Tâc, Kâmûs, Sıhâh derlemesi) ve kökün Kur'an'daki tüm geçişleri. Kıraat farkı varsa (8 rivayet) burada. |
| **Mealler** | "Herkes böyle mi anlamış?" Tüm mealler yan yana: ortak anlam, ayrışan kelime tercihleri (kaç meal hangisini seçmiş), parantez içi eklemeler, benzer çizgideki meal grupları, renkli vurgular. Türkçe, İngilizce, Arapça vb.; ~90 dilde 492 meal tek tıkla. |
| **Tefsir & İniş** | Üstte nerede indiği (Mekkî/Medenî), iniş sırası, sebeb-i nüzûl (Vâhidî + rivâyet tefsirleri). Altında en eskiden günümüze 123 tefsir; türe (rivâyet, dirâyet, lügat/i'râb, işârî, kıraat, modern) ve dile göre süzülür. |
| **Hadis** | Kütüb-i Sitte + Muvatta (Arapça, Türkçe, İngilizce; ~100 bin metin). Ayetin metnini içeren rivayetler otomatik bağlanır. |
| **Notlarım** | Ayet veya sure bazında etiketli notlar. Tüm notlar aranır, Markdown olarak dışa aktarılır. Tefsirden alıntıyla not alınabilir. |

Klavye: ↑ ↓ ayetler arası, Esc kapat. Arama kutusu: Arapça, Türkçe veya `68:4` gibi ayet numarası.

## Kurulum (dedplay / ZimaOS)
1. ZimaOS → App Store → **Custom Install** → **Import** → bu depodaki `docker-compose.yml` içeriğini yapıştırın → Install.
   Komut satırından: `curl -O https://raw.githubusercontent.com/berzahbey/kuran/main/docker-compose.yml && docker compose up -d`
2. `http://dedplay:8120` açın. İlk açılışta tüm külliyat arka planda iner (~20 dk, ~2.3 GB). Durum: **Kaynaklar**.
3. İlk derlemeden sonra GitHub'da **Packages → kuran → Package settings → Change visibility → Public** yapın (yoksa sunucu imajı indiremez).

**Güncelleme:** `main`'e her gönderimde GitHub Actions yeni imajı `ghcr.io/berzahbey/kuran:latest` olarak derler.
Sunucuda `docker compose pull && docker compose up -d` (ZimaOS'ta uygulamanın "Update" düğmesi). Veriler `/DATA/AppData/kuran-calisma/veri` içinde kalır.

## Kaynaklar yerelde, eksikler internetten
Her şey uygulamanın kendi veritabanındadır, internetsiz çalışır. İnmemiş bir şey açılırsa o an internetten çekilir ve kaydedilir.

## Yalın meal üretimi (bir seferlik)
**Kaynaklar → Yalın meali üret** (veya `python app/uret.py --sureler 1-114`). Her ayet için kök/lügat, garîb eserleri, 9 klasik ve modern tefsir, 13 Türkçe ve 4 İngilizce meal okunur. Onaylı Kalem 1-7 üslubuyla yazılır, 'taslak' olarak kaydedilir. Meali olan ayete (onaylı veya elle düzeltilmiş) dokunulmaz, yarıda kalırsa kaldığı yerden devam eder. `ANTHROPIC_API_KEY` gerekir. Anahtar yoksa uygulamanın geri kalanı aynen çalışır.

## Veri kaynakları
- Arapça metin, 8 kıraat, 492 meal: github.com/fawazahmed0/quran-api
- Morfoloji/kök: github.com/mustafa0x/quran-morphology (Quranic Arabic Corpus tabanlı)
- Lügat: Lane, *An Arabic-English Lexicon*: github.com/laneslexicon/xml (kamu malı)
- Tefsirler: github.com/spa5k/tafsir_api
- Hadisler: github.com/fawazahmed0/hadith-api
- Font: Amiri Quran (SIL OFL)

Mealler ve modern tefsirlerin bir kısmı telif hakkına tabidir; uygulama kişisel çalışma içindir.

## Depo yapısı
- `app/`: uygulama (FastAPI + SQLite + web arayüzü), `kur.py` veri kurulumu, `uret.py` yalın meal üretimi, `kitap.py` EPUB
- `ornek/`: onaylı yalın mealler (ilk açılışta içeri alınır)
- `araclar/`: komut satırı araçları
