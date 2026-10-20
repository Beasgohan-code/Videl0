# Videl integration settings mapped to Eldian Music API's downloader.
# Upstream: https://github.com/Eldian-Network/eldian-music-api (MIT)
from dataclasses import dataclass
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    yt_dlp_format: str = os.getenv("YT_DLP_FORMAT", "bestaudio/best")
    yt_dlp_socket_timeout: int = int(os.getenv("YT_DLP_SOCKET_TIMEOUT", "20"))
    yt_dlp_retries: int = int(os.getenv("YT_DLP_RETRIES", "3"))
    download_cleanup_seconds: int = int(os.getenv("DOWNLOAD_CLEANUP_SECONDS", "900"))
    yt_dlp_proxy: str | None = os.getenv("PROXY_URL") or os.getenv("YOUTUBE_PROXY") or os.getenv("YT_DLP_PROXY")
    yt_dlp_proxy_file: str | None = os.getenv("YOUTUBE_PROXY_FILE") or None
    yt_dlp_cookies: str | None = os.getenv("YOUTUBE_COOKIES") or None
    yt_dlp_cookies_file: str | None = os.getenv("YTDLP_COOKIES") or os.getenv("YOUTUBE_COOKIES_FILE") or None


settings = Settings()
