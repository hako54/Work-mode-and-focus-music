"""Telegram botu: onay akışı, komutlar ve zamanlanmış işler."""
from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from . import fireplace, metadata, profiles
from .config import CONFIG
from .db import Database, parse_iso, utcnow
from .media import fmt_ts
from .pipeline import LONG_KINDS, Pipeline
from .profiles import SETTING_HELP, default_settings
from .styles import STYLE_BY_KEY, active_styles
from .series import SERIES, find_series
from .themes import EN_LABEL, THEMES, find_theme

log = logging.getLogger(__name__)
KIND_TR = {"daily": "Günlük", "short": "Short", "compilation": "Derleme", "mix": "Uzun Mix"}
STATUS_TR = {"pending": "⏳ onay bekliyor", "scheduled": "🗓 zamanlandı", "published": "✅ yayında",
             "rejected": "🗑 reddedildi", "failed": "⚠️ hata", "building": "🔧 hazırlanıyor",
             "uploading": "⬆️ yükleniyor"}

HELP_PRODUCTION = {
    "focus": """<b>🎧 Focus Music Otomasyonu</b>

<b>Üretim</b>
/uret [stil] – şimdi günlük video üret
/derleme – şimdi uzun derleme üret
""",
    "romantic": """<b>💕 Evermore Romance Piano – Komutlar</b>

<i>Otomatik: 3 günde bir ~5 dk parça + Short (💕→☕→😴→🍃 sırayla), 15 günde bir 80–180 dk derleme
(şömine). Yayın 08:00. Her video onayınıza gelir.</i>

<b>🎵 Üretim</b>
/uret [seri] [tema] [sahne|kolaj] – yeni parça + Short (kredi harcar; takvimi kaydırmaz)
   ör. /uret jazz kafe sahne · /uret uyku yagmur · /uret sonbahar
/derleme [seri] – en çok dinlenenlerden uzun video (kredisiz)
/mix [dk] – tamamı yeni parçalardan uzun mix (çok kredi harcar)

<b>🎧 Parçalar</b>
/parcalar – kullanılmamış parçaları dinle → Video yap / Sil (kredisiz)
/kullanilan – yayınlananlar, en çok izlenenden aza
/dinle &lt;#no&gt; – bir parçayı tekrar dinle

<b>🗂 Seçenekler</b>
/seriler · /temalar · /stiller · /stil &lt;anahtar&gt; ac|kapat

<b>🔥 Arka plan (şömine)</b>
Bota video/fotoğraf gönder (en fazla 20 MB)
/video &lt;link&gt; [link2 …] – 4K/büyük videoları Drive/Dropbox linkiyle ekle
/arkaplan · /arkaplan sil &lt;ad&gt;

<b>✅ Onay</b>
Kartta: ✅ Onayla (08:00) · ⚡ Hemen yayınla · ❌ Reddet · 🎵 Müzik / 🖼 Görsel / ✏️ Metin yenile
""",
}

HELP_COMMON = """/bekleyenler – onay bekleyenleri tekrar göster
/onayla &lt;id&gt; · /reddet &lt;id&gt;
/baslik &lt;id&gt; &lt;yeni başlık&gt; – başlığı elle değiştir

<b>Durum</b>
/durum – genel durum ve sıradaki işler
/istatistik – kanal ve video istatistikleri
/log – son log satırları
/test – API bağlantılarını kontrol et

<b>Ayarlar</b>
/ayar – ayarları göster · /ayar &lt;anahtar&gt; &lt;değer&gt;
/stiller – stiller ve performansları · /stil &lt;anahtar&gt; ac|kapat
/duraklat · /devam – otomasyonu durdur / sürdür"""


def help_text() -> str:
    return HELP_PRODUCTION[profiles.current().key] + HELP_COMMON


