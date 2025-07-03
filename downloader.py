import json
import os
import shutil
import requests
import argparse
import re
import yadisk
import html
from datetime import datetime
from urllib.parse import urlparse
from tqdm import tqdm


# Список файлов, которые нужно игнорировать при скачивании
IGNORED_FILES = ["Google Colab.html", "Launch Meeting - Zoom.html"]

# Список доменов, которые пропускаются при скачивании
SKIPPED_DOMAINS = ["youtube.com", "youtu.be", "t.me"]


def get_unique_filename(dest_path):
    """
    Возвращает уникальное имя файла, добавляя (01), (02) и т.д. при необходимости.
    """
    if not os.path.exists(dest_path):
        return dest_path

    base_path, ext = os.path.splitext(dest_path)
    counter = 1

    while counter < 100:  # Ограничение до (99)
        new_path = f"{base_path} ({counter:02d}){ext}"
        if not os.path.exists(new_path):
            return new_path
        counter += 1

    # Если дошли до 100, используем timestamp
    import time

    timestamp = int(time.time())
    return f"{base_path} ({timestamp}){ext}"


def should_ignore_file(filename):
    """
    Проверяет, нужно ли игнорировать файл.
    """
    return filename in IGNORED_FILES


def collect_links_from_messages(messages):
    """
    Собирает все ссылки из сообщений и возвращает их список.
    """
    links = []
    for message in messages:
        text_entities = message.get("text_entities", [])
        for entity in text_entities:
            url = None
            if entity.get("type") == "link":
                url = entity.get("text")
            elif entity.get("type") == "text_link":
                url = entity.get("href")

            if url and url.startswith(("http://", "https://")):
                # Получаем дату сообщения для контекста
                date_str = message.get("date")
                if date_str:
                    date_obj = datetime.fromisoformat(date_str)
                    date_folder = date_obj.strftime("%Y-%m")
                    links.append(f"{date_folder}: {url}")
                else:
                    links.append(url)
    return links


