import os
import time
from pathlib import Path
from progress.bar import IncrementalBar

from exiftool import ExifToolHelper, exceptions
import geocoder

# Лимит запросов к OSM, чтобы не получить бан
GEO_DELAY = 1.1  # секунды между запросами

def get_all_files(root_path: Path):
    """Возвращает список всех файлов (рекурсивно) в директории."""
    files = []
    for dirpath, _, filenames in os.walk(root_path):
        for name in filenames:
            files.append(Path(dirpath) / name)
    return files

def reverse_geocode(lat_lon_str: str):
    """Безопасный геокодинг с задержкой и обработкой ошибок."""
    time.sleep(GEO_DELAY)
    try:
        g = geocoder.osm(lat_lon_str, method='reverse')
        if not g.ok:
            return None
        return g.osm
    except Exception:
        return None

def write_tags(request, file_path: Path, process_log, error_log):
    city = request.get('addr:city')
    country = request.get('addr:country')

    if city is None and country is None:
        error_log.write(f"{file_path}; not found city and country - skip\n")
        return

    tags_to_set = {}
    log_parts = []

    if city:
        tags_to_set["City"] = city
        log_parts.append(f"city; {city}")
    if country:
        tags_to_set["Country"] = country
        log_parts.append(f"country; {country}")

    # Используем Keywords, если хочешь именно «теги» в смысле ключевых слов
    # tags_to_set["Keywords"] = [city, country] если нужно списком

    try:
        with ExifToolHelper() as et:
            et.set_tags(
                [str(file_path)],
                tags=tags_to_set,
                params=[
                    "-duplicates",
                    "-overwrite_original_in_place",
                    "-scanForXMP"
                ]
            )
        process_log.write(f"{file_path}; add tags: {'; '.join(log_parts)}\n")
    except exceptions.ExifToolExecuteError as e:
        error_log.write(f"{file_path}; exiftool error: {e}\n")

def main():
    import sys
    if len(sys.argv) != 2:
        print("Usage: python script.py <directory>")
        sys.exit(1)

    root_dir = Path(sys.argv[1]).resolve()
    if not root_dir.is_dir():
        print(f"Error: {root_dir} is not a directory")
        sys.exit(1)

    all_files = get_all_files(root_dir)
    total = len(all_files)
    if total == 0:
        print("No files found.")
        return

    print(f"Found {total} files to process.")
    bar = IncrementalBar('Processing', max=total)

    with open('process.log', 'w', encoding='utf-8') as process_log, \
         open('error.log', 'w', encoding='utf-8') as error_log:

        with ExifToolHelper() as et:  # один экземпляр exiftool на весь скрипт
            for file_path in all_files:
                try:
                    gps_data = et.get_tags(str(file_path), tags=["GPSPosition"])
                    if not gps_data:
                        bar.next()
                        continue

                    # get_tags возвращает список словарей: [{filename: {...}}]
                    file_tags = gps_data[0].get(str(file_path)) or {}
                    gps = file_tags.get("GPSPosition")

                    if gps is None or len(str(gps).split(",")) < 2:
                        bar.next()
                        continue

                    # Преобразуем GPSPosition в формат, понятный geocoder (lat, lon)
                    # exiftool обычно возвращает строку вида "48.8566, 2.3522" или похожую
                    lat_lon_str = str(gps).replace(" ", ", ")

                    request = reverse_geocode(lat_lon_str)
                    if request:
                        write_tags(request, file_path, process_log, error_log)

                except exceptions.ExifToolExecuteError as e:
                    error_log.write(f"{file_path}; exiftool execute error: {e}\n")
                except Exception as e:
                    error_log.write(f"{file_path}; unexpected error: {e}\n")

                bar.next()

    bar.finish()
    print("Done.")

if __name__ == "__main__":
    main()
