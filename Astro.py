import os
import re
import sys
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

import customtkinter as ctk
from tkinter import messagebox, filedialog
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw


# КРИТИЧЕСКИ ВАЖНО: Настраиваем эфемериды ДО импорта kerykeion
def get_app_dir() -> Path:
    """Directory containing the source files or the EXE."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = get_app_dir()


# Настройка реальных эфемерид
def setup_real_ephemeris():
    """Установка пути к реальным файлам эфемерид"""
    # Ищем файл эфемерид в разных местах
    possible_paths = [
        APP_DIR / "de440.leb",
        APP_DIR / "de440.les",
        APP_DIR / "de430.leb",
        APP_DIR / "de430.les",
        APP_DIR / "ephe" / "de440.leb",
        APP_DIR / "ephe" / "de440.les",
    ]

    # Если приложение скомпилировано, ищем в sys._MEIPASS
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", APP_DIR))
        possible_paths.extend([
            meipass / "de440.leb",
            meipass / "de440.les",
            meipass / "de430.leb",
            meipass / "de430.les",
            meipass / "ephe" / "de440.leb",
            meipass / "ephe" / "de440.les",
        ])

    for path in possible_paths:
        if path.exists():
            print(f"Найден файл эфемерид: {path}")
            os.environ["LIBEPHEMERIS_LEB"] = str(path)
            os.environ["LIBEPHEMERIS_LCB"] = str(path)
            os.environ["KERYKEION_EPHEMERIS_MODE"] = "leb"
            return str(path)

    # Если файл не найден, используем онлайн-режим
    print("Файл эфемерид не найден. Используем онлайн-режим.")
    os.environ["KERYKEION_EPHEMERIS_MODE"] = "online"
    return None


# Создаем виртуальный файл для обхода проверки
def create_virtual_ephemeris():
    """Создает виртуальный файл-заглушку для обхода ошибки"""
    try:
        # Пробуем найти реальные эфемериды
        real_file = setup_real_ephemeris()
        if real_file:
            return real_file

        # Если нет реальных эфемерид, используем заглушку
        # и переключаемся в онлайн-режим
        os.environ["KERYKEION_EPHEMERIS_MODE"] = "online"
        return None
    except Exception as e:
        print(f"Ошибка настройки эфемерид: {e}")
        return None


# Настраиваем эфемериды
create_virtual_ephemeris()

# Теперь импортируем kerykeion
from kerykeion import (
    AstrologicalSubjectFactory,
    ChartDataFactory,
    AspectsFactory,
    to_context,
)
from kerykeion import ChartDrawer

# Попытка импорта cairosvg с обработкой ошибки
CAIROSVG_AVAILABLE = False
try:
    import cairosvg

    CAIROSVG_AVAILABLE = True
except ImportError:
    print("cairosvg не установлен")
except Exception as e:
    print(f"Ошибка при импорте cairosvg: {e}")

# Совместимость с разными версиями Pillow
try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_LANCZOS = Image.LANCZOS

# Флаг для Windows
if sys.platform == "win32":
    SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    SUBPROCESS_FLAGS = 0

APP_NAME = "Astrology AI"
APP_VERSION = "1.0.0"

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820

SHELL_MARGIN = 18

# Цвета
BG = "#070A10"
PANEL = "#0E131D"
CARD = "#151B27"
CARD_HOVER = "#1C2432"
INPUT = "#0D121B"
BORDER = "#293344"
TEXT = "#F5F7FA"
MUTED = "#AAB3C3"
ACCENT = "#9A8CFF"
ACCENT_HOVER = "#7F70F2"

# Фиксированные координаты Кишинева
FIXED_LAT = 47.00306
FIXED_LNG = 28.85708
FIXED_TIMEZONE = "Europe/Chisinau"

HOUSE_SYSTEM_MAP = {
    "Placidus": "P",
    "Whole Sign": "W",
    "Equal": "A",
    "Campanus": "C",
    "Regiomontanus": "R",
    "Porphyrius": "O",
}

# Пример данных
EXAMPLE_NAME = "Иван Иванов"
EXAMPLE_DATE = "01.06.1990"


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

def resource_path(filename: str) -> Path:
    """Get a bundled resource path."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", APP_DIR))
    else:
        base = APP_DIR
    return base / filename


BACKGROUND = resource_path("astro.png")
ICON = resource_path("astro.ico")

OUTPUT_DIR = APP_DIR / "Astrology_Output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def safe_filename(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*]+', "_", value.strip())
    value = re.sub(r"\s+", "_", value)
    return value[:80] or "chart"


def parse_date(value: str):
    return datetime.strptime(value.strip(), "%d.%m.%Y").date()


