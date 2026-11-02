# Evermore Romance Piano — Channel Kit

> Kurulum notları Türkçe, YouTube'a girilecek tüm metinler İngilizce.
> YouTube Studio → **Customization (Özelleştirme)** bölümünde ilgili alanlara kopyalayın.

## Name & handle

| Field | Value |
|---|---|
| **Channel name** | Evermore Romance Piano |
| **Handle** | `@EvermoreRomancePiano` |
| **Channel URL** | https://www.youtube.com/@EvermoreRomancePiano |

"Evermore" = sonsuza dek. Saatlerce süren, hiç bitmeyen romantik piyano mixlerine gönderme yapar.
Not: "Evermore" aynı zamanda Taylor Swift'in bir albümünün adı. Karışıklığı önlemek için başlık ve açıklamalarda
"original piano" vurgusu korunuyor; Taylor Swift ya da başka sanatçı adlarını etiket olarak asla kullanmayın.

## Images (`branding/`) — YouTube ölçülerinde, kırpma gerekmez

| File | Where | Size | Notes |
|---|---|---|---|
| `banner.png` | Customization → Branding → Banner image | **2560×1440** (YouTube önerilen) | **Seçilen: B Moonlight.** Kanal adı ve "Soft Romantic Piano · Relaxing · Calm · Sweet Dreams" ortadaki **1546×423** güvenli alanda; her cihazda tam görünür |
| `profile.png` | Customization → Branding → Picture | **800×800** (YouTube önerilen) | Banner ile uyumlu yıldızlı lacivert zemin; altın kalp, "ER" monogramı ve tuşlar dairesel kırpmanın içinde; 88 px'te bile okunur |
| `watermark.png` | Customization → Branding → Video watermark | **150×150**, şeffaf | Videonun sağ alt köşesinde ince kalp |

**Banner alternatifleri** (`branding/banner_alternatives/`, hepsi 2560×1440, yazılar güvenli alanda; `_overview.jpg` hepsini mavi güvenli-alan çerçevesiyle gösterir):

| File | Concept |
|---|---|
| `banner_A_rose_keys.png` | Burgundy bokeh, ivory piano keys, rose petals |
| `banner_B_moonlight.png` | **Selected** — midnight-blue starry sky, crescent moon, warm horizon glow (= `banner.png`) |
| `banner_C_blush.png` | Light & elegant: cream-blush background, wine-red title, rose petals |
| `banner_D_candlelight.png` | Dark warm room, glowing candles on both sides |
| `banner_E_melody.png` | Burgundy bokeh, flowing gold music staff with notes |

Yükleme ekranında YouTube "Adjust/Crop" gösterirse hiçbir şeye dokunmadan **Done** deyin.
Yeniden üretmek: `python scripts/make_branding.py "Evermore Romance Piano"`

## Channel description (paste as-is, 919 characters; limit 1000)

```
Welcome to Evermore Romance Piano — soft, original piano music for a love that lasts forever.

Every video is a long, slow, uninterrupted mix (1 to 3+ hours) of tender, gentle piano: warm low tones, smooth transitions and no sudden or sharp sounds. Some mixes are paired with the soft crackle of a fireplace for an even cozier evening.

Made for:
🌹 Romantic evenings and candlelit dinners
💆 Massage, spa and self-care sessions
📖 Reading, journaling and slow mornings
😴 Falling asleep and deep relaxation
💕 Date nights, anniversaries and quiet moments together

New long mixes every two days. Subscribe and turn on notifications so your next romantic evening always has its soundtrack.

The music and visuals on this channel are created with the help of AI tools and carefully selected and arranged by us. Every mix is original — no copyrighted songs or covers.

Evermore Romance Piano — love, played softly, forever. 🎹🌹
```

## Channel keywords (Settings → Channel → Basic info → Keywords)

```
romantic piano, love music, relaxing piano, romantic music, instrumental love songs, original piano music, spa music, massage music, sleep music, calm piano, candlelight dinner music, wedding piano, soft piano music, piano for couples, fireplace piano, evermore romance piano, evermore romance
```

## Links (Customization → Basic info → Links)

- Title: `Subscribe` → `https://www.youtube.com/@EvermoreRomancePiano?sub_confirmation=1`
- Title: `Long Mixes` → `https://www.youtube.com/@EvermoreRomancePiano/videos`

Video açıklamalarına ve sosyal medyaya koymak için abone bağlantısı:
`https://www.youtube.com/@EvermoreRomancePiano?sub_confirmation=1`

## Featured video

Kanal sayfasında ilk izlenen video için en çok izlenen 3 saatlik mixi seçin
(Customization → Layout → *Featured video for returning subscribers*).

## Railway

`CHANNEL_NAME=Evermore Romance Piano` ve `CHANNEL_HANDLE=EvermoreRomancePiano` (boş bırakırsanız varsayılan da bunlar).
Bot her video açıklamasına otomatik olarak şunu ekler:
`🔔 Subscribe to Evermore Romance Piano: https://www.youtube.com/@EvermoreRomancePiano?sub_confirmation=1`
