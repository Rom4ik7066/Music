import unittest

from music_library import UnsupportedMusicLink, parse_music_link


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


if __name__ == "__main__":
    unittest.main()
