from exiftool import ExifToolHelper, exceptions  # нужна для изъятия из фалов мета-тегов
import geocoder  # нужна для определения места по GPS координатам
from os import listdir
from os.path import isfile, join
from sys import argv
import time
from progress.bar import IncrementalBar

COUNTER = 0


def count(path):
    global COUNTER
    COUNTER += len(listdir(path))
    for obj in listdir(path):
        if isfile(join(path, obj)):
            pass
        else:
            # true_path = path + '/' + obj
            COUNTER = COUNTER - 1
            count(path + '/' + obj)


error = open('error.log', 'w')
process = open('process.log', 'w')
subject1, subject2 = (), ()
script, input_file = argv

count(input_file)
length = COUNTER
print(length)
bar = IncrementalBar('Countdown', max=length)

'''Перебором проверяется наличие папок или файлов в указанной, в аргументе, директории.
Первое же вхождение в папку запускает рекурсивный цикл'''


# Путь к директории


def find_files(path):
    for obj in listdir(path):
        if isfile(join(path, obj)):
            true_path = path + '/' + obj
            bar.next()
            print(true_path)
            # Здесь запускается основной скрипт, используя 'true_path'
            try:
                with ExifToolHelper() as et:
                    for d in et.get_tags(true_path, tags="GPSPosition"):  # указываем какой тег вытаскивать из файла в
                        # переменную
                        if len(et.get_tags(true_path, tags="GPSPosition")[0]) > 1:
                            v = list(d.items())[1][1]
                            v = v.replace(' ', ', ')
                            request = geocoder.osm(v, method='reverse')
                            write_tags(request, true_path)
                        else:
                            continue
            except exceptions.ExifToolExecuteError:
                continue

        else:
            # Иначе происходит рекурсивное вхождение в другую директорию
            find_files(path + '/' + obj)


def write_tags(request, true_path):
    if request.osm.get('addr:city') is None and request.osm.get('addr:country') is None:
        error.write(f"In file {true_path} not present city and country - skip file")

    elif request.osm.get('addr:city') is not None and request.osm.get('addr:country') is not None:
        subject1 = request.osm['addr:city']
        subject2 = request.osm['addr:country']
        with ExifToolHelper() as et:
            et.set_tags(
                [true_path],
                tags={"TagsList": [subject1, subject2], },
                params=["-duplicates", "-writeCreating", "-overwrite_original_in_place", "-zip", "-scanForXMP"]
            )
        process.write(f"{true_path}; add tags:city; {subject1}; add tags:country; {subject2}\n")

    elif request.osm.get('addr:city') is not None and request.osm.get('addr:country') is None:
        subject = request.osm['addr:city']
        with ExifToolHelper() as et:
            et.set_tags(
                [true_path],
                tags={"TagsList": subject, },
                params=["-duplicates", "-writeCreating", "-overwrite_original_in_place", "-zip", "-scanForXMP"]
            )
        process.write(f"{true_path}; add ONLY tags:city; {subject};\n")

    elif request.osm.get('addr:city') is None and request.osm.get('addr:country') is not None:
        subject = request.osm['addr:country']
        with ExifToolHelper() as et:
            et.set_tags(
                [true_path],
                tags={"TagsList": subject, },
                params=["-duplicates", "-writeCreating", "-overwrite_original_in_place", "-zip", "-scanForXMP"]
            )
        process.write(f"{true_path}; add ONLY tags:country; {subject};\n")

    else:
        error.write(f"{true_path}; Not found or unknown error\n")


def close_file():
    error.close()
    process.close()


# инициация
find_files(input_file)
bar.finish()
close_file()