def find_and_process_files(
    json_file_path, target_dir, download_files=False, collect_links=True
):
    """
    Главная функция для обработки JSON-экспорта Telegram.

    Args:
        json_file_path: путь к JSON файлу с экспортом
        target_dir: целевая директория для сохранения
        download_files: флаг - скачивать ли файлы по ссылкам
        collect_links: флаг - собирать ли ссылки в файл
    """

    # Списки для отслеживания результатов скачивания
    skipped_links = []  # Пропущенные ссылки (соцсети и т.д.)
    error_links = []  # Ссылки с ошибками скачивания
    # Определяем директорию, где находится JSON-файл.
    # Это нужно, чтобы правильно находить локальные файлы из экспорта (photos/, files/ и т.д.)
    export_base_dir = os.path.dirname(os.path.abspath(json_file_path))

    # Загружаем данные из JSON-файла
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Ошибка: JSON-файл '{json_file_path}' не найден.")
        return
    except json.JSONDecodeError:
        print(
            f"Ошибка: Не удалось прочитать JSON-файл '{json_file_path}'. Проверьте его формат."
        )
        return

    # Создаем основную папку для загрузок, если ее нет
    os.makedirs(target_dir, exist_ok=True)
    print(f"Файлы будут сохранены в папку: '{os.path.abspath(target_dir)}'")

    messages = data.get("messages", [])
    if not messages:
        print("В JSON-файле не найдено сообщений.")
        return

    # Список ключей, которые могут содержать пути к локальным файлам
    file_keys = [
        "file",
        "photo",
        "video_file",
        "voice_message",
        "audio_file",
        "sticker_emoji",
    ]

    # --- 1. Обработка прикрепленных файлов ---
    print("\n--- Шаг 1: Поиск и копирование прикрепленных файлов ---")
    for message in tqdm(messages, desc="Обработка сообщений (файлы)"):
        # Проверяем, есть ли в сообщении прикрепленный файл
        file_path_relative = None
        for key in file_keys:
            if key in message and isinstance(message[key], str):
                file_path_relative = message[key]
                break

        if file_path_relative:
            # Получаем дату сообщения
            date_str = message.get("date")
            if not date_str:
                continue

            # Форматируем дату в YYYY-MM
            date_obj = datetime.fromisoformat(date_str)
            date_folder = date_obj.strftime("%Y-%m")

            # Собираем полный путь к исходному файлу
            source_path = os.path.join(export_base_dir, file_path_relative)

            # Проверяем, существует ли файл
            if not os.path.exists(source_path):
                # print(f"Предупреждение: Файл не найден по пути: {source_path}")
                continue

            # Создаем папку для сохранения с датой
            dest_dir = os.path.join(target_dir, date_folder)
            os.makedirs(dest_dir, exist_ok=True)

            # Копируем файл с сохранением оригинального имени
            file_name = os.path.basename(file_path_relative)
            dest_path = os.path.join(dest_dir, file_name)

            # Копируем, только если файл еще не существует
            if not os.path.exists(dest_path):
                shutil.copy2(source_path, dest_path)
                # print(f"Скопирован: {file_name} -> {dest_dir}")

    # --- 2. Сбор ссылок из сообщений ---
    if collect_links:
        print("\n--- Шаг 2: Сбор ссылок из сообщений ---")
        links = collect_links_from_messages(messages)

        if links:
            links_file_path = os.path.join(target_dir, "links.txt")
            with open(links_file_path, "w", encoding="utf-8") as f:
                for link in links:
                    f.write(link + "\n")
            print(f"Сохранено {len(links)} ссылок в файл: {links_file_path}")
        else:
            print("Ссылки в сообщениях не найдены.")

    # --- 3. Скачивание файлов по ссылкам (только если флаг download_files установлен) ---
    if download_files:
        print("\n--- Шаг 3: Скачивание файлов по ссылкам ---")
        for message in tqdm(messages, desc="Обработка сообщений (скачивание)"):
            text_entities = message.get("text_entities", [])
            for entity in text_entities:
                url = None
                if entity.get("type") == "link":
                    url = entity.get("text")
                elif entity.get("type") == "text_link":
                    url = entity.get("href")

                if url and url.startswith(("http://", "https://")):
                    # Пропускаем ссылки на соцсети и видеохостинги, которые не являются прямыми файлами
                    if any(domain in url for domain in SKIPPED_DOMAINS):
                        # Получаем дату для контекста
                        date_str = message.get("date")
                        if date_str:
                            date_obj = datetime.fromisoformat(date_str)
                            date_folder = date_obj.strftime("%Y-%m")
                            skipped_links.append(f"{date_folder}: {url}")
                        else:
                            skipped_links.append(url)
                        continue

                    # Получаем дату сообщения
                    date_str = message.get("date")
                    if not date_str:
                        continue

                    # Форматируем дату
                    date_obj = datetime.fromisoformat(date_str)
                    date_folder = date_obj.strftime("%Y-%m")

                    # Создаем папку для сохранения
                    dest_dir = os.path.join(target_dir, date_folder)
                    os.makedirs(dest_dir, exist_ok=True)

                    # Определяем имя файла
                    file_name = get_filename_from_url_improved(url, message["id"])

                    # Проверяем, нужно ли игнорировать этот файл
                    if should_ignore_file(file_name):
                        print(f"Игнорируем файл: {file_name}")
                        continue

                    # Создаем уникальное имя файла, если такой уже существует
                    initial_dest_path = os.path.join(dest_dir, file_name)
                    dest_path = get_unique_filename(initial_dest_path)

                    print(f"\nНайдена ссылка: {url}")
                    print(f"Скачиваю в: {dest_path}")

                    success = False
                    final_path = dest_path

                    # Специальная обработка для Яндекс.Диска
                    if is_yandex_disk_link(url):
                        success, final_path = download_yandex_disk_file_with_progress(
                            url, dest_path
                        )
                    else:
                        # Обычное скачивание для других ссылок
                        success, header_filename = download_with_progress(
                            url, dest_path
                        )

                        # Если получили имя файла из заголовков, переименовываем
                        if success and header_filename:
                            # Проверяем, нужно ли игнорировать файл по новому имени
                            if should_ignore_file(header_filename):
                                print(f"Игнорируем файл: {header_filename}")
                                if os.path.exists(dest_path):
                                    os.remove(dest_path)
                                continue

                            new_dest_path = os.path.join(dest_dir, header_filename)
                            new_dest_path = get_unique_filename(new_dest_path)
                            if dest_path != new_dest_path:
                                os.rename(dest_path, new_dest_path)
                                final_path = new_dest_path
                                print(f"Переименован в: {new_dest_path}")

                    if success:
                        try:
                            file_size = os.path.getsize(final_path)
                            file_size_mb = file_size / (1024 * 1024)
                            final_file_name = os.path.basename(final_path)
                            print(
                                f"✓ Скачан: {final_file_name} ({file_size_mb:.2f} МБ)"
                            )
                        except:
                            final_file_name = os.path.basename(final_path)
                            print(f"✓ Скачан: {final_file_name}")
                    else:
                        print(f"✗ Ошибка скачивания: {url}")
                        # Добавляем ссылку с ошибкой в список
                        error_links.append(f"{date_folder}: {url}")

    print("\nГотово! Все найденные файлы обработаны.")

    # --- 4. Сохранение списков пропущенных и неудачных ссылок ---
    if download_files:
        if skipped_links:
            skipped_file_path = os.path.join(target_dir, "skipped.txt")
            with open(skipped_file_path, "w", encoding="utf-8") as f:
                for link in skipped_links:
                    f.write(link + "\n")
            print(
                f"Сохранено {len(skipped_links)} пропущенных ссылок в файл: {skipped_file_path}"
            )

        if error_links:
            error_file_path = os.path.join(target_dir, "errors.txt")
            with open(error_file_path, "w", encoding="utf-8") as f:
                for link in error_links:
                    f.write(link + "\n")
            print(
                f"Сохранено {len(error_links)} ссылок с ошибками в файл: {error_file_path}"
            )

        if not skipped_links and not error_links:
            print("Все ссылки успешно обработаны - нет пропущенных или ошибок!")


