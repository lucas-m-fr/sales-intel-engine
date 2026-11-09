import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env(path: Path | None = None) -> None:
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "").strip()
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "").strip()
NVIDIA_BASE_URL = os.getenv(
    "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1/chat/completions"
)
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
ARCHIVE_DIR = Path(os.getenv("ARCHIVE_DIR", str(ROOT / "archive")))
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data")))


def configure(firecrawl_api_key=None, nvidia_api_key=None, nvidia_model=None, nvidia_base_url=None):
    """Set runtime credentials (used by the Streamlit UI)."""
    global FIRECRAWL_API_KEY, NVIDIA_API_KEY, NVIDIA_MODEL, NVIDIA_BASE_URL
    if firecrawl_api_key:
        FIRECRAWL_API_KEY = firecrawl_api_key.strip()
    if nvidia_api_key:
        NVIDIA_API_KEY = nvidia_api_key.strip()
    if nvidia_model:
        NVIDIA_MODEL = nvidia_model.strip()
    if nvidia_base_url:
        NVIDIA_BASE_URL = nvidia_base_url.strip()


def load_api_key():
    return FIRECRAWL_API_KEY or None