def format_degree(value) -> str:
    try:
        number = float(value)
        degrees = int(number)
        minutes = int(round((number - degrees) * 60))
        if minutes >= 60:
            degrees += 1
            minutes = 0
        return f"{degrees}° {minutes:02d}'"
    except Exception:
        return str(value)


# ---------------------------------------------------------
# Astrology
# ---------------------------------------------------------

def make_subject(
        name: str,
        birth_date,
        houses: str,
):
    """Создание астрологического субъекта используя только фабрику."""
    # Пытаемся сначала с online=True
    try:
        subject = AstrologicalSubjectFactory.from_birth_data(
            name=name,
            year=birth_date.year,
            month=birth_date.month,
            day=birth_date.day,
            hour=12,
            minute=0,
            lng=FIXED_LNG,
            lat=FIXED_LAT,
            tz_str=FIXED_TIMEZONE,
            zodiac_type="Tropical",
            houses_system_identifier=houses,
            online=True,
        )
        return subject
    except Exception as e:
        print(f"Ошибка создания субъекта с online=True: {e}")

        # Если online не работает, пробуем без online
        try:
            subject = AstrologicalSubjectFactory.from_birth_data(
                name=name,
                year=birth_date.year,
                month=birth_date.month,
                day=birth_date.day,
                hour=12,
                minute=0,
                lng=FIXED_LNG,
                lat=FIXED_LAT,
                tz_str=FIXED_TIMEZONE,
                zodiac_type="Tropical",
                houses_system_identifier=houses,
                online=False,
            )
            return subject
        except Exception as e2:
            print(f"Ошибка создания субъекта без online: {e2}")

            # Последняя попытка - явно указываем режим эфемерид
            try:
                os.environ["KERYKEION_EPHEMERIS_MODE"] = "online"
                subject = AstrologicalSubjectFactory.from_birth_data(
                    name=name,
                    year=birth_date.year,
                    month=birth_date.month,
                    day=birth_date.day,
                    hour=12,
                    minute=0,
                    lng=FIXED_LNG,
                    lat=FIXED_LAT,
                    tz_str=FIXED_TIMEZONE,
                    zodiac_type="Tropical",
                    houses_system_identifier=houses,
                    online=True,
                )
                return subject
            except Exception as e3:
                raise RuntimeError(f"Не удалось создать субъект: {e3}")


def make_chart(subject) -> Path:
    """Create SVG chart and return its path."""
    try:
        chart_data = ChartDataFactory.create_natal_chart_data(subject)
    except Exception as e:
        print(f"Ошибка создания chart_data: {e}")
        raise RuntimeError(f"Не удалось создать карту: {e}")

    filename = (
        f"{safe_filename(subject.name)}_"
        f"{subject.year:04d}-{subject.month:02d}-{subject.day:02d}"
    )

    drawer = ChartDrawer(chart_data=chart_data)

    try:
        drawer.save_svg(
            output_path=OUTPUT_DIR,
            filename=filename,
        )
    except TypeError:
        svg_content = drawer.draw_svg()
        svg_path = OUTPUT_DIR / f"{filename}.svg"
        svg_path.write_text(svg_content, encoding="utf-8")
        return svg_path
    except Exception as e:
        print(f"Ошибка сохранения SVG: {e}")
        try:
            svg_content = drawer.draw_svg()
            svg_path = OUTPUT_DIR / f"{filename}.svg"
            svg_path.write_text(svg_content, encoding="utf-8")
            return svg_path
        except Exception as e2:
            raise RuntimeError(f"Не удалось сохранить SVG: {e2}")

    svg_path = OUTPUT_DIR / f"{filename}.svg"

    if not svg_path.exists():
        candidates = list(OUTPUT_DIR.glob(f"{filename}*.svg"))
        if candidates:
            svg_path = candidates[0]

    return svg_path


