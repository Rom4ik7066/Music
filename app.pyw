import ctypes
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


def _show_startup_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, message, "Моя музыка", 0x10)


def _check_dependencies() -> bool:
    required_modules = ("tkinter", "webbrowser", "music_library")
    missing = [
        name for name in required_modules if importlib.util.find_spec(name) is None
    ]
    if missing:
        _show_startup_error(
            "Не найдены необходимые компоненты: "
            + ", ".join(missing)
            + ". Переустановите приложение или Python с поддержкой Tcl/Tk."
        )
        return False
    return True


if not _check_dependencies():
    sys.exit(1)

if len(sys.argv) >= 3 and sys.argv[1] == "--webview":
    if importlib.util.find_spec("webview") is None:
        _show_startup_error(
            "Не найден встроенный браузер pywebview. "
            "Пересоберите приложение командой build_exe.bat."
        )
        sys.exit(1)
    from webview_window import run_browser_window

    run_browser_window(sys.argv[2])
    sys.exit(0)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from music_library import UnsupportedMusicLink, parse_music_link
from app_version import APP_VERSION, DISPLAY_VERSION
from update_service import download_update, fetch_latest_release


THEMES = {
    "dark": {
        "background": "#10131b",
        "card": "#191e29",
        "accent": "#8b7cff",
        "accent_active": "#7769e8",
        "text": "#f4f5fb",
        "muted": "#a3a9ba",
        "error": "#ff8585",
        "entry": "#222836",
        "border": "#353c4d",
    },
    "light": {
        "background": "#f3f5f7",
        "card": "#ffffff",
        "accent": "#3867c8",
        "accent_active": "#2d55a8",
        "text": "#202534",
        "muted": "#626b78",
        "error": "#b42318",
        "entry": "#ffffff",
        "border": "#cbd1da",
    },
}


class MusicLibraryApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Моя музыка")
        self.root.resizable(False, False)
        self.root.geometry("520x410")
        self._center_window()

        self.link = ""
        self.service_name = ""
        self.error_message = tk.StringVar()
        self.theme = self._load_theme()
        self.palette = THEMES[self.theme]
        self.current_view = "link"
        self.previous_view = "link"
        self.theme_var = tk.StringVar(value=self.theme)
        self.root.configure(bg=self.palette["background"])
        self._configure_styles()
        self._show_link_form()

    @staticmethod
    def _settings_path() -> Path:
        app_data = os.environ.get("APPDATA", str(Path.home()))
        return Path(app_data) / "GitasMusic" / "settings.json"

    def _load_theme(self) -> str:
        try:
            with self._settings_path().open(encoding="utf-8") as settings_file:
                theme = json.load(settings_file).get("theme", "dark")
        except (OSError, ValueError, AttributeError):
            return "dark"
        return theme if theme in THEMES else "dark"

    def _save_theme(self) -> None:
        path = self._settings_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as settings_file:
                json.dump({"theme": self.theme}, settings_file)
        except OSError:
            pass

    def _center_window(self) -> None:
        self.root.update_idletasks()
        width, height = 520, 410
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Music.TEntry",
            fieldbackground=self.palette["entry"],
            foreground=self.palette["text"],
            insertcolor=self.palette["text"],
            bordercolor=self.palette["border"],
            lightcolor=self.palette["border"],
            darkcolor=self.palette["border"],
            padding=12,
        )
        style.configure(
            "Accent.TButton",
            background=self.palette["accent"],
            foreground="#ffffff",
            borderwidth=0,
            padding=(16, 12),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Accent.TButton",
            background=[
                ("active", self.palette["accent_active"]),
                ("disabled", self.palette["border"]),
            ],
        )
        style.configure(
            "Secondary.TButton",
            background=self.palette["card"],
            foreground=self.palette["text"],
            borderwidth=0,
            padding=(14, 10),
            font=("Segoe UI", 9),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", self.palette["border"])],
        )
        style.configure(
            "Theme.TRadiobutton",
            background=self.palette["background"],
            foreground=self.palette["text"],
            font=("Segoe UI", 10),
        )
        style.map(
            "Theme.TRadiobutton",
            background=[("active", self.palette["background"])],
            foreground=[("disabled", self.palette["muted"])],
        )

    def _new_page(self) -> tk.Frame:
        for child in self.root.winfo_children():
            child.destroy()
        page = tk.Frame(
            self.root,
            bg=self.palette["background"],
            padx=38,
            pady=32,
        )
        page.pack(fill="both", expand=True)
        header = tk.Frame(page, bg=self.palette["background"])
        header.pack(fill="x")
        tk.Label(
            header,
            text="♫  MY MUSIC",
            bg=self.palette["background"],
            fg=self.palette["accent"],
            font=("Segoe UI Semibold", 10),
        ).pack(side="left")
        ttk.Button(
            header,
            text="Назад" if self.current_view == "settings" else "Настройки",
            style="Secondary.TButton",
            command=(
                self._return_from_settings
                if self.current_view == "settings"
                else self._show_settings
            ),
        ).pack(side="right")
        return page

    def _show_link_form(self) -> None:
        self.current_view = "link"
        self.error_message.set("")
        page = self._new_page()
        tk.Label(
            page,
            text="Где ваша музыка?",
            bg=self.palette["background"],
            fg=self.palette["text"],
            font=("Segoe UI Semibold", 22),
        ).pack(anchor="w", pady=(26, 8))
        tk.Label(
            page,
            text="Вставьте ссылку на плейлист, альбом, профиль или трек.",
            bg=self.palette["background"],
            fg=self.palette["muted"],
            font=("Segoe UI", 10),
            wraplength=430,
            justify="left",
        ).pack(anchor="w", pady=(0, 20))

        self.link_entry = ttk.Entry(page, style="Music.TEntry", font=("Segoe UI", 10))
        self.link_entry.pack(fill="x")
        self.link_entry.bind("<Return>", lambda _event: self._connect())
        self.link_entry.focus_set()

        tk.Label(
            page,
            text="SoundCloud  ·  Яндекс Музыка  ·  Spotify\nYouTube  ·  YouTube Music",
            bg=self.palette["background"],
            fg=self.palette["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(12, 20))
        ttk.Button(
            page,
            text="Продолжить",
            style="Accent.TButton",
            command=self._connect,
        ).pack(fill="x")
        tk.Label(
            page,
            textvariable=self.error_message,
            bg=self.palette["background"],
            fg=self.palette["error"],
            font=("Segoe UI", 9),
            wraplength=430,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))
        tk.Label(
            page,
            text="Откройте ссылку во встроенном окне проигрывателя.",
            bg=self.palette["background"],
            fg=self.palette["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", side="bottom", pady=(16, 0))

    def _connect(self) -> None:
        try:
            service, link = parse_music_link(self.link_entry.get())
        except UnsupportedMusicLink as error:
            self.error_message.set(str(error))
            return

        self.link = link
        self.service_name = service.name
        self._show_library()

    def _show_library(self) -> None:
        self.current_view = "library"
        self.error_message.set("")
        page = self._new_page()
        tk.Label(
            page,
            text="Ваша музыка",
            bg=self.palette["background"],
            fg=self.palette["text"],
            font=("Segoe UI Semibold", 22),
        ).pack(anchor="w", pady=(26, 8))
        tk.Label(
            page,
            text="Сервис подключён",
            bg=self.palette["background"],
            fg=self.palette["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(0, 22))

        card = tk.Frame(page, bg=self.palette["card"], padx=18, pady=16)
        card.pack(fill="x")
        tk.Label(
            card,
            text=self.service_name,
            bg=self.palette["card"],
            fg=self.palette["accent"],
            font=("Segoe UI Semibold", 11),
        ).pack(anchor="w")
        tk.Label(
            card,
            text=self.link,
            bg=self.palette["card"],
            fg=self.palette["text"],
            font=("Segoe UI", 9),
            wraplength=390,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        tk.Label(
            page,
            text="Откройте ссылку в сервисе, чтобы увидеть библиотеку "
            "и включить доступную вам музыку.",
            bg=self.palette["background"],
            fg=self.palette["muted"],
            font=("Segoe UI", 9),
            wraplength=430,
            justify="left",
        ).pack(anchor="w", pady=(18, 20))
        ttk.Button(
            page,
            text="Открыть в окне проигрывателя",
            style="Accent.TButton",
            command=self._open_link,
        ).pack(fill="x")
        ttk.Button(
            page,
            text="Изменить ссылку",
            style="Secondary.TButton",
            command=self._show_link_form,
        ).pack(fill="x", pady=(10, 0))
        tk.Label(
            page,
            textvariable=self.error_message,
            bg=self.palette["background"],
            fg=self.palette["error"],
            font=("Segoe UI", 9),
            wraplength=430,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _show_settings(self) -> None:
        if self.current_view != "settings":
            self.previous_view = self.current_view
        self.current_view = "settings"
        page = self._new_page()
        tk.Label(
            page,
            text="Настройки",
            bg=self.palette["background"],
            fg=self.palette["text"],
            font=("Segoe UI Semibold", 22),
        ).pack(anchor="w", pady=(26, 20))
        tk.Label(
            page,
            text="Тема оформления",
            bg=self.palette["background"],
            fg=self.palette["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(0, 8))
        self.theme_var.set(self.theme)
        choices = tk.Frame(page, bg=self.palette["background"])
        choices.pack(anchor="w", pady=(0, 20))
        for value, label in (("dark", "Тёмная"), ("light", "Светлая")):
            ttk.Radiobutton(
                choices,
                text=label,
                value=value,
                variable=self.theme_var,
                style="Theme.TRadiobutton",
                command=lambda selected=value: self._set_theme(selected),
            ).pack(side="left", padx=(0, 24))

        ttk.Button(
            page,
            text="Проверить обновления",
            style="Accent.TButton",
            command=self._check_for_updates,
        ).pack(fill="x")
        tk.Label(
            page,
            text=f"Версия приложения: {DISPLAY_VERSION}",
            bg=self.palette["background"],
            fg=self.palette["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", side="bottom")

    def _return_from_settings(self) -> None:
        if self.previous_view == "library" and self.link:
            self._show_library()
        else:
            self._show_link_form()

    def _set_theme(self, theme: str) -> None:
        if theme not in THEMES or theme == self.theme:
            return
        self.theme = theme
        self.palette = THEMES[theme]
        self.root.configure(bg=self.palette["background"])
        self._configure_styles()
        self._save_theme()
        self._show_settings()

    def _check_for_updates(self) -> None:
        try:
            release = fetch_latest_release()
        except (OSError, ValueError) as error:
            messagebox.showerror(
                "Проверка обновлений",
                f"Не удалось проверить GitHub Releases.\n\n{error}",
                parent=self.root,
            )
            return

        if release is None:
            messagebox.showinfo(
                "Проверка обновлений",
                f"Установлена последняя версия ({DISPLAY_VERSION}).",
                parent=self.root,
            )
            return

        answer = messagebox.askyesno(
            "Доступно обновление",
            f"Доступна версия {release['tag_name']}.\n"
            f"Текущая версия: {DISPLAY_VERSION} ({APP_VERSION}).\n\n"
            "Скачать обновление?",
            parent=self.root,
        )
        if not answer:
            return

        destination = filedialog.asksaveasfilename(
            parent=self.root,
            title="Сохранить обновление",
            initialfile="MyMusic.exe",
            defaultextension=".exe",
            filetypes=(("Приложение Windows", "*.exe"),),
        )
        if not destination:
            return
        try:
            download_update(release["asset_url"], destination)
        except (OSError, ValueError) as error:
            messagebox.showerror(
                "Загрузка обновления",
                f"Не удалось скачать обновление.\n\n{error}",
                parent=self.root,
            )
            return
        messagebox.showinfo(
            "Обновление загружено",
            "Файл обновления скачан. Закройте приложение и запустите "
            "скачанный MyMusic.exe.",
            parent=self.root,
        )

    def _open_link(self) -> None:
        try:
            if getattr(sys, "frozen", False):
                command = [sys.executable, "--webview", self.link]
            else:
                command = [
                    sys.executable,
                    os.path.abspath(__file__),
                    "--webview",
                    self.link,
                ]
            subprocess.Popen(command)
        except OSError as error:
            self.error_message.set(
                f"Не удалось запустить окно проигрывателя: {error}"
            )


def main() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as error:
        _show_startup_error(
            "Не удалось запустить графический интерфейс Tcl/Tk.\n\n"
            f"Проверьте установку Python или переустановите приложение.\n\n{error}"
        )
        sys.exit(1)
    MusicLibraryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
