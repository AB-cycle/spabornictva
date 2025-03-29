import os
import requests
from flask import redirect, request, session, url_for, render_template, flash
from datetime import datetime, timedelta
from flask_login import login_required, current_user
from kod import app, db
from kod.models import Track, Strava, User
import logging

# Ваши данные клиента, полученные при регистрации приложения в Strava
CLIENT_ID = '140178'  # Замените на ваш Client ID
CLIENT_SECRET = '7b3664912d6f52cf215e020f4267a97fc521ea88'  # Замените на ваш Client Secret
REDIRECT_URI = 'http://127.0.0.1:5000/callback'  # Замените на ваш Redirect URI

# Secret ключ для сессий Flask
app.secret_key = os.urandom(24)

# URL для аутентификации в Strava
AUTH_URL = f'https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=read,read_all,activity:read'

# URL для обмена кода на токен
TOKEN_URL = 'https://www.strava.com/oauth/token'


@app.route('/')
def index():
    """Стартовая страница. Переход на страницу авторизации Strava."""
    return redirect(AUTH_URL)


@app.route('/callback')
@login_required
def callback():
    code = request.args.get('code')
    if not code:
        return 'Ошибка: отсутствует код авторизации Strava.', 400

    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    }

    response = requests.post(TOKEN_URL, data=data)
    if response.status_code == 200:
        token_data = response.json()
        print(f"Token Data: {token_data}")
        access_token = token_data['access_token']
        refresh_token = token_data['refresh_token']
        expires_at = token_data.get('expires_at')

        save_strava_tokens(current_user.id, access_token, refresh_token, expires_at)

        headers = {'Authorization': f'Bearer {access_token}'}
        strava_profile_url = 'https://www.strava.com/api/v3/athlete'
        profile_response = requests.get(strava_profile_url, headers=headers)
        if profile_response.status_code == 200:
            profile_data = profile_response.json()
            strava_url = f"https://www.strava.com/athletes/{profile_data['id']}"
            update_strava_url_in_db(current_user.id, strava_url)
        else:
            print(f"Profile Fetch Error: {profile_response.status_code} - {profile_response.text}")

        return redirect(url_for('profile'))
    else:
        print(f"Token Exchange Error: {response.status_code} - {response.text}")
        return f'Ошибка при обмене кода на токен. Статус: {response.status_code}', 500



@app.route('/strava_profile')
@login_required
def strava_profile():
    """Страница профиля пользователя."""
    strava_data = Strava.query.filter_by(user_id=current_user.id).first()

    if not strava_data:
        logging.debug(f"Пользователь {current_user.id} не имеет данных Strava.")
        flash("Вы не синхронизированы с Strava. Пожалуйста, выполните синхронизацию.", "warning")
        return redirect(url_for('sync'))  # Перенаправление на страницу синхронизации

    access_token = session.get('access_token')
    if not access_token:
        logging.debug(f"У пользователя {current_user.id} нет токена доступа Strava.")
        return redirect(url_for('strava_sync'))

    strava_profile_data = session.get('strava_profile_data')
    activities = session.get('strava_activities')

    if not strava_profile_data or not activities:
        if token_is_expired():
            refresh_access_token()

        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            strava_profile_url = 'https://www.strava.com/api/v3/athlete'
            response = requests.get(strava_profile_url, headers=headers)
            response.raise_for_status()
            strava_profile_data = response.json()
            session['strava_profile_data'] = strava_profile_data

            activities = get_activities(access_token)
            session['strava_activities'] = activities

            strava_url = f"https://www.strava.com/athletes/{strava_profile_data['id']}"
            update_strava_url_in_db(current_user.id, strava_url)

        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка при получении данных с Strava для пользователя {current_user.id}: {e}")
            flash("Ошибка при загрузке данных с Strava.", "danger")

    return render_template(
        'profile.html',
        strava_profile_data=strava_profile_data,
        activities=activities,
        strava_profile_url=strava_data.strava_url if strava_data else None
    )


def update_strava_url_in_db(user_id, strava_url):
    """Обновляет ссылку на профиль Strava в базе данных или добавляет новую запись."""
    try:
        strava_data = Strava.query.filter_by(user_id=user_id).first()
        if strava_data:
            if not strava_data.strava_url:  # Проверяем, есть ли уже ссылка
                strava_data.strava_url = strava_url
                db.session.commit()
                logging.info(f"Strava URL записан для пользователя с ID {user_id}: {strava_url}.")
            else:
                pass
        else:
            # Если записи нет, создаем новую
            strava_data = Strava(user_id=user_id, strava_url=strava_url)
            db.session.add(strava_data)
            db.session.commit()
            logging.info(f"Strava URL добавлен для нового пользователя с ID {user_id}: {strava_url}.")
    except Exception as e:
        # Обработка ошибок при записи в базу данных
        db.session.rollback()
        logging.info(f"Ошибка при обновлении Strava URL для пользователя с ID {user_id}: {e}")


