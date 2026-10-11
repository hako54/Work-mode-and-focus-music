"""YouTube refresh token almak için BİR KEZ kendi bilgisayarınızda çalıştırın.

    pip install google-auth-oauthlib
    python scripts/youtube_auth.py <CLIENT_ID> <CLIENT_SECRET>

Tarayıcı açılır; kanalın sahibi olan Google hesabıyla (ve kanal Brand Account
ise o kanalı seçerek) giriş yapın. Ekrana yazılan refresh token'ı Railway'de
YOUTUBE_REFRESH_TOKEN değişkenine kaydedin.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube"]


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    client_id, client_secret = sys.argv[1], sys.argv[2]
    flow = InstalledAppFlow.from_client_config(
        {"installed": {"client_id": client_id, "client_secret": client_secret,
                       "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                       "token_uri": "https://oauth2.googleapis.com/token",
                       "redirect_uris": ["http://localhost"]}},
        SCOPES,
    )
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    print("\nYOUTUBE_REFRESH_TOKEN=" + creds.refresh_token)


if __name__ == "__main__":
    main()
