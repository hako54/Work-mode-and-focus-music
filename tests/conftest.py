import os
import tempfile

# Modüller CONFIG'i import anında okur; testler geçici bir veri klasörü kullanır.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="focusmusic-test-")
os.environ["DRY_RUN"] = "1"
for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "STABILITY_API_KEY"):
    os.environ.pop(k, None)
