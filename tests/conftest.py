import os
import tempfile

# Modüller CONFIG'i import anında okur; testler geçici bir veri klasörü kullanır.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="focusmusic-test-")
os.environ["DRY_RUN"] = "1"
for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "STABILITY_API_KEY"):
    os.environ.pop(k, None)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _fast_fireplace(monkeypatch):
    """Şömine animasyonu/çıtırtı testlerde kısa tutulur (gerçekte 12 sn / 60 sn)."""
    from app import fireplace
    monkeypatch.setattr(fireplace, "FIRE_LOOP_SECONDS", 1)
    monkeypatch.setattr(fireplace, "CRACKLE_SECONDS", 8)
