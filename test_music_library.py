import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from music_library import UnsupportedMusicLink, parse_music_link
from update_service import (
    RELEASE_API_URL,
    download_update,
    fetch_latest_release,
    is_newer_version,
)


class ParseMusicLinkTests(unittest.TestCase):
    def test_recognizes_supported_services(self) -> None:
        cases = (
            ("https://soundcloud.com/artist/sets/favorites", "SoundCloud"),
            ("music.yandex.ru/users/listener/playlists/3", "Яндекс Музыка"),
            ("https://open.spotify.com/playlist/example", "Spotify"),
            ("https://youtu.be/dQw4w9WgXcQ", "YouTube"),
            ("https://www.youtube.com/watch?v=example", "YouTube"),
            ("https://music.youtube.com/playlist?list=example", "YouTube Music"),
        )
        for link, expected_name in cases:
            with self.subTest(link=link):
                service, normalized = parse_music_link(link)
                self.assertEqual(service.name, expected_name)
                self.assertTrue(normalized.startswith("https://"))

    def test_rejects_unknown_hosts_and_non_https_urls(self) -> None:
        for link in (
            "https://soundcloud.com.example.org/artist",
            "https://notyoutube.com/watch?v=example",
            "http://open.spotify.com/playlist/example",
            "https://example.org/music",
            "javascript:alert(1)",
        ):
            with self.subTest(link=link):
                with self.assertRaises(UnsupportedMusicLink):
                    parse_music_link(link)

    def test_rejects_credentials_in_url(self) -> None:
        with self.assertRaises(UnsupportedMusicLink):
            parse_music_link("https://user:password@open.spotify.com/playlist/example")


class UpdateVersionTests(unittest.TestCase):
    def test_stable_release_is_newer_than_installed_alpha(self) -> None:
        self.assertTrue(is_newer_version("v0.1.0"))

    def test_newer_patch_is_available(self) -> None:
        self.assertTrue(is_newer_version("v0.1.1"))

    def test_same_or_older_release_is_not_newer(self) -> None:
        self.assertFalse(is_newer_version("v0.1.0-alpha"))
        self.assertFalse(is_newer_version("v0.0.9"))

    def test_invalid_version_is_ignored(self) -> None:
        self.assertFalse(is_newer_version("latest"))

    def test_fetches_release_asset_from_github_api(self) -> None:
        release_data = {
            "tag_name": "v0.1.1",
            "assets": [
                {
                    "name": "MyMusic.exe",
                    "browser_download_url": (
                        "https://github.com/Rom4ik7066/Music/releases/"
                        "download/v0.1.1/MyMusic.exe"
                    ),
                }
            ],
        }
        response = BytesIO(json.dumps(release_data).encode("utf-8"))
        with patch(
            "update_service.urllib.request.urlopen",
            return_value=response,
        ) as open_url:
            release = fetch_latest_release()

        self.assertEqual(release["tag_name"], "v0.1.1")
        self.assertIn("MyMusic.exe", release["asset_url"])
        self.assertEqual(open_url.call_args.args[0].full_url, RELEASE_API_URL)

    def test_missing_github_release_has_clear_error(self) -> None:
        error = HTTPError(RELEASE_API_URL, 404, "Not Found", {}, None)
        with patch("update_service.urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(ValueError, "нет опубликованных релизов"):
                fetch_latest_release()

    def test_download_replaces_destination_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "MyMusic.exe"
            destination.write_bytes(b"previous executable")
            response = BytesIO(b"new executable")
            with patch(
                "update_service.urllib.request.urlopen",
                return_value=response,
            ):
                download_update(
                    "https://github.com/Rom4ik7066/Music/releases/download/"
                    "v0.1.1/MyMusic.exe",
                    str(destination),
                )

            self.assertEqual(destination.read_bytes(), b"new executable")
            self.assertEqual(list(Path(folder).glob("*.part")), [])

    def test_download_rejects_non_github_url(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                download_update(
                    "https://example.org/MyMusic.exe",
                    str(Path(folder) / "MyMusic.exe"),
                )


if __name__ == "__main__":
    unittest.main()
