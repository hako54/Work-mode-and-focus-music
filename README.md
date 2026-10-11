# Work Mode & Focus Music — YouTube Otomasyonu

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
