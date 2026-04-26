import logging
import requests
from pathlib import Path
from typing import Callable, Optional

import config

logger = logging.getLogger(__name__)


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _download(
    url: str,
    dest: Path,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    chunk_size: int = 1024 * 256,
) -> Path:
    if dest.exists():
        logger.info("File already exists, skipping download: %s", dest)
        return dest

    logger.info("Downloading %s → %s", url, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", -1))
        downloaded = 0

        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)

    logger.info("Download complete: %s (%s)", dest, _human_bytes(dest.stat().st_size))
    return dest



def download_small(
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Path:
    return _download(config.SMALL_DUMP_URL, config.SMALL_DUMP_FILE, progress_cb)


def download_full(
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Path:
    return _download(config.FULL_DUMP_URL, config.FULL_DUMP_FILE, progress_cb)