def refresh_access_token(user_id):
    """Обновление токена с использованием refresh_token."""
    strava_data = Strava.query.filter_by(user_id=user_id).first()
    if not strava_data or not strava_data.refresh_token:
        logging.error(f"Не удалось найти refresh_token для пользователя {user_id}.")
        return None

    refresh_data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': strava_data.refresh_token,
        'grant_type': 'refresh_token'
    }

    response = requests.post(TOKEN_URL, data=refresh_data)
    if response.status_code == 200:
        token_data = response.json()
        strava_data.access_token = token_data['access_token']
        strava_data.refresh_token = token_data['refresh_token']
        strava_data.token_expires_at = datetime.utcfromtimestamp(token_data['expires_at'])
        db.session.commit()
        logging.info(f"Токен обновлён для пользователя {user_id}.")
        return strava_data.access_token
    else:
        logging.error(f"Ошибка при обновлении токена для пользователя {user_id}.")
        return None





def token_is_expired(user_id):
    """Проверка, истёк ли токен пользователя."""
    strava_data = Strava.query.filter_by(user_id=user_id).first()
    if strava_data and strava_data.token_expires_at:
        current_time = datetime.utcnow()
        return strava_data.token_expires_at < current_time
    return True


@app.route('/activities')
def activities():
    """Получение активностей пользователя через API Strava и отображение GPX ссылок."""
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('index'))  # Перенаправление на авторизацию, если нет токена

    if token_is_expired():
        refresh_access_token(current_user.id)  # Передаем user_id

    headers = {'Authorization': f'Bearer {access_token}'}
    activities_url = 'https://www.strava.com/api/v3/athlete/activities'
    response = requests.get(activities_url, headers=headers)

    if response.status_code == 200:
        activities_data = response.json()
        activities_list = ''
        for activity in activities_data:
            activities_list += f"{activity['name']} - {activity['distance'] / 1000} км<br>"
            activities_list += f"<a href='{url_for('download_gpx', activity_id=activity['id'])}'>Скачать GPX</a><br><br>"
        return activities_list
    else:
        return f'Ошибка при получении данных активностей. Статус: {response.status_code}', 500


@app.route('/strava_sync')
@login_required
def sync():
    """Страница с формой для синхронизации со Strava."""
    return render_template('strava_sync.html', auth_url=AUTH_URL)


def get_activities(access_token):
    """Получение ВСЕХ активностей пользователя за последние 60 дней через API Strava с пагинацией."""
    activities_url = 'https://www.strava.com/api/v3/athlete/activities'
    headers = {'Authorization': f'Bearer {access_token}'}
    cutoff_date = datetime.now() - timedelta(days=60)
    recent_activities = []
    page = 1
    per_page = 200  # Максимальное количество активностей на странице

    logging.info("Начало получения активностей с пагинацией...")

    while True:
        params = {'page': page, 'per_page': per_page}
        response = requests.get(activities_url, headers=headers, params=params)

        # Прерываем цикл при ошибке запроса
        if response.status_code != 200:
            logging.error(f"Ошибка запроса. Страница: {page}, Статус: {response.status_code}")
            break

        activities_data = response.json()
        
        # Прерываем цикл, если данных больше нет
        if not activities_data:
            logging.info(f"Страница {page} пустая. Прекращаем пагинацию.")
            break

        logging.info(f"Обработка страницы {page} ({len(activities_data)} активностей)...")

        # Флаг для остановки обработки при обнаружении старой активности
        stop_processing = False
        
        for activity in activities_data:
            activity_date = datetime.strptime(activity['start_date'], '%Y-%m-%dT%H:%M:%SZ')
            
            if activity_date >= cutoff_date:
                recent_activities.append(activity)
            else:
                logging.info(f"Найдена активность от {activity_date}. Прекращаем обработку.")
                stop_processing = True
                break  # Выход из цикла по активностям

        if stop_processing:
            break  # Выход из основного цикла пагинации

        page += 1

    logging.info(f"Всего обработано активностей: {len(recent_activities)}")
    return recent_activities if recent_activities else None


def get_user_by_id(user_id):
    """Получает пользователя по его ID."""
    # Получаем пользователя по user_id
    user = User.query.filter_by(id=user_id).first()
    if not user:
        logging.error(f"Пользователь с ID {user_id} не найден.")
        return None  # Прерываем выполнение, если пользователь не найден

    return user  # Возвращаем пользователя

