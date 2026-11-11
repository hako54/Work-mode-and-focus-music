"""YouTube Data API v3: yükleme, küçük resim, playlist, istatistik."""
from __future__ import annotations

import logging
import time
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from .config import CONFIG
from .db import iso

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube"]
MUSIC_CATEGORY = "10"
REDIRECTS = {"localhost": "http://localhost", "playground": "https://developers.google.com/oauthplayground"}


def token_file() -> Path:
    return CONFIG.data_dir / "youtube_refresh_token.txt"


def refresh_token() -> str:
    """Telegram'dan (/youtube) yenilenen token varsa o, yoksa Railway'deki YOUTUBE_REFRESH_TOKEN."""
    f = token_file()
    if f.exists() and f.read_text().strip():
        return f.read_text().strip()
    return CONFIG.youtube_refresh_token


def is_expired_error(e: Exception) -> bool:
    return "invalid_grant" in str(e)


def auth_url(redirect: str = "localhost") -> str:
    return "https://accounts.google.com/o/oauth2/auth?" + urlencode({
        "client_id": CONFIG.youtube_client_id, "redirect_uri": REDIRECTS[redirect], "response_type": "code",
        "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent"})


def exchange_code(text: str, redirect: str = "localhost") -> str:
    """Yönlendirilen adres (…?code=…) ya da yalnızca kod -> yeni refresh token (kaydedilir)."""
    text = text.strip()
    code = parse_qs(urlparse(text).query).get("code", [text])[0] if "code=" in text else text
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "code": code, "client_id": CONFIG.youtube_client_id, "client_secret": CONFIG.youtube_client_secret,
        "redirect_uri": REDIRECTS[redirect], "grant_type": "authorization_code"})
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200 or not data.get("refresh_token"):
        raise YouTubeError(f"Google kodu kabul etmedi: {data.get('error_description') or data.get('error') or r.text[:200]}")
    token_file().write_text(data["refresh_token"])
    return data["refresh_token"]


class YouTubeError(RuntimeError):
    pass


class YouTube:
    def __init__(self) -> None:
        if not (CONFIG.youtube_client_id and CONFIG.youtube_client_secret and refresh_token()):
            raise YouTubeError("YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN eksik")
        creds = Credentials(
            None,
            refresh_token=refresh_token(),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CONFIG.youtube_client_id,
            client_secret=CONFIG.youtube_client_secret,
            scopes=SCOPES,
        )
        self.api = build("youtube", "v3", credentials=creds, cache_discovery=False)

    def upload(self, video: Path, title: str, description: str, tags: list[str],
               publish_at: datetime | None) -> str:
        """publish_at verilirse 'private + publishAt' ile zamanlanır, yoksa hemen yayınlanır."""
        status: dict = {
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # YouTube'un yapay zeka içerik beyanı
            "embeddable": True,
        }
        if publish_at:
            status.update(privacyStatus="private", publishAt=iso(publish_at).replace("+00:00", "Z"))
        else:
            status["privacyStatus"] = "public"
        body = {
            "snippet": {"title": title, "description": description, "tags": tags,
                        "categoryId": MUSIC_CATEGORY, "defaultLanguage": CONFIG.content_language},
            "status": status,
        }
        media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=16 * 1024 * 1024, resumable=True)
        req = self.api.videos().insert(part="snippet,status", body=body, media_body=media)
        response, retries = None, 0
        while response is None:
            try:
                _, response = req.next_chunk()
            except HttpError as e:
                if e.resp.status in (500, 502, 503, 504) and retries < 5:
                    retries += 1
                    time.sleep(2 ** retries)
                    continue
                raise YouTubeError(_explain(e)) from e
        return response["id"]

    def set_thumbnail(self, video_id: str, image: Path) -> None:
        try:
            self.api.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(image))).execute()
        except HttpError as e:
            # Kanal telefonla doğrulanmamışsa 403 döner; yüklemeyi bozmasın.
            log.warning("Küçük resim ayarlanamadı: %s", _explain(e))

    def ensure_playlist(self, title: str, description: str = "") -> str:
        page = None
        while True:
            res = self.api.playlists().list(part="snippet", mine=True, maxResults=50, pageToken=page).execute()
            for item in res.get("items", []):
                if item["snippet"]["title"] == title:
                    return item["id"]
            page = res.get("nextPageToken")
            if not page:
                break
        res = self.api.playlists().insert(
            part="snippet,status",
            body={"snippet": {"title": title, "description": description}, "status": {"privacyStatus": "public"}},
        ).execute()
        return res["id"]

    def add_to_playlist(self, playlist_id: str, video_id: str) -> None:
        try:
            self.api.playlistItems().insert(
                part="snippet",
                body={"snippet": {"playlistId": playlist_id,
                                  "resourceId": {"kind": "youtube#video", "videoId": video_id}}},
            ).execute()
        except HttpError as e:
            log.warning("Playlist'e eklenemedi: %s", _explain(e))

    def stats(self, video_ids: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for i in range(0, len(video_ids), 50):
            res = self.api.videos().list(part="statistics,status", id=",".join(video_ids[i:i + 50])).execute()
            for item in res.get("items", []):
                s = item.get("statistics", {})
                out[item["id"]] = {
                    "views": int(s.get("viewCount", 0)),
                    "likes": int(s.get("likeCount", 0)),
                    "privacy": item.get("status", {}).get("privacyStatus"),
                    "upload_status": item.get("status", {}).get("uploadStatus"),
                    "rejection": item.get("status", {}).get("rejectionReason"),
                }
        return out

    def channel(self) -> dict:
        res = self.api.channels().list(part="snippet,statistics", mine=True).execute()
        items = res.get("items", [])
        if not items:
            raise YouTubeError("Bu hesaba bağlı kanal bulunamadı")
        it = items[0]
        return {"title": it["snippet"]["title"], **{k: int(v) for k, v in it["statistics"].items()
                                                     if k in ("subscriberCount", "viewCount", "videoCount")}}


def _explain(e: HttpError) -> str:
    text = str(e)
    if "quotaExceeded" in text:
        return "YouTube API günlük kotası doldu (yarın sıfırlanır)."
    if "uploadLimitExceeded" in text:
        return "Kanalın günlük yükleme limiti aşıldı."
    if "forbidden" in text.lower() or e.resp.status == 403:
        return f"Yetki hatası (403). Kanal doğrulaması / OAuth izinleri kontrol edilmeli. {text[:300]}"
    return text[:500]
