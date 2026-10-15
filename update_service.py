import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional

from app_version import APP_VERSION

GITHUB_REPOSITORY = "Rom4ik7066/Music"
RELEASE_API_URL = (
    f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
)
MAX_RELEASE_METADATA_SIZE = 1024 * 1024
MAX_UPDATE_SIZE = 300 * 1024 * 1024


def _version_parts(value: str) -> tuple[tuple[int, int, int], bool]:
    match = re.fullmatch(
        r"v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?", value.strip()
    )
    if match is None:
        raise ValueError(f"Неподдерживаемый формат версии: {value}")
    numbers = tuple(int(match.group(index)) for index in (1, 2, 3))
    return numbers, match.group(4) is not None


def is_newer_version(candidate: str, current: str = APP_VERSION) -> bool:
    try:
        candidate_numbers, candidate_is_prerelease = _version_parts(candidate)
        current_numbers, current_is_prerelease = _version_parts(current)
    except ValueError:
        return False
    if candidate_numbers != current_numbers:
        return candidate_numbers > current_numbers
    return current_is_prerelease and not candidate_is_prerelease


def fetch_latest_release() -> dict[str, str] | None:
    request = urllib.request.Request(
        RELEASE_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "GitasMusic-Updater",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = response.read(MAX_RELEASE_METADATA_SIZE + 1)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise ValueError("В репозитории пока нет опубликованных релизов.") from error
        raise
    if len(payload) > MAX_RELEASE_METADATA_SIZE:
        raise OSError("Ответ GitHub превышает допустимый размер.")

    release = json.loads(payload.decode("utf-8"))
    tag_name = release.get("tag_name", "")
    if not tag_name:
        raise ValueError("В релизе GitHub отсутствует версия.")
    if not is_newer_version(tag_name):
        return None

    for asset in release.get("assets", []):
        if asset.get("name") == "MyMusic.exe":
            asset_url = asset.get("browser_download_url", "")
            parsed_url = urlparse(asset_url)
            if parsed_url.scheme == "https" and parsed_url.hostname == "github.com":
                return {"tag_name": tag_name, "asset_url": asset_url}
            raise ValueError("Ссылка на файл обновления некорректна.")
    raise ValueError("В релизе нет файла MyMusic.exe.")


def download_update(asset_url: str, destination: str) -> None:
    parsed_url = urlparse(asset_url)
    if parsed_url.scheme != "https" or parsed_url.hostname != "github.com":
        raise ValueError("Разрешена загрузка только с github.com по HTTPS.")

    request = urllib.request.Request(
        asset_url,
        headers={"User-Agent": "GitasMusic-Updater"},
    )
    destination_path = Path(destination)
    temporary_path: Optional[Path] = None
    downloaded = 0
    try:
        with tempfile.NamedTemporaryFile(
            prefix="gitasmusic-update-",
            suffix=".part",
            dir=destination_path.parent,
            delete=False,
        ) as output:
            temporary_path = Path(output.name)
            with urllib.request.urlopen(request, timeout=30) as response:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > MAX_UPDATE_SIZE:
                        raise OSError("Файл обновления превышает 300 МБ.")
                    output.write(chunk)
        if downloaded == 0:
            raise OSError("GitHub вернул пустой файл обновления.")
        os.replace(temporary_path, destination_path)
    except (OSError, ValueError):
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise