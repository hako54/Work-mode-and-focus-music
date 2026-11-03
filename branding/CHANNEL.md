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

## Channel description (paste as-is, 981 characters; limit 1000)

```
Welcome to Evermore Romance Piano — soft, original love music for the moments you want to last forever. 🌙

Gentle piano, warm strings, tender guitar and mellow saxophone blend into calm, romantic melodies — no sudden or sharp sounds, just warmth and peace.

On this channel you'll find:
❤️ Romantic love music for date nights & intimate moments
🔥 Cozy fireplace & candlelight ambience
🌧️ Rainy, snowy and starry night romance
💆 Soft music for massage, spa & relaxation
😴 Long 1–3 hour mixes for sleep & quiet evenings

New romantic music every few days, plus a long mix of your favorites every two weeks.

Sharing a quiet evening with someone special or unwinding after a long day — let the music set the mood.

The music and visuals are created with the help of AI tools and carefully curated by us. Every piece is original — no covers or copyrighted songs.

🎹 Love, played softly. Forever.

#RomanticMusic #LoveMusic #RomanticPiano #CozyNight #RelaxingMusic #EvermoreRomancePiano
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