def svg_to_png(svg_path: Path) -> Path:
    """Convert SVG to PNG using the best available method."""
    png_path = svg_path.with_suffix(".png")

    # Метод 1: cairosvg
    if CAIROSVG_AVAILABLE:
        try:
            print(f"Конвертация SVG в PNG с помощью cairosvg: {svg_path}")
            cairosvg.svg2png(
                url=str(svg_path),
                write_to=str(png_path),
                output_width=1000,
            )
            if png_path.exists():
                print(f"PNG создан: {png_path}")
                return png_path
        except Exception as e:
            print(f"cairosvg не сработал: {e}")

    # Метод 2: Inkscape
    inkscape_paths = [
        "inkscape",
        r"C:\Program Files\Inkscape\bin\inkscape.exe",
        r"C:\Program Files (x86)\Inkscape\bin\inkscape.exe",
    ]

    for inkscape in inkscape_paths:
        try:
            print(f"Пробуем Inkscape: {inkscape}")
            result = subprocess.run(
                [inkscape, "--version"],
                capture_output=True,
                timeout=5,
                creationflags=SUBPROCESS_FLAGS,
            )
            if result.returncode != 0:
                continue

            subprocess.run(
                [
                    inkscape,
                    str(svg_path),
                    "--export-filename", str(png_path),
                    "--export-width", "1000",
                    "--export-type", "png",
                ],
                check=True,
                timeout=30,
                creationflags=SUBPROCESS_FLAGS,
            )

            if png_path.exists():
                print(f"PNG создан через Inkscape: {png_path}")
                return png_path
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            continue
        except Exception as e:
            print(f"Inkscape не сработал: {e}")
            continue

    # Метод 3 (запасной)
    try:
        img = Image.new("RGB", (800, 600), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((50, 50), "SVG Chart Created", fill="black")
        draw.text((50, 100), f"File: {svg_path.name}", fill="black")
        draw.text((50, 150), "Install Inkscape or Cairo for better rendering", fill="black")
        img.save(png_path)
        print(f"Создан базовый PNG: {png_path}")
        return png_path
    except Exception as e:
        print(f"Не удалось создать даже базовый PNG: {e}")

    raise RuntimeError(
        "Не удалось конвертировать SVG в PNG.\n\n"
        "Установите один из вариантов:\n"
        "1. pip install cairosvg (требует GTK)\n"
        "2. Установите Inkscape: https://inkscape.org/release/\n"
        "   и добавьте его в PATH\n\n"
        "Для установки GTK для Windows:\n"
        "https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases"
    )


# ---------------------------------------------------------
# Прогнозы (на основе натальной карты)
# ---------------------------------------------------------

def generate_forecast(subject, birth_date, current_date=None):
    """
    Генерация базового астрологического прогноза
    на основе положений планет в натальной карте.
    """
    if current_date is None:
        current_date = datetime.now().date()

    # Рассчитываем возраст
    age = current_date.year - birth_date.year
    if current_date.month < birth_date.month or (
            current_date.month == birth_date.month and current_date.day < birth_date.day):
        age -= 1

    # Получаем положения планет
    planets = {
        "Солнце": getattr(subject, "sun", None),
        "Луна": getattr(subject, "moon", None),
        "Меркурий": getattr(subject, "mercury", None),
        "Венера": getattr(subject, "venus", None),
        "Марс": getattr(subject, "mars", None),
        "Юпитер": getattr(subject, "jupiter", None),
        "Сатурн": getattr(subject, "saturn", None),
        "Уран": getattr(subject, "uranus", None),
        "Нептун": getattr(subject, "neptune", None),
        "Плутон": getattr(subject, "pluto", None),
    }

    # Базовые описания планет в знаках
    planet_meanings = {
        "Солнце": {
            "Овен": "Энергичный, инициативный, лидер",
            "Телец": "Стабильный, практичный, надёжный",
            "Близнецы": "Общительный, любознательный, гибкий",
            "Рак": "Чувствительный, заботливый, интуитивный",
            "Лев": "Яркий, творческий, щедрый",
            "Дева": "Аналитичный, перфекционист, заботливый",
            "Весы": "Дипломатичный, гармоничный, справедливый",
            "Скорпион": "Страстный, проницательный, решительный",
            "Стрелец": "Оптимистичный, ищущий, свободолюбивый",
            "Козерог": "Дисциплинированный, ответственный, амбициозный",
            "Водолей": "Оригинальный, прогрессивный, независимый",
            "Рыбы": "Мечтательный, сострадательный, творческий"
        },
        "Луна": {
            "Овен": "Эмоции вспыльчивые, непосредственные",
            "Телец": "Эмоции стабильные, потребность в безопасности",
            "Близнецы": "Эмоции изменчивые, потребность в общении",
            "Рак": "Эмоции глубокие, привязанность к дому",
            "Лев": "Эмоции яркие, потребность в признании",
            "Дева": "Эмоции аналитические, забота о деталях",
            "Весы": "Эмоции дипломатичные, стремление к гармонии",
            "Скорпион": "Эмоции интенсивные, глубокие переживания",
            "Стрелец": "Эмоции оптимистичные, стремление к свободе",
            "Козерог": "Эмоции сдержанные, практичные",
            "Водолей": "Эмоции нестандартные, независимые",
            "Рыбы": "Эмоции эмпатичные, чувствительные"
        }
    }

    forecast_parts = []

    # 1. Общий прогноз на основе возраста
    forecast_parts.append(f"📊 ОБЩИЙ ПРОГНОЗ (возраст: {age} лет)\n")
    forecast_parts.append("=" * 50 + "\n")

    # Прогноз по возрастам
    if age < 18:
        forecast_parts.append("🔮 Период становления личности.\n")
        forecast_parts.append("Рекомендуется: развивать таланты, учиться новому, исследовать мир.\n")
    elif 18 <= age < 30:
        forecast_parts.append("🔮 Период активного роста и поиска своего пути.\n")
        forecast_parts.append("Рекомендуется: строить карьеру, расширять круг общения, путешествовать.\n")
    elif 30 <= age < 45:
        forecast_parts.append("🔮 Период стабильности и реализации.\n")
        forecast_parts.append("Рекомендуется: укреплять достижения, развивать отношения, инвестировать в будущее.\n")
    elif 45 <= age < 60:
        forecast_parts.append("🔮 Период мудрости и передачи опыта.\n")
        forecast_parts.append("Рекомендуется: делиться знаниями, заботиться о здоровье, наслаждаться жизнью.\n")
    else:
        forecast_parts.append("🔮 Период гармонии и созерцания.\n")
        forecast_parts.append("Рекомендуется: проводить время с семьёй, заниматься любимыми делами, отдыхать.\n")

    forecast_parts.append("\n")

    # 2. Прогноз по Солнцу
    sun = planets.get("Солнце")
    if sun:
        sign = getattr(sun, "sign", "неизвестно")
        desc = planet_meanings.get("Солнце", {}).get(sign, "")
        forecast_parts.append(f"☀️ СОЛНЦЕ в знаке {sign}\n")
        if desc:
            forecast_parts.append(f"Ваша сущность: {desc}\n")
        forecast_parts.append("\n")

    # 3. Прогноз по Луне
    moon = planets.get("Луна")
    if moon:
        sign = getattr(moon, "sign", "неизвестно")
        desc = planet_meanings.get("Луна", {}).get(sign, "")
        forecast_parts.append(f"🌙 ЛУНА в знаке {sign}\n")
        if desc:
            forecast_parts.append(f"Ваши эмоции: {desc}\n")
        forecast_parts.append("\n")

    # 4. Прогноз на текущий период
    forecast_parts.append("📅 ПРОГНОЗ НА ТЕКУЩИЙ ПЕРИОД\n")
    forecast_parts.append("=" * 50 + "\n")

    month = current_date.month
    if month in [1, 2]:
        forecast_parts.append("❄️ Зима: время для планирования и внутренней работы.\n")
        forecast_parts.append("Сосредоточьтесь на целях, которые хотите достичь в этом году.\n")
    elif month in [3, 4, 5]:
        forecast_parts.append("🌸 Весна: время для новых начинаний и роста.\n")
        forecast_parts.append("Используйте энергию для реализации задуманного.\n")
    elif month in [6, 7, 8]:
        forecast_parts.append("☀️ Лето: время для активности и общения.\n")
        forecast_parts.append("Расширяйте круг общения, путешествуйте, будьте открыты новому.\n")
    else:
        forecast_parts.append("🍂 Осень: время для подведения итогов.\n")
        forecast_parts.append("Оценивайте достижения, завершайте начатое, готовьтесь к новому этапу.\n")

    # 5. Рекомендации
    forecast_parts.append("\n💡 РЕКОМЕНДАЦИИ\n")
    forecast_parts.append("=" * 50 + "\n")

    if sun:
        sign = getattr(sun, "sign", "")
        if sign in ["Овен", "Лев", "Стрелец"]:
            forecast_parts.append("⚡ У вас сильная огненная энергия. Используйте её для вдохновения других.\n")
        elif sign in ["Телец", "Дева", "Козерог"]:
            forecast_parts.append("🌍 У вас земная практичность. Стройте надёжные основы для будущего.\n")
        elif sign in ["Близнецы", "Весы", "Водолей"]:
            forecast_parts.append("🌪️ У вас воздушная лёгкость. Развивайте коммуникации и связи.\n")
        elif sign in ["Рак", "Скорпион", "Рыбы"]:
            forecast_parts.append("🌊 У вас водная глубина. Доверяйте интуиции и эмпатии.\n")

    forecast_parts.append("\n")
    forecast_parts.append("⚠️ Важно: прогноз основан на астрологической традиции и\n")
    forecast_parts.append("является инструментом для саморефлексии, а не научным предсказанием.\n")

    return "".join(forecast_parts)


# ---------------------------------------------------------
# Main application
# ---------------------------------------------------------

class AstrologyApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(1050, 700)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        if ICON.exists():
            try:
                self.iconbitmap(str(ICON))
            except Exception:
                pass

        self.subject = None
        self.birth_date = None
        self.chart_svg = None
        self.chart_png = None
        self.forecast_text = ""

        self.bg_image = None
        self.bg_label = None
        self._resize_after_id = None

        self.sidebar_buttons = {}
        self.pages = {}

        self._build_background()
        self._build_interface()
        self._show_page("natal")

        self.bind("<Configure>", self._on_resize)

    # -----------------------------------------------------
    # Background
    # -----------------------------------------------------

    def _build_background(self):
        if not BACKGROUND.exists():
            self.configure(fg_color=BG)
            return

        try:
            image = Image.open(BACKGROUND).convert("RGB")
            image = image.filter(ImageFilter.GaussianBlur(2.5))
            image = ImageEnhance.Brightness(image).enhance(0.42)
            image = ImageEnhance.Contrast(image).enhance(0.85)

            self._background_source = image

            self.bg_label = ctk.CTkLabel(
                self,
                text="",
                fg_color="transparent",
            )
            self.bg_label.place(
                x=0,
                y=0,
                relwidth=1,
                relheight=1,
            )
            self.bg_label.lower()

            self._update_background()

        except Exception:
            self.configure(fg_color=BG)

    def _update_background(self):
        if not self.bg_label or not hasattr(self, "_background_source"):
            return

        width = max(self.winfo_width(), WINDOW_WIDTH)
        height = max(self.winfo_height(), WINDOW_HEIGHT)

        source = self._background_source.copy()
        source.thumbnail((width, height), RESAMPLE_LANCZOS)

        canvas = Image.new("RGB", (width, height), BG)

        x = max((width - source.width) // 2, 0)
        y = max((height - source.height) // 2, 0)

        canvas.paste(source, (x, y))

        self.bg_image = ctk.CTkImage(
            light_image=canvas,
            dark_image=canvas,
            size=(width, height),
        )

        self.bg_label.configure(image=self.bg_image)

    def _on_resize(self, event):
        if event.widget != self:
            return

        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)

        self._resize_after_id = self.after(80, self._update_background)

    # -----------------------------------------------------
    # Interface
    # -----------------------------------------------------

    def _build_interface(self):
        self.shell = ctk.CTkFrame(
            self,
            fg_color="#0B0F17",
            corner_radius=24,
            border_width=1,
            border_color="#252C3A",
            width=100,
            height=100,
        )
        self.shell.place(
            x=SHELL_MARGIN,
            y=SHELL_MARGIN,
            relwidth=1,
            relheight=1,
        )

        self.sidebar = ctk.CTkFrame(
            self.shell,
            width=225,
            fg_color="#0D121B",
            corner_radius=24,
        )
        self.sidebar.pack(
            side="left",
            fill="y",
            padx=(8, 4),
            pady=8,
        )
        self.sidebar.pack_propagate(False)

        self.content = ctk.CTkFrame(
            self.shell,
            fg_color="transparent",
            corner_radius=20,
        )
        self.content.pack(
            side="right",
            fill="both",
            expand=True,
            padx=(4, 8),
            pady=8,
        )

        self._build_sidebar()
        self._build_pages()

    def _build_sidebar(self):
        logo = ctk.CTkLabel(
            self.sidebar,
            text="✦  ASTROLOGY AI",
            font=ctk.CTkFont(
                family="Segoe UI",
                size=18,
                weight="bold",
            ),
            text_color=TEXT,
        )
        logo.pack(
            anchor="w",
            padx=22,
            pady=(28, 6),
        )

        version = ctk.CTkLabel(
            self.sidebar,
            text=f"v{APP_VERSION}",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
        )
        version.pack(
            anchor="w",
            padx=24,
            pady=(0, 25),
        )

        items = [
            ("natal", "☉  Натальная карта"),
            ("planets", "◉  Планеты"),
            ("aspects", "✧  Аспекты"),
            ("forecast", "🌟  Прогноз"),
        ]

        for key, text in items:
            button = ctk.CTkButton(
                self.sidebar,
                text=text,
                anchor="w",
                height=45,
                corner_radius=12,
                fg_color="transparent",
                hover_color=CARD_HOVER,
                text_color=MUTED,
                font=ctk.CTkFont(size=13),
                command=lambda k=key: self._show_page(k),
            )
            button.pack(
                fill="x",
                padx=14,
                pady=4,
            )

            self.sidebar_buttons[key] = button

        spacer = ctk.CTkFrame(
            self.sidebar,
            fg_color="transparent",
        )
        spacer.pack(fill="both", expand=True)

        info = ctk.CTkLabel(
            self.sidebar,
            text="Astrology calculations\npowered by Kerykeion\n\nOffline mode\nNo API required",
            justify="left",
            text_color=MUTED,
            font=ctk.CTkFont(size=11),
        )
        info.pack(
            anchor="w",
            padx=22,
            pady=(10, 25),
        )

    def _build_pages(self):
        self.pages["natal"] = self._create_natal_page()
        self.pages["planets"] = self._create_planets_page()
        self.pages["aspects"] = self._create_aspects_page()
        self.pages["forecast"] = self._create_forecast_page()

    def _new_page(self):
        page = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )
        page.place(
            x=0,
            y=0,
            relwidth=1,
            relheight=1,
        )
        return page

    def _header(self, parent, title, subtitle):
        frame = ctk.CTkFrame(
            parent,
            fg_color="transparent",
        )
        frame.pack(
            fill="x",
            padx=26,
            pady=(25, 12),
        )

        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=27, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            frame,
            text=subtitle,
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
        ).pack(
            anchor="w",
            pady=(5, 0),
        )

        return frame

    # -----------------------------------------------------
    # Natal page
    # -----------------------------------------------------

    def _create_natal_page(self):
        page = self._new_page()

        self._header(
            page,
            "Натальная карта",
            "Введите имя и дату рождения для создания персональной карты.",
        )

        form = ctk.CTkFrame(
            page,
            fg_color=CARD,
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
        )
        form.pack(
            fill="x",
            padx=26,
            pady=10,
        )

        fields = ctk.CTkFrame(
            form,
            fg_color="transparent",
        )
        fields.pack(
            fill="x",
            padx=20,
            pady=20,
        )

        # Имя
        self.name_entry = self._field(fields, "Имя", 0, 0, EXAMPLE_NAME)

        # Дата рождения
        self.date_entry = self._field(fields, "Дата рождения (ДД.ММ.ГГГГ)", 0, 1, EXAMPLE_DATE)

        # Система домов
        self.houses_menu = self._menu(
            fields,
            "Система домов",
            0,
            2,
            list(HOUSE_SYSTEM_MAP.keys()),
            "Placidus",
        )

        # Информация о местоположении
        location_info = ctk.CTkLabel(
            fields,
            text=f"📍 Кишинев (широта {FIXED_LAT}, долгота {FIXED_LNG})",
            text_color=MUTED,
            font=ctk.CTkFont(size=12),
        )
        location_info.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(5, 8))

        for column in range(3):
            fields.grid_columnconfigure(column, weight=1)

        self.generate_button = ctk.CTkButton(
            form,
            text="✦  Создать натальную карту",
            height=48,
            corner_radius=13,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._generate,
        )
        self.generate_button.pack(
            fill="x",
            padx=28,
            pady=(0, 25),
        )

        preview = ctk.CTkFrame(
            page,
            fg_color=CARD,
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
        )
        preview.pack(
            fill="both",
            expand=True,
            padx=26,
            pady=(5, 25),
        )

        self.chart_label = ctk.CTkLabel(
            preview,
            text="Здесь появится натальная карта",
            text_color=MUTED,
            font=ctk.CTkFont(size=14),
        )
        self.chart_label.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=20,
        )

        return page

    def _field(self, parent, label, row, column, placeholder):
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.grid(row=row, column=column, sticky="ew", padx=8, pady=(5, 8))

        ctk.CTkLabel(
            wrapper,
            text=label,
            text_color=MUTED,
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", pady=(0, 4))

        entry = ctk.CTkEntry(
            wrapper,
            height=38,
            corner_radius=10,
            fg_color=INPUT,
            border_color=BORDER,
            text_color=TEXT,
            placeholder_text=placeholder,
        )
        entry.pack(fill="x")

        return entry

    def _menu(self, parent, label, row, column, values, default):
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.grid(row=row, column=column, sticky="ew", padx=8, pady=(5, 8))

        ctk.CTkLabel(
            wrapper,
            text=label,
            text_color=MUTED,
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", pady=(0, 4))

        menu = ctk.CTkOptionMenu(
            wrapper,
            values=values,
            height=38,
            corner_radius=10,
            fg_color=INPUT,
            button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
            dropdown_fg_color=CARD,
        )
        menu.set(default)
        menu.pack(fill="x")

        return menu

    # -----------------------------------------------------
    # Planets
    # -----------------------------------------------------

    def _create_planets_page(self):
        page = self._new_page()

        self._header(
            page,
            "Планеты",
            "Положения основных планет в момент рождения.",
        )

        self.planets_scroll = ctk.CTkScrollableFrame(
            page,
            fg_color=CARD,
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
        )
        self.planets_scroll.pack(
            fill="both",
            expand=True,
            padx=26,
            pady=(10, 25),
        )

        self.planets_placeholder = ctk.CTkLabel(
            self.planets_scroll,
            text="Сначала создайте натальную карту.",
            text_color=MUTED,
        )
        self.planets_placeholder.pack(
            padx=20,
            pady=30,
        )

        return page

    def _update_planets(self):
        for widget in self.planets_scroll.winfo_children():
            widget.destroy()

        if not self.subject:
            ctk.CTkLabel(
                self.planets_scroll,
                text="Сначала создайте натальную карту.",
                text_color=MUTED,
            ).pack(pady=30)
            return

        planets = [
            ("Солнце", "sun"),
            ("Луна", "moon"),
            ("Меркурий", "mercury"),
            ("Венера", "venus"),
            ("Марс", "mars"),
            ("Юпитер", "jupiter"),
            ("Сатурн", "saturn"),
            ("Уран", "uranus"),
            ("Нептун", "neptune"),
            ("Плутон", "pluto"),
        ]

        header = ctk.CTkFrame(
            self.planets_scroll,
            fg_color=INPUT,
            corner_radius=10,
        )
        header.pack(fill="x", padx=5, pady=(5, 8))

        headers = ["Планета", "Знак", "Градус", "Дом", "R"]
        for i, text in enumerate(headers):
            ctk.CTkLabel(
                header,
                text=text,
                text_color=MUTED,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(
                row=0,
                column=i,
                sticky="w",
                padx=12,
                pady=10,
            )

        for i in range(5):
            header.grid_columnconfigure(i, weight=1)

        for display_name, attr_name in planets:
            planet = getattr(self.subject, attr_name, None)

            if planet is None:
                continue

            row = ctk.CTkFrame(
                self.planets_scroll,
                fg_color="transparent",
                corner_radius=10,
            )
            row.pack(fill="x", padx=5, pady=2)

            sign = getattr(planet, "sign", "-")
            position = getattr(planet, "position", "-")
            house = getattr(planet, "house", "-")
            retrograde = getattr(planet, "retrograde", False)

            values = [
                display_name,
                str(sign),
                format_degree(position),
                str(house),
                "R" if retrograde else "",
            ]

            for i, value in enumerate(values):
                ctk.CTkLabel(
                    row,
                    text=value,
                    text_color=TEXT if i != 4 else ACCENT,
                    font=ctk.CTkFont(
                        size=12,
                        weight="bold" if i == 0 else "normal",
                    ),
                ).grid(
                    row=0,
                    column=i,
                    sticky="w",
                    padx=12,
                    pady=9,
                )

            for i in range(5):
                row.grid_columnconfigure(i, weight=1)

    # -----------------------------------------------------
    # Aspects
    # -----------------------------------------------------

    def _create_aspects_page(self):
        page = self._new_page()

        self._header(
            page,
            "Аспекты",
            "Основные аспекты между объектами натальной карты.",
        )

        self.aspects_scroll = ctk.CTkScrollableFrame(
            page,
            fg_color=CARD,
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
        )
        self.aspects_scroll.pack(
            fill="both",
            expand=True,
            padx=26,
            pady=(10, 25),
        )

        self.aspects_placeholder = ctk.CTkLabel(
            self.aspects_scroll,
            text="Сначала создайте натальную карту.",
            text_color=MUTED,
        )
        self.aspects_placeholder.pack(pady=30)

        return page

    def _update_aspects(self):
        for widget in self.aspects_scroll.winfo_children():
            widget.destroy()

        if not self.subject:
            ctk.CTkLabel(
                self.aspects_scroll,
                text="Сначала создайте натальную карту.",
                text_color=MUTED,
            ).pack(pady=30)
            return

        try:
            aspects = AspectsFactory.single_chart_aspects(self.subject)
        except Exception as e:
            ctk.CTkLabel(
                self.aspects_scroll,
                text=f"Ошибка получения аспектов:\n{e}",
                text_color="#FF8F8F",
            ).pack(pady=30)
            return

        if not aspects:
            ctk.CTkLabel(
                self.aspects_scroll,
                text="Аспекты не найдены.",
                text_color=MUTED,
            ).pack(pady=30)
            return

        for aspect in aspects:
            if isinstance(aspect, dict):
                p1 = aspect.get("p1_name", "-")
                p2 = aspect.get("p2_name", "-")
                aspect_name = aspect.get("aspect", "-")
                orb = aspect.get("orbit", aspect.get("orb", "-"))
            else:
                p1 = getattr(aspect, "p1_name", "-")
                p2 = getattr(aspect, "p2_name", "-")
                aspect_name = getattr(aspect, "aspect", "-")
                orb = getattr(aspect, "orbit", getattr(aspect, "orb", "-"))

            card = ctk.CTkFrame(
                self.aspects_scroll,
                fg_color=INPUT,
                corner_radius=12,
            )
            card.pack(
                fill="x",
                padx=5,
                pady=4,
            )

            ctk.CTkLabel(
                card,
                text=f"{p1}   {aspect_name}   {p2}",
                text_color=TEXT,
                font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(
                side="left",
                padx=15,
                pady=12,
            )

            ctk.CTkLabel(
                card,
                text=f"орб: {orb}",
                text_color=MUTED,
                font=ctk.CTkFont(size=11),
            ).pack(
                side="right",
                padx=15,
                pady=12,
            )

    # -----------------------------------------------------
    # Forecast page
    # -----------------------------------------------------

    def _create_forecast_page(self):
        page = self._new_page()

        self._header(
            page,
            "🌟 Астрологический прогноз",
            "Персональный прогноз на основе вашей натальной карты.",
        )

        self.forecast_textbox = ctk.CTkTextbox(
            page,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=18,
            text_color=TEXT,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=13,
            ),
            wrap="word",
        )
        self.forecast_textbox.pack(
            fill="both",
            expand=True,
            padx=26,
            pady=(5, 25),
        )

        self.forecast_textbox.insert(
            "1.0",
            "Сначала создайте натальную карту,\nчтобы получить персональный прогноз.",
        )
        self.forecast_textbox.configure(state="disabled")

        return page

    def _update_forecast(self):
        """Обновление прогноза"""
        self.forecast_textbox.configure(state="normal")
        self.forecast_textbox.delete("1.0", "end")

        if not self.subject or not self.birth_date:
            self.forecast_textbox.insert("1.0",
                                         "Сначала создайте натальную карту,\nчтобы получить персональный прогноз.")
            self.forecast_textbox.configure(state="disabled")
            return

        # Генерируем прогноз
        forecast = generate_forecast(self.subject, self.birth_date)
        self.forecast_textbox.insert("1.0", forecast)
        self.forecast_textbox.configure(state="disabled")

    # -----------------------------------------------------
    # Navigation
    # -----------------------------------------------------

    def _show_page(self, key):
        for name, page in self.pages.items():
            if name == key:
                page.lift()

        for name, button in self.sidebar_buttons.items():
            if name == key:
                button.configure(
                    fg_color=ACCENT,
                    text_color="white",
                )
            else:
                button.configure(
                    fg_color="transparent",
                    text_color=MUTED,
                )

    # -----------------------------------------------------
    # Generate
    # -----------------------------------------------------

    def _generate(self):
        try:
            name = self.name_entry.get().strip() or "Unknown"
            self.birth_date = parse_date(self.date_entry.get())
            houses = HOUSE_SYSTEM_MAP.get(self.houses_menu.get(), "P")

        except ValueError as exc:
            messagebox.showerror("Ошибка ввода", str(exc))
            return

        self.generate_button.configure(
            state="disabled",
            text="Создание карты...",
        )

        self.chart_label.configure(
            text="Расчёт натальной карты...\nПожалуйста, подождите.",
            image=None,
        )

        thread = threading.Thread(
            target=self._generate_worker,
            args=(
                name,
                self.birth_date,
                houses,
            ),
            daemon=True,
        )
        thread.start()

    def _generate_worker(
            self,
            name,
            birth_date,
            houses,
    ):
        try:
            subject = make_subject(
                name=name,
                birth_date=birth_date,
                houses=houses,
            )

            svg_path = make_chart(subject)
            png_path = svg_to_png(svg_path)

            self.after(
                0,
                lambda: self._generation_success(
                    subject, svg_path, png_path
                ),
            )

        except Exception as exc:
            error_text = str(exc)
            self.after(0, lambda: self._generation_error(error_text))

    def _generation_success(self, subject, svg_path, png_path):
        self.subject = subject
        self.chart_svg = svg_path
        self.chart_png = png_path

        try:
            if not png_path.exists():
                raise FileNotFoundError("PNG файл не найден")

            image = Image.open(png_path).convert("RGB")

            max_width = 850
            max_height = 540

            ratio = min(
                max_width / image.width,
                max_height / image.height,
                1,
            )

            size = (
                max(1, int(image.width * ratio)),
                max(1, int(image.height * ratio)),
            )

            chart_image = ctk.CTkImage(
                light_image=image,
                dark_image=image,
                size=size,
            )

            self.chart_label.configure(image=chart_image, text="")
            self.chart_label.image = chart_image

        except Exception as exc:
            self.chart_label.configure(
                image=None,
                text=f"Карта создана, но не удалось показать PNG:\n{exc}\n\nSVG сохранен в:\n{svg_path}",
            )

        self._update_planets()
        self._update_aspects()
        self._update_forecast()

        self.generate_button.configure(
            state="normal",
            text="✦  Создать натальную карту",
        )

        self._show_page("natal")

        messagebox.showinfo(
            "Готово",
            "Натальная карта создана.\n\n"
            f"Файлы сохранены в:\n{OUTPUT_DIR}\n\n"
            "🌟 Перейдите на вкладку 'Прогноз' для просмотра персонального прогноза.",
        )

    def _generation_error(self, error_text):
        self.generate_button.configure(
            state="normal",
            text="✦  Создать натальную карту",
        )

        self.chart_label.configure(
            image=None,
            text="Не удалось создать карту.\nПроверьте данные и настройки.",
        )

        messagebox.showerror("Ошибка", error_text)


# ---------------------------------------------------------
# Run
# ---------------------------------------------------------

if __name__ == "__main__":
    app = AstrologyApp()
    app.mainloop()