def download_with_progress(url, dest_path, chunk_size=8192):
    """
    Скачивает файл с отображением прогресса.
    """
    try:
        response = requests.get(url, stream=True, timeout=10, allow_redirects=True)
        response.raise_for_status()

        # Получаем размер файла из заголовков
        total_size = int(response.headers.get("content-length", 0))

        # Пытаемся получить имя файла из заголовков
        content_disposition = response.headers.get("content-disposition", "")
        filename_from_header = None
        if content_disposition:
            filename_match = re.findall(
                r'filename[*]?=["\']?([^"\';\r\n]*)', content_disposition
            )
            if filename_match:
                filename_from_header = sanitize_filename(filename_match[0])

        size_str = format_file_size(total_size) if total_size > 0 else "неизвестен"
        print(f"Скачиваю: размер {size_str}")

        with open(dest_path, "wb") as f:
            if total_size > 0:
                # Показываем прогресс-бар для файлов с известным размером
                with tqdm(
                    total=total_size, unit="B", unit_scale=True, desc="Скачивание"
                ) as pbar:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            pbar.update(len(chunk))
            else:
                # Простое скачивание без прогресс-бара
                downloaded = 0
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

        return True, filename_from_header

    except Exception as e:
        print(f"Ошибка скачивания {url}: {e}")
        return False, None


