import ctypes
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import winreg

import webview

from music_library import UnsupportedMusicLink, parse_music_link


WEBVIEW2_DOWNLOAD_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
WEBVIEW2_CLIENTS_KEY = r"SOFTWARE\Microsoft\EdgeUpdate\Clients"
MESSAGE_ERROR = 0x10
MESSAGE_QUESTION = 0x24
MESSAGE_YESNO = 0x04


def _message(text: str, flags: int = MESSAGE_ERROR) -> int:
    return ctypes.windll.user32.MessageBoxW(None, text, "Моя музыка", flags)


def _webview2_installed() -> bool:
    registry_views = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)
    registry_hives = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    for hive in registry_hives:
        for view in registry_views:
            try:
                with winreg.OpenKey(
                    hive, WEBVIEW2_CLIENTS_KEY, 0, winreg.KEY_READ | view
                ) as clients:
                    for index in range(winreg.QueryInfoKey(clients)[0]):
                        try:
                            client_name = winreg.EnumKey(clients, index)
                            with winreg.OpenKey(clients, client_name) as client:
                                values = {}
                                for value_index in range(winreg.QueryInfoKey(client)[1]):
                                    try:
                                        name, value, _ = winreg.EnumValue(
                                            client, value_index
                                        )
                                        values[name.lower()] = str(value)
                                    except OSError:
                                        continue
                                name = values.get("name", "").lower()
                                version = values.get("pv", "")
                                if "webview2" in name and version not in ("", "0.0.0.0"):
                                    return True
                        except OSError:
                            continue
            except OSError:
                continue
    return False


def _verify_microsoft_signature(installer_path: str) -> bool:
    escaped_path = installer_path.replace("'", "''")
    command = (
        "$signature = Get-AuthenticodeSignature -LiteralPath "
        f"'{escaped_path}'; "
        "if ($signature.Status -ne 'Valid' -or "
        "$signature.SignerCertificate.Subject -notmatch 'Microsoft') { exit 1 }"
    )
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _install_webview2() -> bool:
    answer = _message(
        "Для встроенного проигрывателя нужен Microsoft Edge WebView2 Runtime.\n"
        "Скачать установщик с официального сайта Microsoft и установить его сейчас?",
        MESSAGE_QUESTION | MESSAGE_YESNO,
    )
    if answer != 6:
        return False

    installer_path = ""
    try:
        with urllib.request.urlopen(WEBVIEW2_DOWNLOAD_URL, timeout=30) as response:
            with tempfile.NamedTemporaryFile(
                prefix="mymusic-webview2-", suffix=".exe", delete=False
            ) as installer:
                installer_path = installer.name
                total_size = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > 50 * 1024 * 1024:
                        raise OSError("Установщик превышает допустимый размер.")
                    installer.write(chunk)

        if not installer_path or os.path.getsize(installer_path) == 0:
            raise OSError("Скачанный установщик пуст.")
        if not _verify_microsoft_signature(installer_path):
            raise OSError(
                "Не удалось подтвердить цифровую подпись Microsoft у установщика."
            )

        subprocess.run(
            [installer_path, "/silent", "/install"],
            check=True,
            timeout=300,
        )
        return _webview2_installed()
    except (
        OSError,
        urllib.error.URLError,
        subprocess.SubprocessError,
    ) as error:
        _message(
            "Не удалось установить Microsoft Edge WebView2 Runtime.\n\n"
            f"{error}\n\n"
            "Установите WebView2 Runtime с официального сайта Microsoft и "
            "запустите проигрыватель снова."
        )
        return False
    finally:
        if installer_path and os.path.exists(installer_path):
            try:
                os.remove(installer_path)
            except OSError:
                pass


def run_browser_window(value: str) -> None:
    try:
        service, url = parse_music_link(value)
    except UnsupportedMusicLink as error:
        _message(str(error))
        return

    if not _webview2_installed() and not _install_webview2():
        _message(
            "Встроенное окно проигрывателя не запущено: Microsoft Edge "
            "WebView2 Runtime не установлен."
        )
        return

    try:
        webview.create_window(
            f"{service.name} — Моя музыка",
            url=url,
            width=1100,
            height=760,
            min_size=(640, 480),
        )
        webview.start(gui="edgechromium")
    except Exception as error:
        _message(
            "Не удалось открыть встроенное окно проигрывателя.\n\n"
            f"{error}\n\n"
            "Проверьте установку Microsoft Edge WebView2 Runtime."
        )
