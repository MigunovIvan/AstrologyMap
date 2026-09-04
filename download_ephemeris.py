import os
import urllib.request
from pathlib import Path


def download_ephemeris():
    """Скачивает файл эфемерид с официального сайта NASA"""
    app_dir = Path(__file__).parent

    # Ссылки на файлы эфемерид (DE440 - современные эфемериды)
    url = "https://ssd.jpl.nasa.gov/ftp/eph/planets/Linux/de440/de440.les"
    # Альтернативный URL, если первый не работает
    url_alt = "https://naif.jpl.nasa.gov/pub/naif/toolkit//PC_Linux_64_GCC_8.3.1/packages/spice_ephemerides/de440.bsp"

    output_file = app_dir / "de440.leb"

    print(f"Скачивание эфемерид... Это может занять несколько минут.")
    print(f"Файл будет сохранен в: {output_file}")

    try:
        # Пробуем скачать файл
        urllib.request.urlretrieve(url, output_file)
        if output_file.exists() and output_file.stat().st_size > 1000000:
            print(f"✓ Файл эфемерид успешно скачан: {output_file}")
            return str(output_file)
        else:
            raise Exception("Файл слишком маленький или поврежден")
    except Exception as e:
        print(f"Ошибка загрузки с первого URL: {e}")
        try:
            # Пробуем альтернативный URL
            urllib.request.urlretrieve(url_alt, output_file)
            if output_file.exists() and output_file.stat().st_size > 1000000:
                print(f"✓ Файл эфемерид успешно скачан: {output_file}")
                return str(output_file)
            else:
                raise Exception("Файл слишком маленький или поврежден")
        except Exception as e2:
            print(f"Ошибка загрузки со второго URL: {e2}")
            return None


if __name__ == "__main__":
    result = download_ephemeris()
    if result:
        print(f"Эфемериды готовы к использованию: {result}")
    else:
        print("Не удалось скачать эфемериды. Попробуйте скачать вручную:")
        print("1. Перейдите на https://ssd.jpl.nasa.gov/ftp/eph/planets/Linux/de440/")
        print("2. Скачайте файл de440.les")
        print("3. Переименуйте его в de440.leb")
        print(f"4. Поместите в папку: {Path(__file__).parent}")