class Bot:
    def __init__(self, db: Database):
        self.db = db
        self.pipe = Pipeline(db)
        self.tz = ZoneInfo(CONFIG.timezone)
        self.busy = asyncio.Lock()
        self.app = Application.builder().token(CONFIG.telegram_token).post_init(self._post_init).build()
        self.loop: asyncio.AbstractEventLoop | None = None
        self._register()

    # ------------------------------------------------------------------ setup
    def _register(self) -> None:
        admin = filters.User(user_id=list(CONFIG.admin_ids)) if CONFIG.admin_ids else filters.User(user_id=[])
        cmds: dict[str, Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]] = {
            "start": self.cmd_help, "yardim": self.cmd_help, "help": self.cmd_help,
            "durum": self.cmd_status, "uret": self.cmd_generate, "derleme": self.cmd_compilation,
            "bekleyenler": self.cmd_pending, "onayla": self.cmd_approve, "reddet": self.cmd_reject,
            "baslik": self.cmd_title, "istatistik": self.cmd_stats, "log": self.cmd_log, "test": self.cmd_test,
            "ayar": self.cmd_settings, "stiller": self.cmd_styles, "stil": self.cmd_style_toggle,
            "duraklat": self.cmd_pause, "devam": self.cmd_resume, "kutuphane": self.cmd_library,
            "demo": self.cmd_generate, "mix": self.cmd_demo, "parcalar": self.cmd_tracks, "temalar": self.cmd_themes,
            "kullanilan": self.cmd_used, "dinle": self.cmd_listen, "seriler": self.cmd_series,
            "video": self.cmd_video_link, "arkaplan": self.cmd_backgrounds,
        }
        for name, fn in cmds.items():
            self.app.add_handler(CommandHandler(name, fn, filters=admin))
        media_filter = (filters.VIDEO | filters.PHOTO | filters.ANIMATION | filters.Document.VIDEO
                        | filters.Document.IMAGE)
        self.app.add_handler(MessageHandler(admin & media_filter, self.on_media))
        self.app.add_handler(CallbackQueryHandler(self.on_button))
        # Yetkisiz kullanıcıya kendi ID'sini söyle (ilk kurulum için).
        self.app.add_handler(CommandHandler("start", self.cmd_whoami, filters=~admin))
        self.app.add_error_handler(self.on_error)

    async def on_error(self, update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        log.error("Telegram işleyici hatası", exc_info=ctx.error)

    async def _post_init(self, app: Application) -> None:
        self.loop = asyncio.get_running_loop()
        self._recover()
        self.schedule_jobs()
        await self.notify(f"🤖 Bot başladı ({profiles.current().key} · {html.escape(profiles.channel_name())}). " + ("(DRY_RUN: YouTube'a yükleme yapılmayacak)" if CONFIG.dry_run else "")
                          + "\n/yardim ile komutları görebilirsiniz.")

    def _recover(self) -> None:
        """Yeniden başlatmada yarım kalan işleri düzelt."""
        for r in self.db.query("SELECT id, status FROM videos WHERE status IN ('building', 'uploading')"):
            self.db.update_video(r["id"], status="failed" if r["status"] == "building" else "pending",
                                 error="Servis yeniden başladı, iş yarıda kaldı")

    def schedule_jobs(self) -> None:
        jq = self.app.job_queue
        for job in jq.jobs():
            job.schedule_removal()
        gh, gm = (int(x) for x in self.db.get_setting("generate_time").split(":"))
        gen = time(gh, gm, tzinfo=self.tz)
        comp = (datetime.combine(datetime.now(self.tz).date(), gen) + timedelta(minutes=30)).timetz()
        if profiles.current().main_kind == "mix":
            jq.run_daily(self.job_mix, gen, name="mix")
            jq.run_daily(self.job_prune, time(4, 0, tzinfo=self.tz), name="prune")
        else:
            jq.run_daily(self.job_daily, gen, name="daily")
            jq.run_daily(self.job_compilation, comp, name="compilation")
        jq.run_repeating(self.job_stats, interval=6 * 3600, first=120, name="stats")
        jq.run_repeating(self.job_reminders, interval=1800, first=300, name="reminders")
        jq.run_daily(self.job_weekly, time(10, 0, tzinfo=self.tz), days=(1,), name="weekly")

    # ------------------------------------------------------------------ helpers
    async def notify(self, text: str, **kw) -> None:
        for uid in CONFIG.admin_ids:
            try:
                await self.app.bot.send_message(uid, text, parse_mode=ParseMode.HTML, **kw)
            except Exception as e:  # noqa: BLE001
                log.warning("Telegram mesajı gönderilemedi (%s): %s", uid, e)

    def notify_threadsafe(self, text: str) -> None:
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.notify(html.escape(text)), self.loop)

    async def run_heavy(self, label: str, fn: Callable, *args):
        """Ağır işi ayrı thread'de, tek seferde bir tane olacak şekilde çalıştır."""
        if self.busy.locked():
            await self.notify(f"⏳ Başka bir iş sürüyor; <i>{html.escape(label)}</i> sıraya alındı.")
        async with self.busy:
            return await asyncio.to_thread(fn, *args, self.notify_threadsafe)

    def local(self, value: str | None) -> str:
        dt = parse_iso(value)
        return dt.astimezone(self.tz).strftime("%d.%m %H:%M") if dt else "-"

    def paused(self) -> bool:
        return self.db.get_setting("paused") == "1"

    # ------------------------------------------------------------------ approval card
    def _keyboard(self, vid: int, kind: str) -> InlineKeyboardMarkup:
        when = self.pipe.next_publish_at()
        rows = [[InlineKeyboardButton("✅ Onayla" + (f" ({when.astimezone(self.tz):%H:%M})" if when else ""),
                                      callback_data=f"ap:{vid}"),
                 InlineKeyboardButton("⚡ Hemen yayınla", callback_data=f"an:{vid}"),
                 InlineKeyboardButton("❌ Reddet", callback_data=f"rj:{vid}")]]
        regen = [InlineKeyboardButton("🖼 Görsel", callback_data=f"ri:{vid}"),
                 InlineKeyboardButton("✏️ Metin", callback_data=f"rt:{vid}")]
        if kind not in LONG_KINDS:
            regen.insert(0, InlineKeyboardButton("🎵 Müzik", callback_data=f"rm:{vid}"))
        rows.append(regen)
        return InlineKeyboardMarkup(rows)

    async def send_card(self, vid: int) -> None:
        v = self.db.video(vid)
        style = STYLE_BY_KEY.get(v["style_key"] or "")
        dur = 0.0
        if v["track_id"]:
            dur = self.db.track(v["track_id"])["duration_sec"] or 0
        elif v["preview_path"]:
            dur = self._comp_duration(vid)
        pub = self.pipe.next_publish_at()
        when = pub.astimezone(self.tz).strftime("bugün %H:%M") if pub else "onaylanınca hemen"
        shorts = [c for c in self.db.children(vid) if c["status"] == "pending"]
        desc = (v["description"] or "")[:420]
        caption = (
            f"🆕 <b>#{vid} · {KIND_TR[v['kind']]}</b> · {html.escape(style.label if style else '')}\n"
            f"<b>{html.escape(v['title'] or '')}</b>\n"
            f"⏱ {fmt_ts(dur)} · 📅 Yayın: {when}" + (" · 📱 + Short" if shorts else "") +
            f"\n\n{html.escape(desc)}"
        )[:1020]
        for uid in CONFIG.admin_ids:
            if v["thumb_path"] and Path(v["thumb_path"]).exists():
                with open(v["thumb_path"], "rb") as f:
                    await self.app.bot.send_photo(uid, f, caption=caption, parse_mode=ParseMode.HTML)
            else:
                await self.app.bot.send_message(uid, caption, parse_mode=ParseMode.HTML)
            if v["preview_path"] and Path(v["preview_path"]).exists():
                with open(v["preview_path"], "rb") as f:
                    await self.app.bot.send_audio(uid, f, title=v["title"] or "preview", performer=profiles.channel_name(),
                                                  read_timeout=120, write_timeout=120)
            await self.app.bot.send_message(uid, f"#{vid} için karar:", reply_markup=self._keyboard(vid, v["kind"]))

    def _comp_duration(self, vid: int) -> float:
        rows = self.db.query("SELECT ct.start_sec, t.duration_sec FROM compilation_tracks ct JOIN tracks t "
                             "ON t.id = ct.track_id WHERE ct.video_id = ? ORDER BY ct.position DESC LIMIT 1", (vid,))
        return (rows[0]["start_sec"] + rows[0]["duration_sec"]) if rows else 0.0

    # ------------------------------------------------------------------ actions
    async def do_generate(self, style_key: str | None = None, theme_key: str | None = None,
                          auto: bool = False, visual: str | None = None, series_key: str | None = None) -> None:
        try:
            def work(key, progress):
                return self.pipe.create_daily(key, progress, theme_key=theme_key, auto=auto, visual=visual,
                                              series_key=series_key)
            vid = await self.run_heavy("günlük video", work, style_key)
            await self.send_card(vid)
        except Exception as e:  # noqa: BLE001
            log.exception("Günlük üretim hatası")
            await self.notify(f"⚠️ Günlük video üretilemedi:\n<code>{html.escape(str(e)[:800])}</code>")

    async def do_mix(self, style_key: str | None = None, minutes: int | None = None) -> None:
        try:
            def work(key, progress):
                return self.pipe.create_mix(key, progress, minutes)
            vid = await self.run_heavy("deneme mix" if minutes else "uzun mix", work, style_key)
            await self.send_card(vid)
        except Exception as e:  # noqa: BLE001
            log.exception("Mix üretim hatası")
            await self.notify(f"⚠️ Uzun mix üretilemedi:\n<code>{html.escape(str(e)[:800])}</code>\n"
                              "Üretilen parçalar kütüphanede kaldı; bir sonraki /uret onları kullanır.")

    async def do_compilation(self, series_key: str | None = None) -> None:
        try:
            def work(progress):
                return self.pipe.create_compilation(progress, series_key=series_key)
            vid = await self.run_heavy("derleme", work)
            await self.send_card(vid)
        except Exception as e:  # noqa: BLE001
            log.exception("Derleme hatası")
            await self.notify(f"⚠️ Derleme üretilemedi:\n<code>{html.escape(str(e)[:800])}</code>")

    async def do_approve(self, vid: int, now: bool = False) -> None:
        try:
            def work(video_id, progress):
                return self.pipe.approve(video_id, progress, publish_now=now)
            ids = await self.run_heavy("yükleme", work, vid)
            links = "\n".join(f"▶️ https://youtu.be/{i}\n✏️ Studio: https://studio.youtube.com/video/{i}/edit"
                              for i in ids)
            v = self.db.video(vid)
            await self.notify(f"✅ #{vid} yüklendi ({STATUS_TR.get(v['status'], v['status'])}, "
                              f"yayın {self.local(v['publish_at'])})\n{links}\n\n"
                              "ℹ️ Video gizli (private) kalırsa Studio bağlantısından "
                              "<b>Visibility → Public</b> yapın (API audit olmadan YouTube böyle kilitler).")
        except Exception as e:  # noqa: BLE001
            log.exception("Yükleme hatası")
            await self.notify(f"⚠️ #{vid} yüklenemedi, onay bekliyor olarak kaldı:\n"
                              f"<code>{html.escape(str(e)[:800])}</code>\nTekrar denemek için /onayla {vid}")

    async def do_regen(self, vid: int, part: str) -> None:
        def work(video_id: int, p: str, progress):
            self.pipe.regenerate(video_id, p, progress)
            return video_id
        try:
            await self.run_heavy("yenileme", work, vid, part)
            await self.send_card(vid)
        except Exception as e:  # noqa: BLE001
            log.exception("Yenileme hatası")
            await self.notify(f"⚠️ #{vid} yenilenemedi:\n<code>{html.escape(str(e)[:800])}</code>")

    async def on_button(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        q = update.callback_query
        if not q or q.from_user.id not in CONFIG.admin_ids:
            if q:
                await q.answer("Yetkiniz yok")
            return
        action, _, raw = (q.data or "").partition(":")
        vid = int(raw)
        await q.answer()
        if action in ("tv", "td"):  # kütüphane parçası: videoya çevir / sil
            await self.on_track_button(q, action, vid)
            return
        try:
            v = self.db.video(vid)
        except KeyError:
            await q.edit_message_text("Bu video artık yok.")
            return
        has_pending = v["status"] == "pending" or any(c["status"] == "pending" for c in self.db.children(vid))
        if not has_pending:
            await q.edit_message_text(f"#{vid}: {STATUS_TR.get(v['status'], v['status'])}")
            return
        labels = {"ap": "✅ Onaylandı, yükleniyor…", "an": "⚡ Onaylandı, hemen yayınlanmak üzere yükleniyor…",
                  "rj": "🗑 Reddedildi", "rm": "🎵 Müzik yenileniyor…",
                  "ri": "🖼 Görsel yenileniyor…", "rt": "✏️ Metin yenileniyor…"}
        await q.edit_message_text(f"#{vid}: {labels.get(action, action)}")
        if action in ("ap", "an"):
            asyncio.create_task(self.do_approve(vid, now=action == "an"))
        elif action == "rj":
            self.pipe.reject(vid)
        elif action in ("rm", "ri", "rt"):
            part = {"rm": "music", "ri": "image", "rt": "meta"}[action]
            asyncio.create_task(self.do_regen(vid, part))

    async def on_track_button(self, q, action: str, track_id: int) -> None:
        if track_id not in {t["id"] for t in self.pipe.unused_tracks()}:
            await q.edit_message_caption(f"Parça #{track_id} artık kullanılamaz (zaten videoya çevrilmiş ya da silinmiş).")
            return
        if action == "td":
            self.pipe.discard_track(track_id)
            await q.edit_message_caption(f"🗑 Parça #{track_id} silindi.")
            return
        await q.edit_message_caption(f"✅ Parça #{track_id} onaylandı; video hazırlanıyor, kart birazdan gelecek…")
        asyncio.create_task(self.do_track_video(track_id))

    async def do_track_video(self, track_id: int) -> None:
        try:
            vid = await self.run_heavy("parçadan video", self.pipe.create_daily_from_track, track_id)
            await self.send_card(vid)
        except Exception as e:  # noqa: BLE001
            log.exception("Parçadan video hatası")
            await self.notify(f"⚠️ Parça #{track_id} videoya çevrilemedi:\n<code>{html.escape(str(e)[:800])}</code>")

    async def cmd_used(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """/kullanilan: daha önce videoya dönüşmüş parçalar, en çok izlenenden aza."""
        if not CONFIG.dry_run:
            try:
                await asyncio.to_thread(self.pipe.refresh_stats)
            except Exception as e:  # noqa: BLE001
                log.warning("İstatistik güncellenemedi: %s", e)
        rows = self.pipe.used_tracks()
        if not rows:
            await update.message.reply_text("Henüz videoya dönüşmüş parça yok. /parcalar ile kullanılmamışlara bakın.")
            return
        from .themes import THEME_BY_KEY
        total_views = sum(r["views"] or 0 for r in rows)
        lines = []
        for n, r in enumerate(rows, 1):
            th = THEME_BY_KEY.get(r["theme"] or "")
            style = STYLE_BY_KEY.get(r["style_key"])
            state = {"pending": "⏳ onay bekliyor", "uploading": "⬆️ yükleniyor"}.get(r["status"])
            if not state and r["privacy"] == "private":
                state = "🔒 gizli"
            head = (f"<b>{n}.</b> 👁 {r['views'] or 0:,} · ❤️ {r['likes'] or 0}"
                    + (f" · {state}" if state else ""))
            body = (f"#{r['id']} <b>{html.escape(r['name'] or 'Parça')}</b> ({fmt_ts(r['duration_sec'] or 0)})"
                    f" · {th.emoji + ' ' + th.label if th else ''} · {html.escape(style.label if style else '')}")
            extra = []
            if r["publish_at"]:
                extra.append(f"📅 {self.local(r['publish_at'])}")
            if r["compilations"]:
                extra.append(f"🔁 {r['compilations']} derlemede")
            if r["youtube_id"] and not str(r["youtube_id"]).startswith("dryrun"):
                extra.append(f"https://youtu.be/{r['youtube_id']}")
            lines.append(f"{head}\n{body}\n" + " · ".join(extra))
        header = (f"<b>Kullanılmış parçalar</b> ({len(rows)} parça · toplam 👁 {total_views:,})\n"
                  "En çok izlenenden aza. Dinlemek: /dinle &lt;#numara&gt;\n\n")
        chunk = header
        for line in lines:  # Telegram mesaj sınırı 4096
            if len(chunk) + len(line) + 2 > 3900:
                await update.message.reply_html(chunk, disable_web_page_preview=True)
                chunk = ""
            chunk += line + "\n\n"
        if chunk.strip():
            await update.message.reply_html(chunk, disable_web_page_preview=True)

    async def cmd_listen(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        tid = self._arg_id(ctx)
        if tid is None:
            await update.message.reply_text("Kullanım: /dinle <parça #numarası>")
            return
        try:
            t = self.db.track(tid)
        except KeyError:
            await update.message.reply_text(f"Parça #{tid} yok.")
            return
        if not t["audio_path"] or not Path(t["audio_path"]).exists():
            await update.message.reply_text(f"Parça #{tid} ses dosyası artık sunucuda yok.")
            return
        with open(t["audio_path"], "rb") as fh:
            await update.message.reply_audio(fh, title=t["name"] or f"Track {tid}", performer=profiles.channel_name(),
                                              caption=f"#{tid} · {fmt_ts(t['duration_sec'] or 0)}",
                                              read_timeout=120, write_timeout=120)

    async def cmd_tracks(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """/parcalar: kullanılmamış parçaları tek tek dinlet; onaylananlar kredisiz videoya çevrilir."""
        tracks = self.pipe.unused_tracks()
        if not tracks:
            await update.message.reply_text("Kütüphanede kullanılmamış parça yok. "
                                            "Yayınlanmış parçalar için /kullanilan yazın.")
            return
        await update.message.reply_text(
            f"🎧 {len(tracks)} kullanılmamış parça var. Her birini dinleyin:\n"
            "✅ Video yap → şömineli video + Short hazırlanır, onay kartı gelir (kredi harcamaz)\n"
            "🗑 Sil → parça kalıcı olarak silinir")
        for t in tracks[:15]:
            style = STYLE_BY_KEY.get(t["style_key"])
            caption = (f"#{t['id']} · {t['name'] or 'Parça'} · {style.label if style else t['style_key']} · "
                       f"{fmt_ts(t['duration_sec'] or 0)}")
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Video yap", callback_data=f"tv:{t['id']}"),
                                        InlineKeyboardButton("🗑 Sil", callback_data=f"td:{t['id']}")]])
            with open(t["audio_path"], "rb") as fh:
                await update.message.reply_audio(fh, title=t["name"] or f"Track {t['id']}",
                                                  performer=profiles.channel_name(), caption=caption,
                                                  reply_markup=kb, read_timeout=120, write_timeout=120)
        if len(tracks) > 15:
            await update.message.reply_text(f"…ve {len(tracks) - 15} parça daha. Bunları bitirince tekrar /parcalar.")

    # ------------------------------------------------------------------ commands
    async def cmd_whoami(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            f"Bu bot özel. Sahibiyseniz Railway'de TELEGRAM_ADMIN_IDS değişkenine şu ID'yi ekleyin: "
            f"{update.effective_user.id}")

    async def cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_html(help_text())

    async def cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        jobs = sorted((j for j in self.app.job_queue.jobs() if j.next_t), key=lambda j: j.next_t)
        nxt = "\n".join(f"• {j.name}: {j.next_t.astimezone(self.tz).strftime('%d.%m %H:%M')}" for j in jobs)
        recent = self.db.query("SELECT * FROM videos WHERE kind != 'short' ORDER BY id DESC LIMIT 6")
        lines = "\n".join(f"#{r['id']} {KIND_TR[r['kind']]} · {STATUS_TR.get(r['status'], r['status'])} · "
                          f"{html.escape((r['title'] or '-')[:40])}" for r in recent)
        if profiles.current().main_kind == "mix":
            due = "Mix zamanı geldi mi: " + ("evet" if self.pipe.mix_due() else "hayır")
        else:
            due = "Derleme zamanı geldi mi: " + ("evet" if self.pipe.compilation_due() else "hayır")
        await update.message.reply_html(
            f"<b>Durum</b>: {'⏸ DURAKLATILDI' if self.paused() else '▶️ çalışıyor'}"
            f"{' · DRY_RUN' if CONFIG.dry_run else ''}\n"
            f"Meşgul: {'evet' if self.busy.locked() else 'hayır'} · {due}\n\n"
            f"<b>Sıradaki işler</b>\n{nxt}\n\n<b>Son videolar</b>\n{lines or '-'}")

    async def cmd_generate(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        key, theme, visual, ser = None, None, None, None
        modes = {"sahne": "scene", "scene": "scene", "kolaj": "collage", "collage": "collage",
                 "somine": "fireplace", "şömine": "fireplace"}
        for a in ctx.args:  # /uret [seri] [stil] [tema] [sahne|kolaj] — sıra fark etmez
            if a.lower() in modes:
                visual = modes[a.lower()]
            elif find_series(a):
                ser = find_series(a)
            elif a in {s.key for s in active_styles()}:
                key = a
            elif find_theme(a):
                theme = find_theme(a)
            else:
                await update.message.reply_text(f"'{a}' bir seri, stil ya da tema değil. "
                                                "/seriler, /stiller ve /temalar ile listeye bakın.")
                return
        if profiles.current().main_kind == "mix":
            await update.message.reply_text("💕 Uzun mix üretimi başladı. Parça sayısına göre 20–60 dk sürebilir; "
                                            "adımlar buraya gelecek.")
            asyncio.create_task(self.do_mix(key))
            return
        await update.message.reply_text(
            "🎬 Yeni parça üretimi başladı" + (f" ({theme.emoji} {theme.label})" if theme else "") +
            ", adımlar buraya gelecek. Bu ekstra video otomatik takvimi değiştirmez.")
        asyncio.create_task(self.do_generate(key, theme.key if theme else None, visual=visual,
                                             series_key=ser.key if ser else None))

    async def cmd_themes(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        lines = [f"{t.emoji} <code>{t.key}</code> – {t.label} ({EN_LABEL[t.key]})" for t in THEMES]
        await update.message.reply_html("<b>Temalar</b>\n" + "\n".join(lines) +
                                        "\n\nÖrnek: <code>/uret sonbahar</code> · <code>/uret deniz</code> · "
                                        "<code>/uret moonlight_piano kar</code>")

    async def cmd_compilation(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if profiles.current().main_kind == "mix":
            await update.message.reply_text("Bu kanalda her video zaten uzun bir mix. /uret kullanın.")
            return
        ser = find_series(ctx.args[0]) if ctx.args else None
        if ctx.args and not ser:
            await update.message.reply_text("Bilinmeyen seri. /seriler ile listeye bakın.")
            return
        await update.message.reply_text("🎚 Derleme üretimi başladı" + (f" ({ser.emoji} {ser.label})" if ser else
                                                                        " (sıradaki seri)") + ".")
        asyncio.create_task(self.do_compilation(ser.key if ser else None))

    async def cmd_series(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        nxt = self.pipe.next_series()
        counts = {r["s"]: r["n"] for r in self.db.query(
            "SELECT COALESCE(t.series, 'romance') s, COUNT(*) n FROM videos v JOIN tracks t ON t.id = v.track_id "
            "WHERE v.kind = 'daily' AND v.status IN ('scheduled', 'published') GROUP BY s")}
        lines = [f"{s.emoji} <code>{s.key}</code> – {s.label} ({html.escape(s.genre)}) · {counts.get(s.key, 0)} video"
                 + (" ← sıradaki" if s.key == nxt.key else "") for s in SERIES]
        await update.message.reply_html(
            "<b>Seriler</b> (otomatik üretim sırayla döner)\n" + "\n".join(lines) +
            "\n\nÖrnek: <code>/uret jazz</code> · <code>/uret uyku yagmur</code> · <code>/derleme sleep</code>")

    async def cmd_pending(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        rows = self.db.pending()
        if not rows:
            await update.message.reply_text("Onay bekleyen video yok.")
            return
        for r in rows:
            await self.send_card(r["id"])

    def _arg_id(self, ctx: ContextTypes.DEFAULT_TYPE) -> int | None:
        try:
            return int(ctx.args[0].lstrip("#"))
        except (IndexError, ValueError):
            return None

    async def cmd_approve(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        vid = self._arg_id(ctx)
        if vid is None:
            await update.message.reply_text("Kullanım: /onayla <id>")
            return
        await update.message.reply_text(f"#{vid} yükleniyor…")
        asyncio.create_task(self.do_approve(vid))

    async def cmd_reject(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        vid = self._arg_id(ctx)
        if vid is None:
            await update.message.reply_text("Kullanım: /reddet <id>")
            return
        self.pipe.reject(vid)
        await update.message.reply_text(f"#{vid} reddedildi.")

    async def cmd_title(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        vid = self._arg_id(ctx)
        title = " ".join(ctx.args[1:]).strip()
        if vid is None or not title:
            await update.message.reply_text("Kullanım: /baslik <id> <yeni başlık>")
            return
        self.db.update_video(vid, title=title[:100])
        for c in self.db.children(vid):
            if c["status"] == "pending":
                self.db.update_video(c["id"], title=metadata.short_title(title))
        await update.message.reply_text(f"#{vid} başlığı güncellendi: {title[:100]}")

    async def cmd_stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        text = ""
        if not CONFIG.dry_run:
            try:
                await asyncio.to_thread(self.pipe.refresh_stats)
                from .youtube import YouTube
                ch = await asyncio.to_thread(lambda: YouTube().channel())
                text += (f"<b>{html.escape(ch['title'])}</b>\n👥 {ch.get('subscriberCount', 0):,} abone · "
                         f"👁 {ch.get('viewCount', 0):,} izlenme · 🎬 {ch.get('videoCount', 0)} video\n\n")
            except Exception as e:  # noqa: BLE001
                text += f"⚠️ YouTube verisi alınamadı: {html.escape(str(e)[:300])}\n\n"
        top = self.db.query("SELECT * FROM videos WHERE youtube_id IS NOT NULL ORDER BY views DESC LIMIT 5")
        text += "<b>En çok izlenenler</b>\n" + ("\n".join(
            f"👁 {r['views']:,} · ❤️ {r['likes']} · {html.escape((r['title'] or '')[:45])}" for r in top) or "-")
        perf = self.pipe.style_performance()
        if perf:
            text += "\n\n<b>Stil ortalamaları</b>\n" + "\n".join(
                f"{STYLE_BY_KEY[k].label}: {v:,.0f}" for k, v in sorted(perf.items(), key=lambda x: -x[1]))
        await update.message.reply_html(text)

    async def cmd_log(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            lines = CONFIG.log_path.read_text(errors="replace").splitlines()[-25:]
        except FileNotFoundError:
            lines = ["(log yok)"]
        await update.message.reply_html("<pre>" + html.escape("\n".join(lines))[-3800:] + "</pre>")

    async def cmd_test(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        fire = profiles.current().key == "romantic" and self.pipe.fireplace_on()
        lines = [("✅" if CONFIG.anthropic_api_key else "❌") + " Claude (metin)"
                 + ("" if CONFIG.anthropic_api_key else " – yoksa şablon başlıklar kullanılır")]
        if CONFIG.elevenlabs_api_key:
            try:
                left, limit = await asyncio.to_thread(elevenlabs_credits)
                warn = " ⚠️ az kaldı" if left < 60_000 else ""
                lines.append(f"✅ ElevenLabs (müzik): {left:,} / {limit:,} kredi kaldı{warn}")
            except Exception as e:  # noqa: BLE001
                lines.append(f"⚠️ ElevenLabs: anahtar var ama kredi okunamadı ({html.escape(str(e)[:150])})")
        else:
            lines.append("❌ ElevenLabs (müzik) – zorunlu")
        if self.db.get_setting("daily_visual") in ("collage", "scene", "both"):
            lines.append(("✅ Pexels (temalı klip kolajı)" if CONFIG.pexels_api_key else
                          "❌ Pexels – PEXELS_API_KEY yok; kısa videolarda şömineye geçilir"))
        if fire:
            lines.append("➖ Stability (görsel) – şömine modunda gerekmiyor")
        else:
            lines.append(("✅" if CONFIG.stability_api_key else "❌") + " Stability (görsel)"
                         + ("" if CONFIG.stability_api_key else " – yoksa prosedürel görsel"))
        if CONFIG.youtube_client_id and CONFIG.youtube_client_secret and CONFIG.youtube_refresh_token:
            try:  # DRY_RUN açıkken de bağlantıyı doğrula (yükleme yapmadan)
                from .youtube import YouTube
                ch = await asyncio.to_thread(lambda: YouTube().channel())
                lines.append(f"✅ YouTube: {html.escape(ch['title'])}")
            except Exception as e:  # noqa: BLE001
                lines.append(f"❌ YouTube: {html.escape(str(e)[:300])}")
        else:
            lines.append("❌ YouTube – YOUTUBE_CLIENT_ID / _SECRET / _REFRESH_TOKEN eksik")
        if CONFIG.dry_run:
            lines.append("ℹ️ DRY_RUN açık: videolar YouTube'a yüklenmez")
        await update.message.reply_html("\n".join(lines))

    async def cmd_settings(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if len(ctx.args) >= 2:
            key, value = ctx.args[0], " ".join(ctx.args[1:])
            if key not in default_settings():
                await update.message.reply_text("Bilinmeyen ayar. /ayar ile listeyi görün.")
                return
            err = validate_setting(key, value)
            if err:
                await update.message.reply_text(f"Geçersiz değer: {err}")
                return
            self.db.set_setting(key, value)
            if key == "generate_time":
                self.schedule_jobs()
            await update.message.reply_text(f"✅ {key} = {value}")
            return
        lines = [f"<code>{k}</code> = <b>{html.escape(self.db.get_setting(k))}</b>\n   {SETTING_HELP[k]}"
                 for k in default_settings()]
        await update.message.reply_html("<b>Ayarlar</b> (değiştirmek: /ayar anahtar değer)\n\n" + "\n".join(lines))

    async def cmd_styles(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        perf = self.pipe.style_performance()
        disabled = self.pipe.disabled_styles()
        counts = {r["style_key"]: r["n"] for r in self.db.query(
            "SELECT style_key, COUNT(*) n FROM videos WHERE kind IN ('daily', 'mix') AND youtube_id IS NOT NULL "
            "GROUP BY style_key")}
        lines = [f"{'🚫' if s.key in disabled else '🎵'} <code>{s.key}</code> – {s.label} · "
                 f"{counts.get(s.key, 0)} video · ort. 👁 {perf.get(s.key, 0):,.0f}" for s in active_styles()]
        await update.message.reply_html("<b>Stiller</b>\n" + "\n".join(lines) +
                                        "\n\nTek seferlik: /uret &lt;anahtar&gt; · Kapat/aç: /stil &lt;anahtar&gt; kapat|ac")

    async def cmd_style_toggle(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        keys = {s.key for s in active_styles()}
        if len(ctx.args) != 2 or ctx.args[0] not in keys or ctx.args[1] not in ("ac", "kapat"):
            await update.message.reply_text("Kullanım: /stil <anahtar> ac|kapat")
            return
        disabled = self.pipe.disabled_styles()
        (disabled.add if ctx.args[1] == "kapat" else disabled.discard)(ctx.args[0])
        if len(disabled & keys) >= len(keys):
            await update.message.reply_text("En az bir stil açık kalmalı.")
            return
        self.db.set_setting("disabled_styles", ",".join(sorted(disabled)))
        await update.message.reply_text(f"✅ {ctx.args[0]} {'kapatıldı' if ctx.args[1] == 'kapat' else 'açıldı'}")

    async def cmd_demo(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """/mix: tamamı yeni parçalardan uzun mix (romantic). Dakika başına ~600-900 ElevenLabs kredisi."""
        if profiles.current().key != "romantic":
            await update.message.reply_text("/mix yalnızca romantic profilinde var; burada /uret kullanın.")
            return
        minutes, key = 10, None
        for a in ctx.args:
            if a.isdigit():
                minutes = max(3, min(30, int(a)))
            elif a in {s.key for s in active_styles()}:
                key = a
        await update.message.reply_text(
            f"🎧 {minutes} dk'lık mix üretiliyor (~{minutes * 750:,} ElevenLabs kredisi). Hazır olunca ses "
            "önizlemesi gelecek. Yayınlamak istemezseniz kartta ❌ Reddet deyin.")
        asyncio.create_task(self.do_mix(key, minutes))

    async def on_media(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.message
        if msg.photo:
            f, name = msg.photo[-1], "photo.jpg"
        else:
            f = msg.video or msg.animation or msg.document
            name = getattr(f, "file_name", None) or ("fireplace.mp4" if (msg.video or msg.animation) else "upload")
        if (f.file_size or 0) > 20 * 1024 * 1024:
            await msg.reply_text("⚠️ Telegram botları 20 MB'tan büyük dosyayı indiremez. Büyük (4K) videoları "
                                 "Google Drive'a yükleyip linkini gönderin: /video <link>")
            return
        await msg.reply_text("🔥 Alındı. Dikişsiz döngü hazırlanıyor (fotoğrafta ~5 dk, videoda ~1 dk)…")
        suffix = Path(name).suffix or ".bin"
        tmp = fireplace.cache_dir() / f"upload_{f.file_unique_id}{suffix}"
        try:
            await (await f.get_file()).download_to_drive(tmp)
            bg = await self.run_heavy("şömine arka planı", lambda progress: fireplace.save_upload(tmp, name))
            await self._reply_background(msg, bg)
        except Exception as e:  # noqa: BLE001
            log.exception("Arka plan yüklenemedi")
            tmp.unlink(missing_ok=True)
            await msg.reply_text(f"⚠️ Arka plan eklenemedi: {str(e)[:500]}")

    async def _reply_background(self, msg, bg) -> None:
        loop = fireplace.loop_for(bg, (1920, 1080))
        note = ("Bu video(lar) varken fotoğraflar kullanılmaz; ateş sesi videonun kendi sesinden alınır "
                "(sessizse sentez çıtırtı)." if bg.kind == "video" else
                "Fotoğraf hafif ışık titremesiyle döngüye çevrildi.")
        with open(loop, "rb") as fh:
            await msg.reply_video(fh, caption=f"✅ Arka plan eklendi: {bg.name}\n{note}\n"
                                              f"Toplam: {len(fireplace.backgrounds())} · /arkaplan",
                                  read_timeout=120, write_timeout=120)

    async def cmd_video_link(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """/video <link> [link2 ...]: Drive/Dropbox/doğrudan linklerle büyük (4K, 300 MB+) videolar ekle."""
        msg = update.message
        links = [a for a in (msg.text or "").split() if a.startswith("http")]  # satır satır da yapıştırılabilir
        if not links:
            await msg.reply_text("Kullanım: /video <link> [link2 link3 …]\n"
                                 "Google Drive ya da Dropbox paylaşım linkleri; her biri ayrı satırda da olabilir.\n"
                                 "Drive'da dosyaları 'Bağlantıya sahip olan herkes' ile paylaşın.")
            return
        await msg.reply_text(f"⬇️ {len(links)} video sırayla indirilip 1080p'ye küçültülecek "
                             "(büyük dosyalarda her biri birkaç dakika)…")
        ok = 0
        for n, link in enumerate(links, 1):
            try:
                bg = await self.run_heavy(f"linkten arka plan {n}/{len(links)}",
                                          lambda progress, u=link: fireplace.import_url(u))
                await self._reply_background(msg, bg)
                ok += 1
            except Exception as e:  # noqa: BLE001
                log.exception("Linkten arka plan eklenemedi")
                await msg.reply_text(f"⚠️ {n}. video eklenemedi:\n{link[:80]}\n{str(e)[:400]}")
        if len(links) > 1:
            await msg.reply_text(f"✅ {ok}/{len(links)} video eklendi. Toplam arka plan: "
                                 f"{len(fireplace.backgrounds())} · /arkaplan")

    async def cmd_backgrounds(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if len(ctx.args) == 2 and ctx.args[0] == "sil":
            ok = fireplace.remove(ctx.args[1])
            await update.message.reply_text("🗑 Silindi." if ok else "Bulunamadı (repodaki varsayılan fotoğraf silinemez).")
            return
        bgs = fireplace.backgrounds()
        lines = [f"{'🎬' if b.kind == 'video' else '🖼'} <code>{html.escape(b.name)}</code>"
                 + (" (varsayılan)" if b.path.parent == fireplace.BUNDLED_DIR else "") for b in bgs]
        state = "açık" if self.db.get_setting("fireplace") == "1" else "kapalı"
        await update.message.reply_html(
            f"<b>Şömine arka planları</b> (mod: {state}, çıtırtı: %{self.db.get_setting('fire_volume') or 0})\n"
            + ("\n".join(lines) or "Yok") +
            "\n\nYeni eklemek için bota video ya da fotoğraf gönderin. Silmek: /arkaplan sil &lt;ad&gt;")

    async def cmd_library(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        lines = []
        for s in active_styles():
            unused, reusable = self.pipe.library_tracks(s.key)
            if unused or reusable:
                mins = sum(t["duration"] for t in unused + reusable) / 60
                lines.append(f"🎹 {s.label}: {len(unused)} yeni · {len(reusable)} tekrar kullanılabilir "
                             f"(~{mins:.0f} dk)")
        await update.message.reply_html(
            "<b>Parça kütüphanesi</b>\n" + ("\n".join(lines) or "Henüz parça yok.") +
            f"\n\nMix'in en fazla %{self.db.get_setting('mix_reuse_pct')}'i yayınlanmış parçalardan oluşur; "
            "hiç yayınlanmamış parçalar (reddedilen / yarıda kalan mixlerden) önce kullanılır.")

    async def cmd_pause(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        self.db.set_setting("paused", "1")
        await update.message.reply_text("⏸ Otomasyon duraklatıldı. Elle /uret hâlâ çalışır. Sürdürmek: /devam")

    async def cmd_resume(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        self.db.set_setting("paused", "0")
        await update.message.reply_text("▶️ Otomasyon sürüyor.")

    # ------------------------------------------------------------------ jobs
    async def job_daily(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if self.paused():
            return
        today = datetime.now(self.tz).date()
        for r in self.db.query("SELECT created_at FROM videos WHERE kind = 'daily' "
                               "AND status NOT IN ('rejected', 'failed') ORDER BY id DESC LIMIT 3"):
            if parse_iso(r["created_at"]).astimezone(self.tz).date() == today:
                return  # bugün zaten elle üretilmiş
        if not self.pipe.daily_due():
            return  # daily_every_days dolmadı (romantic: 3 günde bir)
        await self.do_generate(auto=True)

    async def job_mix(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if self.paused() or not self.pipe.mix_due():
            return
        if self.db.one("SELECT id FROM videos WHERE kind = 'mix' AND status IN ('pending', 'building')"):
            return  # önceki mix hâlâ onay bekliyor
        await self.do_mix()

    async def job_prune(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            n = await asyncio.to_thread(self.pipe.prune_library)
            if n:
                log.info("Kütüphaneden %s eski parça sesi silindi", n)
        except Exception as e:  # noqa: BLE001
            log.warning("Kütüphane temizliği başarısız: %s", e)

    async def job_compilation(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if self.paused() or not self.pipe.compilation_due():
            return
        if self.db.one("SELECT id FROM videos WHERE kind = 'compilation' AND status IN ('pending', 'building')"):
            return
        await self.do_compilation()

    async def job_stats(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            await asyncio.to_thread(self.pipe.refresh_stats)
        except Exception as e:  # noqa: BLE001
            log.warning("İstatistik güncellenemedi: %s", e)
            return
        locked = self.pipe.locked_private()
        if locked and self.db.get_setting("warned_locked") != "1":
            self.db.set_setting("warned_locked", "1")
            await self.notify(
                "⚠️ Yayın zamanı geçtiği halde <b>gizli (private)</b> kalan videolar var. Bu genellikle Google Cloud "
                "projesinin YouTube API denetiminden (audit) geçmediği anlamına gelir. README'deki "
                "'API Audit' adımına bakın. Videoları geçici olarak YouTube Studio'dan elle herkese açık yapabilirsiniz.")

    async def job_reminders(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        now = utcnow()
        remind_h = self.db.get_int("reminder_hours")
        auto_h = self.db.get_int("auto_approve_hours")
        for r in self.db.pending():
            age = now - parse_iso(r["created_at"])
            if auto_h > 0 and age >= timedelta(hours=auto_h) and not self.busy.locked():
                await self.notify(f"⏱ #{r['id']} {auto_h} saattir cevapsız; ayar gereği otomatik onaylanıyor.")
                await self.do_approve(r["id"])
                continue
            last = parse_iso(r["last_reminder_at"]) or parse_iso(r["created_at"])
            if remind_h > 0 and now - last >= timedelta(hours=remind_h):
                self.db.update_video(r["id"], last_reminder_at=now.isoformat(timespec="seconds"))
                await self.app.bot.send_message(
                    next(iter(CONFIG.admin_ids)),
                    f"🔔 #{r['id']} hâlâ onay bekliyor: {r['title']}",
                    reply_markup=self._keyboard(r["id"], r["kind"]))

    async def job_weekly(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        week_ago = (utcnow() - timedelta(days=7)).isoformat(timespec="seconds")
        rows = self.db.query("SELECT * FROM videos WHERE youtube_id IS NOT NULL AND publish_at >= ? "
                             "ORDER BY views DESC", (week_ago,))
        if not rows:
            await self.notify("📊 Haftalık rapor: bu hafta yayınlanan video yok.")
            return
        total = sum(r["views"] for r in rows)
        best = rows[0]
        await self.notify(
            f"📊 <b>Haftalık rapor</b>\n{len(rows)} video · toplam 👁 {total:,}\n"
            f"🏆 En iyi: {html.escape(best['title'] or '')} ({best['views']:,} izlenme, "
            f"{STYLE_BY_KEY[best['style_key']].label if best['style_key'] in STYLE_BY_KEY else '-'})\n"
            "Stil seçimi bu verilere göre otomatik ağırlıklandırılıyor.")

    def run(self) -> None:
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def validate_setting(key: str, value: str) -> str | None:
    if key == "compilation_fill":
        return None if value in ("repeat", "generate") else "repeat ya da generate olmalı"
    if key == "daily_visual":
        ok = ("both", "scene", "collage", "fireplace", "image")
        return None if value in ok else "both, scene, collage, fireplace ya da image olmalı"
    if key.endswith("_time"):
        try:
            hh, mm = (int(x) for x in value.split(":"))
            assert 0 <= hh < 24 and 0 <= mm < 60
        except (ValueError, AssertionError):
            return "SS:DD biçiminde olmalı (ör. 09:00)"
        return None
    if not value.isdigit():
        return "pozitif tam sayı olmalı"
    n = int(value)
    if key in ("make_shorts", "paused") and n not in (0, 1):
        return "0 veya 1 olmalı"
    if key in ("daily_min_sec", "daily_max_sec") and not 60 <= n <= 600:
        return "60–600 sn arası olmalı"
    if key == "short_seconds" and not 15 <= n <= 59:
        return "15–59 sn arası olmalı"
    if key in ("compilation_min_min", "compilation_max_min") and not 10 <= n <= 180:
        return "10–180 dk arası olmalı"
    if key in ("mix_min_min", "mix_max_min") and not 30 <= n <= 360:
        return "30–360 dk arası olmalı"
    if key == "mix_every_days" and not 1 <= n <= 30:
        return "1–30 gün arası olmalı"
    if key == "daily_every_days" and not 1 <= n <= 14:
        return "1–14 gün arası olmalı"
    if key == "mix_reuse_pct" and not 0 <= n <= 80:
        return "0–80 arası olmalı"
    if key in ("fireplace", "publish_roll", "bg_rotate") and n not in (0, 1):
        return "0 veya 1 olmalı"
    if key in ("bg_rotate_min_min", "bg_rotate_max_min") and not 5 <= n <= 120:
        return "5–120 dk arası olmalı"
    if key == "fire_volume" and not 0 <= n <= 100:
        return "0–100 arası olmalı"
    if key == "soft_master" and n not in (0, 1):
        return "0 veya 1 olmalı"
    if key == "mix_crossfade_sec" and not 4 <= n <= 20:
        return "4–20 sn arası olmalı"
    if key == "compilation_every_days" and not 1 <= n <= 90:
        return "1–90 gün arası olmalı"
    return None


def elevenlabs_credits() -> tuple[int, int]:
    """ElevenLabs hesabında (kalan, aylık limit) kredi."""
    import requests
    r = requests.get("https://api.elevenlabs.io/v1/user/subscription",
                     headers={"xi-api-key": CONFIG.elevenlabs_api_key}, timeout=15)
    r.raise_for_status()
    d = r.json()
    used, limit = int(d.get("character_count", 0)), int(d.get("character_limit", 0))
    return max(0, limit - used), limit