def is_likely_html_page(url):
    """
    Определяет, является ли URL HTML-страницей (а не прямой ссылкой на файл).
    """
    parsed_url = urlparse(url)
    path = parsed_url.path.lower()

    # Если нет расширения файла или есть характерные для веб-страниц пути
    if (
        not path
        or path.endswith("/")
        or path.endswith(".html")
        or path.endswith(".htm")
        or "/edit" in path
        or "/view" in path
        or "sharing" in url.lower()
        or "docs.google.com" in url.lower()
        or "trafory.yonote.ru" in url.lower()
        or "zoom.us" in url.lower()
        or "github.com" in url.lower()
        or "habr.com" in url.lower()
        or "youtube.com" in url.lower()
        or "youtu.be" in url.lower()
        or "colab.research.google.com" in url.lower()
    ):
        return True

    # Если есть расширение файла, но это не веб-страница
    file_extensions = [
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".zip",
        ".rar",
        ".mp4",
        ".avi",
        ".mkv",
        ".mp3",
        ".wav",
        ".jpg",
        ".png",
        ".gif",
    ]
    if any(path.endswith(ext) for ext in file_extensions):
        return False

    return True


def get_filename_from_url_improved(url, message_id):
    """
    Улучшенная функция для получения имени файла с поддержкой HTML title.
    """
    parsed_url = urlparse(url)
    file_name = os.path.basename(parsed_url.path)

    # Специальная обработка для Яндекс.Диска
    if is_yandex_disk_link(url):
        # Получаем правильное имя файла с Яндекс.Диска
        real_name, _ = get_yandex_disk_file_info(url)
        if real_name:
            return sanitize_filename(real_name)

        # Если не удалось получить имя, используем ID из ссылки
        if "/i/" in url:
            file_id = url.split("/i/")[-1].split("?")[0]
            file_name = f"yandex_disk_{file_id}"
        elif "/d/" in url:
            file_id = url.split("/d/")[-1].split("?")[0]
            file_name = f"yandex_folder_{file_id}"

    # Для HTML страниц всегда пытаемся получить title
    elif is_likely_html_page(url):
        title = get_html_title(url)
        if title:
            file_name = f"{title}.html"
        else:
            # Используем домен и путь для создания понятного имени
            domain = parsed_url.netloc.replace("www.", "")
            path_part = parsed_url.path.strip("/").replace("/", "_")
            if path_part:
                file_name = f"{domain}_{path_part}.html"
            else:
                file_name = f"{domain}.html"

    if not file_name:  # Если имя файла не удалось извлечь
        file_name = f"downloaded_file_{message_id}"

    return sanitize_filename(file_name)


def sanitize_filename(filename):
    """
    Очищает имя файла от недопустимых символов и HTML entities.
    """
    if not filename:
        return filename

    # Декодируем HTML entities (например &#x2F; → /)
    filename = html.unescape(filename)

    # Заменяем недопустимые символы для файловой системы
    # Windows: < > : " / \ | ? *
    # Linux/macOS: /
    invalid_chars = r'[<>:"/\\|?*]'
    filename = re.sub(invalid_chars, "_", filename)

    # Убираем переводы строк и лишние пробелы
    filename = re.sub(r"\s+", " ", filename.strip())

    # Ограничиваем длину (оставляем место для расширения)
    max_length = 200
    if len(filename) > max_length:
        filename = filename[:max_length].rstrip()

    return filename


