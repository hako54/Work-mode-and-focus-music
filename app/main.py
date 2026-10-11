"""Giriş noktası: `python -m app.main`"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import CONFIG


def setup_logging() -> None:
    CONFIG.data_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout),
              RotatingFileHandler(CONFIG.log_path, maxBytes=2_000_000, backupCount=3)):
        h.setFormatter(fmt)
        root.addHandler(h)
    for noisy in ("httpx", "googleapiclient.discovery_cache", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> None:
    setup_logging()
    log = logging.getLogger("main")
    if not CONFIG.telegram_token:
        log.error("TELEGRAM_BOT_TOKEN tanımlı değil")
        sys.exit(1)
    if not CONFIG.admin_ids:
        log.warning("TELEGRAM_ADMIN_IDS boş: bota /start yazın, ID'nizi öğrenip bu değişkene ekleyin")

    from .bot import Bot
    from .db import Database

    Bot(Database(CONFIG.db_path)).run()


if __name__ == "__main__":
    main()
