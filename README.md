# Work Mode & Focus Music · Romantic Piano — YouTube Otomasyonu

Aynı kod iki ayrı kanal profiliyle çalışır (`CHANNEL_PROFILE`):

| Profil | Ne üretir |
|---|---|
| `focus` (varsayılan) | Günlük 3–5 dk odak müziği + Short, 15 günde bir 30–60 dk derleme |
| `romantic` | **1 sa 20 dk – 3 sa+** uzunluğunda, sözsüz **romantik piyano** mixleri + Short ([aşağıda](#romantic-piano-kanalı)) |

Her profil ayrı bir Railway servisinde, kendi volume'u ve kendi YouTube kanalıyla çalışır.

## Focus profili

Her gün 3–5 dakikalık bir odak müziği videosu (ve ondan kesilmiş bir Short), her 15 günde bir de en çok dinlenen parçalardan 30–60 dakikalık bir derleme üretir. Her video önce **Telegram'a onaya** gelir. Onay verdiğinizde YouTube'a yüklenir ve belirlenen saatte yayınlanır.

```
09:00  Bot stili seçer → müzik (ElevenLabs) → görsel (Stability) → başlık/açıklama (Claude)
       → FFmpeg ile 1080p video + 9:16 Short + küçük resim
       → Telegram'a: kapak + ses önizlemesi + [✅ Onayla] [❌ Reddet] [🎵 Müzik] [🖼 Görsel] [✏️ Metin]
Onay → YouTube'a yüklenir, 17:00'de yayına girer (Short 5 saat sonra), stil playlist'ine eklenir
6 saatte bir → izlenme/beğeni istatistikleri çekilir, stil seçimi buna göre ağırlıklanır
15 günde bir → son 15 günün en çok dinlenen parçaları, enerji seviyesine göre sıralanıp crossfade ile
               birleştirilir, açıklamaya zaman damgalı parça listesi eklenir → onaya gelir
```

## Müzik stilleri

Birbirine yakın 8 "focus / work" stili döngüsel olarak kullanılır. Son 2 günün stili tekrar seçilmez. İzlenmesi yüksek stillerin seçilme şansı artar, ama hiç denenmemiş stillere de keşif payı kalır.

| Anahtar | Stil | Enerji |
|---|---|---|
| `lofi_hiphop` | Lo-fi Hip Hop | 3 |
| `chillhop_jazz` | Jazzy Chillhop | 4 |
| `ambient_piano` | Ambient Piano | 1 |
| `deep_focus_ambient` | Deep Focus Ambient | 1 |
| `chillwave_synth` | Chillwave / Soft Synth | 4 |
| `rain_lofi` | Rainy Lo-fi | 2 |
| `downtempo_organic` | Organic Downtempo | 3 |
| `acoustic_lofi` | Acoustic Lo-fi | 2 |

Derlemede parçalar en popüler olanla başlar ve enerji seviyesi en yakın parçayla devam eder; böylece geçişler kulağa yumuşak gelir. Yeterli parça yoksa en başarılı stilde derlemeye özel ek parça üretilir.

## Romantic Piano kanalı

```
09:00  (3 günde bir) Romantik piyano stili seçilir → ~5 dk'lık yeni parça (ElevenLabs, sözsüz, yumuşatılmış)
       → şömine arka planı + altında ateş çıtırtısı → başlık/açıklama (Claude) → 1080p video + Short → Telegram'a onay
15 günde bir → en çok dinlenen parçalar sıralanıp 12 sn yumuşak geçişlerle birleştirilir; 80–180 dk'ya yetmezse
               parçalar sırayla TEKRARLANIR (yeni müzik üretilmez, ElevenLabs kredisi harcanmaz) → onaya gelir
```

**Seriler (aynı kanalda, otomatik üretim sırayla döner):**

| Seri | Müzik | Temalar | Başlık türü | Playlist |
|---|---|---|---|---|
| 💕 `romance` | romantik topluluk (piyano, yaylılar, gitar, sax, çello) | şömine, mum ışığı, gün batımı, deniz… | Romantic Love Music | Romantic Love Music |
| ☕ `jazz` | cozy caz: piyano trio, sax, kontrbas, fırça davul, bossa nova | kafe, yağmur, şehir ışıkları, mum ışığı | Cozy Jazz Music | Cozy Jazz Nights |
| 😴 `sleep` | çok yavaş, vurmalısız ambient + piyano | yıldızlı gece, yağmur, kar, göl | Sleep Music | Sleep Music • Deep Relaxation |
| 🍃 `relax` | spa, doğa, meditasyon | orman, göl, deniz, çiçek | Relaxing Music | Relaxing Music • Calm & Healing |

Uzun derlemeler de seri bazındadır (bir derlemede tek seri) ve seriler arasında sırayla döner. Telegram: `/seriler`, `/uret jazz kafe sahne`, `/uret uyku`, `/derleme sleep`.

**Varsayılan: tek sahne.** Kısa videolar temaya uygun tek, sıcak bir mekânın ağır çekim döngüsüdür (şömineli oda, karlı dağ evi, yağmurlu pencere, kafe, sonbahar pikniği…). Uygun klip bulunamazsa şömine döngüsüne geçilir. Kolaj isteğe bağlı: `/uret … kolaj` ya da `/ayar daily_visual both`.

**Yapay zeka etiketi:** YouTube, yapay zekayla üretilen müziğin beyan edilmesini zorunlu tutuyor; bu yüzden yüklemelerde `containsSyntheticMedia` açık kalır. YouTube'a göre beyan erişimi ve para kazanmayı etkilemez.

**İki video tarzı (sırayla):** (1) **Tek sahne** — temaya uygun tek, sinematik bir mekân (şömineli oturma odası, mum ışığında akşam yemeği, yağmurlu pencere, karlı dağ evi…) atlamasız döngüde; (2) **Kolaj** — temadaki kısa klip ve fotoğraflar. `/uret sonbahar sahne` ya da `/uret deniz kolaj` ile seçilebilir; `/ayar daily_visual scene|collage|both`. Müzik her zaman küçük, uyumlu bir topluluktur (piyano + yaylılar, akustik gitar, yumuşak saksafon/çello, pad, hafif fırça davul). Başlıklar: *"<özgün duygusal ifade> ❤️ Romantic Love Music by the Fire | Cozy Night Ambience"* kalıbında, açıklamalar "Perfect for:" maddeli.

**Temalar ve görüntü:** Her parça bir temayla üretilir (deniz kenarı, sonbahar, orman, yağmur, kış, gün batımı, çiçek bahçesi, yıldızlı gece, göl, mum ışığı). Müzik talimatı temanın havasını anlatır; kısa videonun görüntüsü o temadaki Pexels kliplerinden ve fotoğraflarından yumuşak geçişli, atlamasız dönen bir **kolajdır** (aynı klip iki kez kullanılmaz). Uzun derlemelerde **şömine döngüsü** + çıtırtı kullanılır. Pexels anahtarı yoksa kısa videolarda da şömineye geçilir. Ücretsiz anahtar: pexels.com/api → `PEXELS_API_KEY`. Yayın saati 08:00; onay 08:00'den sonra gelirse ertesi sabah 08:00'e zamanlanır.

**Maliyet:** Kredi yalnızca 5 dk'lık parçalarda harcanır (parça başına ~2.600–4.400 kredi). 3 günde bir ≈ ayda 10 parça ≈ 30–45 bin kredi. Uzun derlemeler ücretsizdir. Kalan krediyi Telegram'da `/test` gösterir. `/ayar daily_every_days 2` sıklığı artırır (ayda ~65 bin kredi). İsteğe bağlı `/mix [dk]` tamamen yeni parçalardan uzun mix üretir (dakikada ~600–900 kredi).

Her parça bir romantik piyano stilinde üretilir; derlemede enerji seviyesi yakın parçalar art arda gelir.

| Anahtar | Stil | Enerji |
|---|---|---|
| `romantic_solo_piano` | Romantic Piano & Strings | 2 |
| `spa_massage_piano` | Spa & Massage Piano | 1 |
| `dreamy_ambient_love` | Dreamy Ambient Love | 1 |
| `piano_strings_love` | Piano & Warm Strings | 2 |
| `moonlight_piano` | Moonlight Night Piano | 1 |
| `piano_cello_romance` | Piano & Cello Romance | 2 |
| `candlelight_jazz_piano` | Candlelight Jazz Piano | 3 |
| `wedding_piano` | Wedding & First Dance Piano | 2 |
| `fireside_love_ballad` | Fireside Love Ballad (piyano + çello + akustik gitar) | 2 |
| `romantic_sax_lounge` | Romantic Sax & Piano Lounge | 3 |
| `acoustic_love_guitar` | Acoustic Love Guitar & Strings | 2 |
| `rainy_romance_piano` | Rainy Romance Piano | 1 |
| `classical_romance_piano` | Classical Romantic Piano | 2 |

**Spa / masaj yumuşaklığı:** Tüm stiller sıcak orta-pes registerda, yavaş (48–70 BPM), uzun notalı ve yumuşak pad'li olacak şekilde yazıldı. Müzik üretim talimatında tiz, ince, çan/zil benzeri sesler ve sert vuruşlar açıkça yasaklandı. Üretilen her parça ayrıca yumuşatılır: tizler kısılır, ani yükselmeler bastırılır, 5 sn yumuşak girişle başlar ve 10 sn'de söner (`/ayar soft_master 0` ile kapatılabilir). Parçalar arasındaki geçiş 12 sn'dir (`/ayar mix_crossfade_sec 4–20`).

### 🔥 Şömine modu (varsayılan açık)

Videoların arka planı, gerçek bir şöminede yanan ateş gibi atlamasız dönen bir döngüdür. Müziğin altında da hafif ateş çıtırtısı çalar.

- **Arka plan:** Bota Telegram'dan bir şömine **videosu** gönderin (10–40 sn yeter, en fazla 20 MB). Bot videonun sonunu başına yumuşakça bindirir; böylece video takılmadan sonsuz döner. Birden fazla video gönderirseniz her mixte farklı biri kullanılır. Hiç video yoksa yedek olarak **fotoğraflar** kullanılır (ışığı hafifçe titreyen 12 sn'lik döngü). En iyi sonuç için gerçek bir şömine videosu kullanın: Telegram'dan gönderin ya da GitHub'da `assets/fireplace/` klasörüne yükleyin (mp4/mov, en fazla 25 MB); bu klasördeki videolar da otomatik kullanılır.
- **Çıtırtı sesi:** Gönderdiğiniz videonun kendi sesi varsa o kullanılır (en doğal sonuç). Yoksa ElevenLabs ile bir kez şömine sesi üretilip saklanır. O da olmazsa sentezlenmiş çıtırtı kullanılır. Ses seviyesi `/ayar fire_volume 20` (0 = kapalı) ile ayarlanır.
- **Büyük (4K, 300 MB+) videolar:** Google Drive'a yükleyin ("Bağlantıya sahip olan herkes" ile paylaşın) ve bota `/video <link> [link2 …]` gönderin (tek mesajda birden fazla link olabilir). Dropbox ve doğrudan .mp4/.mov linkleri de çalışır (en fazla 3 GB). Her video otomatik olarak 1080p, 30 fps ve ilk 45 saniyeye küçültülür; ses korunur.
- **Birden fazla şömine videosu varsa** uzun derlemelerde arka plan **20–30 dakikada bir** 2 sn'lik yumuşak geçişle değişir (`/ayar bg_rotate 0|1`, `bg_rotate_min_min`, `bg_rotate_max_min`). Uzun video yeniden kodlanmadığı için hızlıdır ve ek disk gerektirmez.
- **Puanlama:** `/arkaplan yenile` önizlemelerinin ve yeni eklenen videoların altındaki 1⭐–5⭐ düğmeleriyle puan verin. 5⭐ bir video 3⭐'lıdan ~4 kat sık kullanılır, 1⭐ nadiren, 🚫 hiç. Uzun videolarda yüksek puanlılar öne alınır, 4–5⭐'lılar bir kez daha görünür.
- `/arkaplan` arka planları listeler, `/arkaplan sil <ad>` siler. `/ayar fireplace 0` ile şömine yerine yapay zeka sahne görsellerine dönülür.
- Hazırlanan döngüler `/data/assets/cache` içinde saklanır; her videoda yeniden işlenmez. Hareketli ateş çok detaylı olduğu için video dosyası büyüktür: 3 saatlik bir mix yaklaşık 2,5 GB olur (yükleme sonrası silinir).

**Ayarlar** (`/ayar`): `mix_min_min=80`, `mix_max_min=180` (ör. hep 3 saat+ için `/ayar mix_min_min 180` ve `/ayar mix_max_min 210`), `mix_every_days=2`, `mix_reuse_pct=25`, `library_keep_days=14`. Parça uzunluğu `daily_min_sec` / `daily_max_sec` (180–300 sn).

**Maliyeti düşüren parça kütüphanesi:**
- Reddedilen ya da yarıda kalan bir mixin parçaları silinmez. Bir sonraki mix önce bu parçaları kullanır, yani bunlar için yeniden ödeme yapılmaz.
- Daha önce yayınlanmış parçalar, mixin en fazla `%mix_reuse_pct` kadarını doldurabilir (varsayılan %25). Son 3 mixte geçen parçalar kullanılmaz ve tekrar kullanılan parçalar mixin içine dağıtılır.
- `library_keep_days`'ten eski parça sesleri her gece 04:00'te silinir; böylece disk dolmaz.

**Maliyet:** Her mix, süresi kadar ElevenLabs müziği tüketir. Örneğin 2 günde bir ortalama 130 dk ve %25 tekrar kullanım ayda yaklaşık 15 × 100 ≈ **1.500 dk** müzik eder. ElevenLabs planınızın aylık müzik dakikasına göre `mix_every_days`, `mix_max_min` ve `mix_reuse_pct` ayarlarını düzenleyin. Bir mixin üretimi parça sayısına göre 20–60 dk sürer.

**Kurulum:** Aşağıdaki adımlar aynıdır. Farklar şunlar:
- Ayrı bir YouTube kanalı açın (ad, görseller ve İngilizce açıklama: `branding/CHANNEL.md`), `scripts/youtube_auth.py` ile **o kanal için** ayrı bir refresh token alın. Google Cloud projesi ortak olabilir.
- Railway'de **ayrı bir proje** açın (önerilen; değişkenler, volume, loglar ve fatura karışmaz), aynı GitHub reposundan deploy edin ve servise **ayrı bir volume** (`/data`) bağlayın.
- Değişkenler: `CHANNEL_PROFILE=romantic`, yeni kanalın `YOUTUBE_REFRESH_TOKEN`'ı ve **ayrı bir Telegram botu** (`TELEGRAM_BOT_TOKEN`; iki servis aynı token ile çalışamaz).
- 15 dakikadan uzun video yükleyebilmek için kanalın telefonla doğrulanmış olması **şarttır**.

Anahtarları girdikten sonra ilk iş `DRY_RUN=1` ile `/demo` yazın: gerçek ElevenLabs müziğiyle 10 dk'lık bir deneme mix'i üretilir ve ses önizlemesi Telegram'a gelir (`/demo 5 moonlight_piano` gibi süre/stil de verilebilir). Telegram'da `/uret [stil]` hemen yeni mix üretir, `/kutuphane` ise yeniden kullanılabilir parçaları gösterir. Onay kartında "🎵 Müzik" düğmesi yoktur (mixi reddedip `/uret` deyin; parçalar boşa gitmez).

## Telegram komutları

| Komut | İşlev |
|---|---|
| `/uret [stil]` | Şimdi günlük video üret |
| `/derleme` | Şimdi derleme üret |
| `/bekleyenler` | Onay bekleyen kartları tekrar gönder |
| `/onayla <id>` · `/reddet <id>` | Yazıyla onay/ret |
| `/baslik <id> <metin>` | Başlığı elle değiştir |
| `/durum` | Genel durum, sıradaki işler, son videolar |
| `/istatistik` | Kanal istatistikleri, en çok izlenenler, stil ortalamaları |
| `/stiller` · `/stil <anahtar> ac\|kapat` | Stilleri gör, aç ya da kapat |
| `/ayar` · `/ayar <anahtar> <değer>` | Saatler, süreler, Short, otomatik onay vb. |
| `/duraklat` · `/devam` | Otomasyonu durdur ya da sürdür |
| `/test` | API anahtarlarını ve YouTube bağlantısını kontrol et |
| `/log` | Son log satırları |

Varsayılan ayarlar: üretim 09:00, yayın 17:00 (İstanbul; ABD doğu yakasında 10:00), parça 180–300 sn, derleme 15 günde bir ve 30–60 dk, Short 45 sn, onay hatırlatması 4 saatte bir, otomatik onay kapalı.

---

## Kurulum (bir kerelik)

### 1. YouTube kanalı
1. YouTube'da yeni bir kanal açın. Brand Account önerilir; böylece kanal kişisel hesabınızdan ayrı olur.
2. youtube.com/verify adresinden **telefon doğrulaması** yapın. Bu yapılmazsa özel küçük resim yüklenemez ve 15 dakikadan uzun video yüklenemez.

### 2. Google Cloud (YouTube API)
1. console.cloud.google.com adresinde yeni bir proje oluşturun.
2. **APIs & Services → Library** bölümünden **YouTube Data API v3**'ü etkinleştirin.
3. **OAuth consent screen** ayarları: User type olarak *External* seçin, uygulama adını girin ve kendi e-postanızı *Test user* olarak ekleyin.
4. Ardından **Publishing status → "In production"** yapın. *Testing* modunda kalırsa token 7 günde bir geçersiz olur. "Unverified app" uyarısı görürseniz, kendi kullanımınız için "Advanced → devam et" demeniz yeterli.
5. **Credentials → Create credentials → OAuth client ID** adımında tür olarak *Desktop app* seçin. Client ID ve Client Secret değerlerini not alın.
6. Kendi bilgisayarınızda şunu çalıştırın:
   ```bash
   pip install google-auth-oauthlib
   python scripts/youtube_auth.py <CLIENT_ID> <CLIENT_SECRET>
   ```
   Açılan tarayıcıda kanalın hesabını (Brand Account ise o kanalı) seçin. Ekrana yazılan `YOUTUBE_REFRESH_TOKEN` değerini saklayın.

### 3. ⚠️ YouTube API denetimi (audit) — mutlaka yapılmalı
Google, 28 Temmuz 2020'den sonra oluşturulmuş ve denetimden geçmemiş projelerden API ile yüklenen videoları **"Özel" (private) olarak kilitler**. Kilidin açılması için:
- "YouTube API Services – Audit and Quota Extension Form" başvurusunu yapın (Google Cloud konsolunda YouTube API sayfasından ya da "YouTube API audit form" aramasıyla ulaşılır).
- Başvuruda kendi kanalınıza, kendi ürettiğiniz içeriği yükleyen kişisel bir otomasyon olduğunu belirtin. Telegram üzerinden insan onayı olduğunu da yazın.
- Onay gelene kadar bot normal çalışır ama videolar private kalır. Bot bu durumu fark edince Telegram'dan uyarı gönderir. Bu sürede videoları YouTube Studio'dan elle "Herkese açık" yapabilirsiniz.

### 4. Diğer API anahtarları
- **ElevenLabs** (müzik, zorunlu): elevenlabs.io → Profile → API Keys. Ticari kullanım hakkı veren ücretli bir plan seçin.
- **Anthropic** (başlık ve açıklama): console.anthropic.com → API Keys.
- **Stability AI** (kapak görselleri): platform.stability.ai → API Keys.
- **Telegram**: @BotFather → `/newbot` → token. Kendi ID'nizi öğrenmek için bota `/start` yazın; bot, ID'nizi söyler.

### 5. Railway'e kurulum
1. railway.com → **New Project → Deploy from GitHub repo** → bu repoyu seçin. Railway `Dockerfile` ve `railway.json`'u otomatik kullanır.
2. Servise **Volume** ekleyin ve bağlama noktası olarak `/data` girin. Veritabanı, sesler ve görseller burada tutulur.
3. **Variables** bölümüne `.env.example`'daki değişkenleri girin.
4. İlk deneme için `DRY_RUN=1` ile başlatın, Telegram'dan `/test` ve `/uret` çalıştırın. Her şey yolundaysa `DRY_RUN=0` yapın.

Tahmini aylık maliyet: Railway yaklaşık $5–10, ElevenLabs plan ücreti (ayda yaklaşık 210 dk müzik), Stability ve Claude ise birkaç dolar.

## Yerel geliştirme

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt     # ffmpeg sistemde kurulu olmalı
pytest -q                               # müzik API'si sahte, gerçek FFmpeg ile uçtan uca test
DATA_DIR=./data DRY_RUN=1 TELEGRAM_BOT_TOKEN=... TELEGRAM_ADMIN_IDS=... python -m app.main
```

## Notlar ve öneriler
- **Para kazanma (YPP):** YouTube, seri üretilmiş ve birbirine çok benzeyen içerikleri "inauthentic content" olarak değerlendirip para kazanmayı reddedebilir. Onay adımı, stil/görsel/başlık çeşitliliği ve yapay zeka beyanı (`containsSyntheticMedia`) bu riski azaltmak için var. Onay adımını kapatmamanız önerilir.
- **Telif:** Yapay zeka ile üretilen müzik çoğu ülkede telif korumasına sahip değildir. Parçaları Content ID'ye kaydettirmeyin; başkalarının videolarına yanlış hak talebi düşebilir.
- **Kota:** Günde 2 yükleme (video + Short) varsayılan API kotası içinde rahatça kalır.
