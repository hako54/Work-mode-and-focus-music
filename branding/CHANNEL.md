# Ember & Keys — Channel Kit

> Kurulum notları Türkçe, YouTube'a girilecek tüm metinler İngilizce.
> YouTube Studio → **Customization (Özelleştirme)** bölümünde ilgili alanlara kopyalayın.

## Name & handle

| Field | Value |
|---|---|
| **Channel name** | Ember & Keys |
| **Handle** | `@EmberAndKeys` (dolu ise: `@EmberAndKeysMusic`, `@EmberKeysPiano`) |
| Alternatives | Fireside Serenade · Candlelight Keys · Hearth & Heart Piano |

Neden bu ad: *Ember* (şömine közü) + *Keys* (piyano tuşları). Kısa, akılda kalıcı, aramada ayırt edilebilir ve kanalın iki imzasını (ateş + piyano) tek seferde anlatıyor. Web aramasında aynı adlı bir YouTube kanalı bulunamadı; yine de handle'ı YouTube'da girerken müsaitliği kontrol edin.

## Images (`branding/`)

| File | Where | Size |
|---|---|---|
| `profile.png` | Customization → Branding → Picture | 800×800 (daire olarak kırpılır) |
| `banner.png` | Customization → Branding → Banner image | 2560×1440 (yazılar mobil güvenli alanda) |
| `watermark.png` | Customization → Branding → Video watermark (End of video / Entire video) | 150×150, şeffaf |

Yeniden üretmek ya da adı değiştirmek için: `python scripts/make_branding.py "Fireside Serenade"`

## Channel description (paste as-is, 912 characters; limit 1000)

```
Welcome to Ember & Keys — a quiet corner of the internet where soft romantic piano meets the warm crackle of a fireplace.

Every video is a long, slow, uninterrupted mix (1 to 3+ hours) of gentle, tender piano: warm low tones, smooth transitions and no sudden or sharp sounds. Just glowing embers, soft melodies and a calm that lasts all evening.

Made for:
🔥 Cozy romantic evenings and candlelit dinners
💆 Massage, spa and self-care sessions
📖 Reading, journaling and slow mornings
😴 Falling asleep and deep relaxation
💕 Date nights, anniversaries and quiet moments together

New long mixes every two days. Subscribe and turn on notifications so your next evening by the fire is always ready.

The music and visuals on this channel are created with the help of AI tools and carefully selected and arranged by us. Every mix is original — no copyrighted songs or covers.

Ember & Keys — soft piano by the fire. 🎹🔥
```

## Channel keywords (Settings → Channel → Basic info → Keywords)

```
romantic piano, fireplace music, relaxing piano, spa music, massage music, crackling fireplace, piano and fire, romantic music, love songs instrumental, sleep music, calm piano, candlelight dinner music, cozy music, relaxing music for couples, soft piano music, ember and keys
```

## Links (Customization → Basic info → Links)

- Title: `Subscribe` → `https://www.youtube.com/@EmberAndKeys?sub_confirmation=1`

## Channel trailer / featured video

Kanal sayfasında ilk izlenen video için en çok izlenen 3 saatlik mixi seçin
(Customization → Layout → *Featured video for returning subscribers*).

## Default upload description footer (bot otomatik ekler)

```
Music and visuals are created with AI tools and curated by the channel.
#romanticmusic #pianomusic #lovemusic
```

## Railway

`CHANNEL_NAME=Ember & Keys` (boş bırakırsanız varsayılan da artık bu).
