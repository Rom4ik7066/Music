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
        "accent_pressed": "#6558c9",
        "text": "#f4f5fb",
        "muted": "#a3a9ba",
        "error": "#ff8585",
        "entry": "#222836",
        "border": "#353c4d",
        "card_hover": "#242c39",
        "card_pressed": "#202734",
    },
    "light": {
        "background": "#f3f5f7",
        "card": "#ffffff",
        "accent": "#3867c8",
        "accent_active": "#2d55a8",
        "accent_pressed": "#25478f",
        "text": "#202534",
        "muted": "#626b78",
        "error": "#b42318",
        "entry": "#ffffff",
        "border": "#cbd1da",
        "card_hover": "#e7ebf0",
        "card_pressed": "#dbe1e9",
    },
}


class SmoothButton(tk.Button):
    def __init__(
        self,
        master: tk.Misc,
        palette: dict[str, str],
        variant: str = "secondary",
        **kwargs,
    ) -> None:
        self.palette = palette
        self.variant = variant
        self._normal_color = (
            palette["accent"] if variant == "primary" else palette["card"]
        )
        self._hover_color = (
            palette["accent_active"]
            if variant == "primary"
            else palette["card_hover"]
        )
        self._pressed_color = (
            palette["accent_pressed"]
            if variant == "primary"
            else palette["card_pressed"]
        )
        self._display_color = self._normal_color
        self._animation_id: str | None = None
        self._hovered = False
        self._pressed = False

        kwargs.setdefault("font", ("Segoe UI Semibold", 10))
        kwargs.setdefault("padx", 18 if variant == "primary" else 14)
        kwargs.setdefault("pady", 12 if variant == "primary" else 9)
        super().__init__(
            master,
            bg=self._normal_color,
            fg="#ffffff" if variant == "primary" else palette["text"],
            activebackground=self._normal_color,
            activeforeground="#ffffff" if variant == "primary" else palette["text"],
            disabledforeground=palette["muted"],
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=palette["border"],
            highlightcolor=palette["accent"],
            cursor="hand2",
            takefocus=True,
            **kwargs,
        )
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        self.bind("<ButtonPress-1>", self._on_press, add="+")
        self.bind("<ButtonRelease-1>", self._on_release, add="+")
        self.bind("<FocusIn>", self._on_focus, add="+")
        self.bind("<FocusOut>", self._on_blur, add="+")

    @staticmethod
    def _blend(start: str, end: str, amount: float) -> str:
        start_rgb = tuple(int(start[index:index + 2], 16) for index in (1, 3, 5))
        end_rgb = tuple(int(end[index:index + 2], 16) for index in (1, 3, 5))
        channels = tuple(
            round(source + (target - source) * amount)
            for source, target in zip(start_rgb, end_rgb)
        )
        return "#" + "".join(f"{channel:02x}" for channel in channels)

    def _animate_to(self, target: str) -> None:
        if self._animation_id is not None:
            try:
                self.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None

        start = self._display_color
        frame_count = 8
        frame_index = 0

        def animate() -> None:
            nonlocal frame_index
            frame_index += 1
            progress = frame_index / frame_count
            eased = 1 - (1 - progress) ** 3
            self._display_color = self._blend(start, target, eased)
            try:
                self.configure(
                    bg=self._display_color,
                    activebackground=self._display_color,
                )
            except tk.TclError:
                self._animation_id = None
                return
            if frame_index < frame_count:
                self._animation_id = self.after(16, animate)
            else:
                self._display_color = target
                self._animation_id = None

        self._animation_id = self.after(0, animate)

    def _update_color(self) -> None:
        if self._pressed:
            target = self._pressed_color
        elif self._hovered or self.focus_get() is self:
            target = self._hover_color
        else:
            target = self._normal_color
        self._animate_to(target)

    def _on_enter(self, _event: tk.Event) -> None:
        self._hovered = True
        self._update_color()

    def _on_leave(self, _event: tk.Event) -> None:
        self._hovered = False
        self._pressed = False
        self._update_color()

    def _on_press(self, _event: tk.Event) -> None:
        self._pressed = True
        self._update_color()

    def _on_release(self, _event: tk.Event) -> None:
        self._pressed = False
        self._update_color()

    def _on_focus(self, _event: tk.Event) -> None:
        self.configure(highlightbackground=self.palette["accent"])
        self._update_color()

    def _on_blur(self, _event: tk.Event) -> None:
        self.configure(highlightbackground=self.palette["border"])
        self._update_color()

    def destroy(self) -> None:
        if self._animation_id is not None:
            try:
                self.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None
        super().destroy()


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
        self._page_animation_id: str | None = None
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
        if self._page_animation_id is not None:
            try:
                self.root.after_cancel(self._page_animation_id)
            except tk.TclError:
                pass
            self._page_animation_id = None
        for child in self.root.winfo_children():
            child.destroy()
        page = tk.Frame(
            self.root,
            bg=self.palette["background"],
            padx=38,
            pady=32,
        )
        page.place(relx=0, rely=0, relwidth=1, relheight=1, y=14)
        self._animate_page_in(page)
        header = tk.Frame(page, bg=self.palette["background"])
        header.pack(fill="x")
        tk.Label(
            header,
            text="♫  MY MUSIC",
            bg=self.palette["background"],
            fg=self.palette["accent"],
            font=("Segoe UI Semibold", 10),
        ).pack(side="left")
        SmoothButton(
            header,
            self.palette,
            text="Назад" if self.current_view == "settings" else "Настройки",
            variant="secondary",
            command=(
                self._return_from_settings
                if self.current_view == "settings"
                else self._show_settings
            ),
        ).pack(side="right")
        return page

    def _animate_page_in(self, page: tk.Frame) -> None:
        frame_count = 9
        distance = 14
        frame_index = 0

        def animate() -> None:
            nonlocal frame_index
            if not page.winfo_exists():
                self._page_animation_id = None
                return
            frame_index += 1
            progress = min(frame_index / frame_count, 1)
            eased = 1 - (1 - progress) ** 3
            page.place_configure(y=round(distance * (1 - eased)))
            if frame_index < frame_count:
                self._page_animation_id = self.root.after(16, animate)
            else:
                self._page_animation_id = None

        self._page_animation_id = self.root.after(16, animate)

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
        SmoothButton(
            page,
            self.palette,
            text="Продолжить",
            variant="primary",
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
        SmoothButton(
            page,
            self.palette,
            text="Открыть в окне проигрывателя",
            variant="primary",
            command=self._open_link,
        ).pack(fill="x")
        SmoothButton(
            page,
            self.palette,
            text="Изменить ссылку",
            variant="secondary",
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

        SmoothButton(
            page,
            self.palette,
            text="Проверить обновления",
            variant="primary",
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
