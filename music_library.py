from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class MusicService:
    name: str
    hosts: frozenset[str]


SERVICES = (
    MusicService(
        "SoundCloud",
        frozenset({"soundcloud.com", "on.soundcloud.com"}),
    ),
    MusicService(
        "Яндекс Музыка",
        frozenset(
            {
                "music.yandex.ru",
                "music.yandex.com",
                "music.yandex.kz",
                "music.yandex.by",
            }
        ),
    ),
    MusicService(
        "Spotify",
        frozenset({"open.spotify.com", "spotify.com", "www.spotify.com"}),
    ),
    MusicService(
        "YouTube",
        frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}),
    ),
    MusicService(
        "YouTube Music",
        frozenset({"music.youtube.com"}),
    ),
)


class UnsupportedMusicLink(ValueError):
    """Raised when a link does not belong to a supported music service."""


def parse_music_link(value: str) -> tuple[MusicService, str]:
    """Validate a supported service URL and return its service and normalized URL."""
    value = value.strip()
    if not value or any(ord(character) < 32 for character in value):
        raise UnsupportedMusicLink("Вставьте корректную ссылку на музыкальный сервис.")

    if "://" not in value:
        value = f"https://{value}"

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError as error:
        raise UnsupportedMusicLink(
            "Не удалось разобрать ссылку. Проверьте её и попробуйте снова."
        ) from error

    try:
        port = parsed.port
    except ValueError as error:
        raise UnsupportedMusicLink("В ссылке указан некорректный порт.") from error

    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or "@" in parsed.netloc
        or port not in (None, 443)
    ):
        raise UnsupportedMusicLink(
            "Нужна ссылка, начинающаяся с https://, на поддерживаемый сервис."
        )

    service = next((item for item in SERVICES if hostname.lower() in item.hosts), None)
    if service is None:
        raise UnsupportedMusicLink(
            "Поддерживаются SoundCloud, Яндекс Музыка, Spotify, YouTube "
            "и YouTube Music."
        )

    return service, parsed.geturl()