def get_html_title(url, timeout=10):
    """
    Получает title HTML страницы с правильной обработкой HTML entities.
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        # Ищем title в HTML
        content = response.text
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", content, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            # Используем функцию sanitize_filename для очистки
            title = sanitize_filename(title)
            return title
    except Exception:
        pass
    return None


def get_yandex_disk_file_info(url):
    """
    Получает информацию о файле с Яндекс.Диска (имя, размер).
    """
    try:
        client = yadisk.Client()
        # Получаем метаданные публичного ресурса
        meta = client.get_public_meta(url)

        file_name = meta.name if hasattr(meta, "name") and meta.name else None
        file_size = meta.size if hasattr(meta, "size") and meta.size else None

        return file_name, file_size
    except Exception as e:
        print(f"Не удалось получить информацию о файле с Яндекс.Диска: {e}")
        return None, None


def format_file_size(size_bytes):
    """
    Форматирует размер файла в читаемый вид.
    """
    if size_bytes is None:
        return "неизвестен"

    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} ТБ"


def download_yandex_disk_file_with_progress(url, dest_path):
    """
    Скачивает файл с Яндекс.Диска с отображением прогресса.
    """
    try:
        client = yadisk.Client()

        # Получаем информацию о файле
        file_name, file_size = get_yandex_disk_file_info(url)

        if file_name:
            # Обновляем путь назначения с правильным именем файла
            dest_dir = os.path.dirname(dest_path)
            sanitized_name = sanitize_filename(file_name)
            initial_path = os.path.join(dest_dir, sanitized_name)
            final_dest_path = get_unique_filename(initial_path)
        else:
            final_dest_path = dest_path

        size_str = format_file_size(file_size)
        print(f"Скачиваю с Яндекс.Диска: {file_name or 'файл'} ({size_str})")

        # Удаляем файл, если он уже существует
        if os.path.exists(final_dest_path):
            os.remove(final_dest_path)

        # Скачиваем файл напрямую (yadisk API не поддерживает chunked download для публичных файлов)
        print("Скачивание... (может занять некоторое время)")
        client.download_public(url, final_dest_path)
        print("✓ Скачивание завершено")

        return True, final_dest_path

    except Exception as e:
        print(f"Ошибка скачивания с Яндекс.Диска {url}: {e}")
        return False, dest_path


def is_yandex_disk_link(url):
    """
    Проверяет, является ли URL ссылкой на Яндекс.Диск.
    """
    return "disk.yandex.ru" in url


def download_yandex_disk_file(url, dest_path):
    """
    Устаревшая функция - используется download_yandex_disk_file_with_progress.
    Оставлена для совместимости.
    """
    return download_yandex_disk_file_with_progress(url, dest_path)[0]


def main():
    parser = argparse.ArgumentParser(
        description="Telegram Chat Export Downloader - скачивает файлы и собирает ссылки из экспорта Telegram"
    )

    # Аргументы командной строки
    parser.add_argument(
        "--download",
        action="store_true",
        help="Скачивать файлы по ссылкам из сообщений",
    )

    parser.add_argument(
        "--links",
        action="store_true",
        default=True,
        help="Собирать ссылки и сохранять в файл links.txt (включено по умолчанию)",
    )

    parser.add_argument("--no-links", action="store_true", help="Отключить сбор ссылок")

    parser.add_argument("--source_file", type=str, help="Путь к JSON файлу с экспортом")

    parser.add_argument(
        "--source_dir", type=str, help="Директория, где искать result.json"
    )

    parser.add_argument(
        "--target_dir",
        type=str,
        default="results",
        help="Целевая директория для сохранения файлов (по умолчанию: results)",
    )

    args = parser.parse_args()

    # Определяем путь к JSON файлу
    json_file_path = None

    if args.source_file:
        json_file_path = args.source_file
    elif args.source_dir:
        json_file_path = os.path.join(args.source_dir, "result.json")
    else:
        # По умолчанию ищем в текущей директории
        default_paths = ["source/ChatExport_2025-06-08/result.json", "result.json"]
        for path in default_paths:
            if os.path.exists(path):
                json_file_path = path
                break

    # Проверяем, что файл найден
    if not json_file_path or not os.path.exists(json_file_path):
        print("Ошибка: JSON файл с экспортом не найден!")
        print("Используйте:")
        print("  --source_file путь/к/файлу.json")
        print("  или --source_dir путь/к/директории/")
        print("  или поместите result.json в текущую директорию")
        return

    # Определяем флаги
    collect_links = args.links and not args.no_links
    download_files = args.download

    print(f"Исходный файл: {json_file_path}")
    print(f"Целевая директория: {args.target_dir}")
    print(f"Сбор ссылок: {'включен' if collect_links else 'отключен'}")
    print(f"Скачивание файлов: {'включено' if download_files else 'отключено'}")

    # Запускаем обработку
    find_and_process_files(
        json_file_path,
        args.target_dir,
        download_files=download_files,
        collect_links=collect_links,
    )


if __name__ == "__main__":
    main()
