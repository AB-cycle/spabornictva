from flask import request, session, jsonify
from flask_login import login_required, current_user
from lxml import etree
from datetime import datetime, timedelta
from geopy.distance import geodesic

from kod import app, db
from kod.models import Track, User

import logging

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        print('No file part in request')
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    
    if file.filename == '':
        print('No selected file')
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        try:
            # Читаем содержимое файла
            file_content = file.read()
            print('File content read successfully')

            # Парсинг GPX с использованием lxml
            root = etree.fromstring(file_content)

            # Определение пространства имен из файла
            namespace = root.nsmap.get(None, '')
            print(f'Namespace detected: {namespace}')

            # Извлечение информации о треках
            tracks = []
            elevation_gain = 0.0
            previous_elevation = None

            for trk in root.xpath('//ns:trk', namespaces={'ns': namespace}):
                name = trk.find('ns:name', namespaces={'ns': namespace}).text
                print(f'Extracting track: {name}')

                for trkseg in trk.xpath('ns:trkseg', namespaces={'ns': namespace}):
                    for trkpt in trkseg.xpath('ns:trkpt', namespaces={'ns': namespace}):
                        lat = trkpt.get('lat')
                        lon = trkpt.get('lon')
                        ele = trkpt.find('ns:ele', namespaces={'ns': namespace}).text
                        time = trkpt.find('ns:time', namespaces={'ns': namespace}).text

                        # Проверяем и добавляем данные в трек
                        if time:
                            tracks.append({
                                'name': name,
                                'lat': lat,
                                'lon': lon,
                                'ele': ele,
                                'time': time
                            })

                            # Если есть значение высоты, вычисляем набор высоты
                            if ele:
                                try:
                                    ele = float(ele)

                                    if previous_elevation is not None and ele > previous_elevation:
                                        elevation_gain += (ele - previous_elevation)

                                    previous_elevation = ele
                                except ValueError:
                                    print(f'Invalid elevation value: {ele}')
                                    continue  # Игнорируем некорректные значения
                        else:
                            print('Trackpoint without time found; skipping.')

            # Логирование извлеченных треков
            print(f'Total tracks extracted: {len(tracks)}')

            if not tracks:
                print('No tracks extracted from GPX file.')
                return jsonify({'error': 'Не атрымалася загрузіць трэк.'}), 400

            # Проверка на существование трека с таким же именем
            existing_track = Track.query.filter_by(filename=file.filename).first()
            if existing_track:
                print(f'File with the same name already exists: {file.filename}')
                return jsonify({'error': 'Такі трэк ўжо быў запампаваны! Выберыце іншы!.'}), 400

            # Получаем user_id из текущего пользователя
            user_id = current_user.id  # Берем ID текущего пользователя через Flask-Login

            # Логика для записи в базу данных
            duration_in_seconds = calculate_duration(tracks)  # Общее время
            net_duration = calculate_net_duration(tracks)  # Чистое время
            formatted_duration = format_duration(duration_in_seconds)
            formatted_net_duration = format_duration(net_duration.total_seconds())

            new_track = Track(
                user_id=user_id,  # Записываем user_id
                filename=file.filename,
                name_track=file.filename,
                distance=round(calculate_distance(tracks), 2),
                duration=formatted_duration,
                net_duration=formatted_net_duration,
                upload_time=datetime.now(),
                record_time=parse_time(tracks[0]['time']) if tracks[0]['time'] else None,
                height=round(elevation_gain)
            )

            # Сохранение трека в базу данных
            db.session.add(new_track)
            db.session.commit()
            print('Track saved to database successfully')

            return jsonify({
                'success': 'Трэк паспяхова запампаваны!',
                'tracks': tracks,
                'filename': file.filename,
                'total_distance': round(calculate_distance(tracks), 2),
                'duration': formatted_duration,
                'net_duration': formatted_net_duration,
                'height': round(elevation_gain)
            }), 200

        except etree.XMLSyntaxError as e:
            print(f'XML parsing error: {str(e)}')
            return jsonify({'error': f'Ошибка парсинга GPX: {str(e)}'}), 400
        except Exception as e:
            print(f'Unexpected error: {str(e)}')
            return jsonify({'error': f'Произошла ошибка: {str(e)}'}), 500

    return jsonify({'error': 'Неверный формат файла'}), 400




def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'gpx'


def calculate_distance(tracks):
    total_distance = 0.0
    previous_point = None

    for track in tracks:
        lat = float(track['lat'])
        lon = float(track['lon'])
        current_point = (lat, lon)

        if previous_point:
            total_distance += geodesic(previous_point, current_point).kilometers

        previous_point = current_point

    return total_distance


def calculate_duration(tracks):
    start_time = parse_time(tracks[0]['time'])
    end_time = parse_time(tracks[-1]['time'])
    return (end_time - start_time).total_seconds()


def calculate_net_duration(tracks):
    total_net_duration = 0
    pause_threshold = 5  # порог паузы в секундах

    # Сортируем трекпункты по времени
    sorted_tracks = sorted(tracks, key=lambda x: parse_time(x['time']))

    for i in range(1, len(sorted_tracks)):
        current_time = parse_time(sorted_tracks[i]['time'])
        previous_time = parse_time(sorted_tracks[i - 1]['time'])

        # Рассчитываем разницу во времени между текущим и предыдущим трекпунктом
        time_diff = (current_time - previous_time).total_seconds()

        # Если разница меньше порога паузы, добавляем к чистому времени
        if time_diff <= pause_threshold:
            total_net_duration += time_diff

    return timedelta(seconds=total_net_duration)


def parse_time(time_string):
    """Попробуйте разобрать строку времени в нескольких форматах."""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(time_string, fmt)
        except ValueError:
            continue
    raise ValueError(f"Не удалось разобрать время: {time_string}")


def format_duration(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"



def calculate_elevation_gain(tracks):
    elevation_gain = 0.0
    previous_elevation = None

    for track in tracks:
        try:
            ele = float(track['ele'])  # Преобразуем высоту в float

            if previous_elevation is not None:
                if ele > previous_elevation:
                    # Если текущая высота выше предыдущей, добавляем разницу к набору высоты
                    gain = ele - previous_elevation
                    elevation_gain += gain
                    logging.debug(f'Elevation gain: {gain} (current: {ele}, previous: {previous_elevation})')

            # Обновляем предыдущую высоту для следующей итерации
            previous_elevation = ele

        except (ValueError, TypeError) as e:
            logging.warning(f'Invalid elevation value encountered: {track["ele"]}. Error: {e}')
            continue  # Пропускаем некорректные значения

    return elevation_gain