def save_tracks_to_db(user_id, activities):
    """Сохраняет треки из Strava в базу данных и возвращает количество новых треков."""
    if not activities:
        logging.info("Нет активностей для сохранения.")
        return 0

    user = get_user_by_id(user_id)
    if not user:
        logging.error(f"Не удалось получить данные пользователя с ID {user_id}. Прерываем сохранение.")
        return 0

    username = user.login
    new_tracks_count = 0

    for activity in activities:
        activity_id = activity.get('id')
        if not activity_id:
            logging.error("Отсутствует ID активности. Пропускаем.")
            continue

        # Проверяем, существует ли уже трек в базе данных
        existing_track = Track.query.filter_by(filename=str(activity_id)).first()
        if existing_track:
            continue

        try:
            # Преобразуем данные активности
            duration_str = str(timedelta(seconds=activity['moving_time']))
            net_duration_str = str(timedelta(seconds=activity['elapsed_time']))
            distance_km = activity['distance'] / 1000
            distance_str = f"{distance_km:.2f}"

            logging.info(f"Сохранение трека: ID={activity_id}, Название={activity.get('name')}, Дистанция={distance_str} км")

            # Создаем новый трек
            new_track = Track(
                user_id=user.id,
                filename=str(activity_id),
                name_track=activity.get('name', f"Активность {activity_id}"),
                distance=distance_str,
                duration=duration_str,
                upload_time=datetime.utcnow(),
                record_time=datetime.strptime(activity['start_date'], '%Y-%m-%dT%H:%M:%SZ'),
                height=activity['total_elevation_gain'],
                net_duration=net_duration_str,
                type=activity.get('type', 'Unknown')
            )

            # Сохраняем трек в базу данных
            db.session.add(new_track)
            db.session.commit()
            new_tracks_count += 1
            logging.info(f"Трек {activity_id} успешно сохранен для пользователя {username}.")

        except Exception as e:
            db.session.rollback()  # Откатываем транзакцию в случае ошибки
            logging.error(f"Ошибка при сохранении трека {activity_id} для пользователя {username}: {e}", exc_info=True)

    return new_tracks_count

@app.route('/sync_strava_tracks', methods=['GET', 'POST'])
@login_required
def sync_strava_tracks():
    logging.info(f"Пачынаем сінхранізацыю рукамі")
    """Синхронизация данных с Strava."""
    access_token = session.get('access_token')
    strava_profile_data = session.get('strava_profile_data')
    activities = session.get('strava_activities')

    if access_token:
        logging.info(f"Токен доступа найден для пользователя {current_user.id}.")

        if not strava_profile_data or not activities:
            if token_is_expired(current_user.id):
                logging.info(f"Токен доступа для пользователя {current_user.id} истек.")
                refresh_access_token()
                access_token = session.get('access_token')
                logging.info(f"Токен доступа обновлен для пользователя {current_user.id}.")

            try:
                # Связь с Strava API для получения данных профиля
                logging.info(f"Связываемся с Strava для пользователя {current_user.id}.")
                headers = {'Authorization': f'Bearer {access_token}'}
                strava_profile_url = 'https://www.strava.com/api/v3/athlete'
                response = requests.get(strava_profile_url, headers=headers)
                response.raise_for_status()
                strava_profile_data = response.json()
                session['strava_profile_data'] = strava_profile_data
                logging.info(f"Данные профиля Strava успешно сохранены для пользователя {current_user.id}.")

                # Получение списка активностей
                activities = get_activities(access_token)
                session['strava_activities'] = activities
                logging.info(f"Получено {len(activities)} активностей для пользователя {current_user.id}.")

                # Обновление ссылки на Strava в базе данных
                strava_url = f"https://www.strava.com/athletes/{strava_profile_data['id']}"
                update_strava_url_in_db(current_user.id, strava_url)
                logging.info(f"Ссылка на профиль Strava обновлена для пользователя {current_user.id}.")

            except requests.exceptions.RequestException as e:
                logging.error(f"Ошибка при получении данных с Strava для пользователя {current_user.id}: {e}")
                flash("Ошибка при загрузке данных с Strava.", "danger")

    return redirect(url_for('profile'))





def save_strava_tokens(user_id, access_token, refresh_token, expires_at):
    """Сохраняет токены Strava в базе данных."""
    strava_data = Strava.query.filter_by(user_id=user_id).first()
    if not strava_data:
        strava_data = Strava(user_id=user_id)
        db.session.add(strava_data)

    strava_data.access_token = access_token
    strava_data.refresh_token = refresh_token
    strava_data.token_expires_at = datetime.utcfromtimestamp(expires_at)
    db.session.commit()

def update_strava_sync_time(user_id):
    """Обновление времени последней синхронизации со Strava."""
    try:
        # Ищем данные пользователя в таблице Strava
        strava_data = Strava.query.filter_by(user_id=user_id).first()
        
        if strava_data:
            # Обновляем время синхронизации
            strava_data.synchron = datetime.utcnow()  # Используем правильное поле "synchron"
            db.session.commit()
            logging.info(f"Время синхронизации обновлено для пользователя с ID {user_id}.")
        else:
            logging.error(f"Не найдены данные Strava для пользователя с ID {user_id}.")
    except Exception as e:
        db.session.rollback()  # Откат транзакции в случае ошибки
        logging.error(f"Ошибка при обновлении времени синхронизации для пользователя с ID {user_id}: {e}")

