from flask import redirect, render_template, url_for, flash, session
from flask_login import current_user, login_required
from kod import app, db
from kod.models import Track, ChallengeParticipants, Challenge, User
import logging
import requests
from kod.strava import token_is_expired, refresh_access_token, get_activities, save_tracks_to_db, update_strava_url_in_db, update_strava_sync_time


@app.route('/profile')
@login_required
def profile():
    """Страница профиля пользователя с интеграцией данных Strava."""
    logging.debug('Загрузка профиля пользователя с ID: %s', current_user.id)
    user = User.query.get(current_user.id)

    if user is None:
        logging.error('Пользователь с ID %s не найден, перенаправление на страницу входа.', current_user.id)
        return redirect(url_for('login'))  # Обработка на случай отсутствия пользователя

    # Получаем связанные данные Strava для текущего пользователя
    strava_data = user.strava_data  # Это объект Strava, связанный с пользователем

    # Если пользователь аутентифицирован и токен истек, обновляем токен
    if current_user.is_authenticated and strava_data and token_is_expired(current_user.id):
        logging.info("Токен доступу скончаны ў %s. Аднаўляем!", current_user.id)
        refresh_access_token(current_user.id)

        # Получаем новый токен из сессии и сохраняем в базе данных
        new_access_token = session.get('access_token')  # Новый токен из сессии
        if new_access_token:
            strava_data.access_token = new_access_token  # Обновляем токен в объекте Strava
            db.session.commit()  # Сохраняем обновленный токен в базе данных
            session['access_token'] = new_access_token  # Сохраняем новый токен в сессии
            logging.info('Токен доступу адноўлены ў %s', current_user.login)
        else:
            logging.error("Не удалось обновить токен для пользователя %s", current_user.login)
            session.pop('access_token', None)  # Очищаем сессию
            return redirect(url_for('login_page'))  # Переход на страницу входа

    # Запрашиваем треки текущего пользователя в хронологическом порядке (новые сначала)
    logging.info('Просім трэкі са Страва: %s', current_user.login)
    user_tracks = Track.query.filter(
        Track.user_id == current_user.id,
        (Track.type == 'ride') | (Track.type == 'virtualride') | (Track.type.is_(None))
    ).order_by(Track.record_time.desc()).limit(10).all()

    # Преобразуем треки для отображения
    formatted_tracks = [
        {
            'id': track.id,
            'name_track': track.name_track,
            'distance': track.distance,
            'duration': track.duration,
            'record_time': track.record_time,
            'net_duration': track.net_duration
        }
        for track in user_tracks
    ]

    # Получаем челенджи, которые создал пользователь
    created_challenges = Challenge.query.filter_by(creator_id=user.id).all()

    # Получаем челенджи, в которых участвует текущий пользователь
    participant_challenges = ChallengeParticipants.query.filter_by(user_id=current_user.id).all()
    participant_challenges_list = [
        Challenge.query.get(participant.challenge_id)
        for participant in participant_challenges if Challenge.query.get(participant.challenge_id)
    ]

    # Получаем токен из таблицы Strava, связанной с пользователем
    access_token = strava_data.access_token if strava_data else None

    strava_profile_url = None
    activities = None

    if access_token:
        logging.info('Токен доступу ёсць у %s', current_user.id)
        try:
            # Получаем данные профиля Strava
            logging.info("Запрашываем інфу пра %s са Страва", current_user.login)
            headers = {'Authorization': f'Bearer {access_token}'}
            strava_profile_api_url = 'https://www.strava.com/api/v3/athlete'
            response = requests.get(strava_profile_api_url, headers=headers)
            response.raise_for_status()
            strava_profile_data = response.json()

            # Извлекаем athlete_id и формируем ссылку
            athlete_id = strava_profile_data.get("id")
            if athlete_id:
                strava_profile_url = f"https://www.strava.com/athletes/{athlete_id}"
                update_strava_url_in_db(current_user.id, strava_profile_url)

            # Получаем активности
            logging.info("Атрымліваем трэкі %s", current_user.login)
            activities = get_activities(access_token)

            # Сохраняем треки из Strava в базу данных
            logging.info("Захоўваем трэкі ў базе дадзенных %s", current_user.login)
            new_tracks_count = save_tracks_to_db(current_user.id, activities)

            update_strava_sync_time(current_user.id)

            # Формируем сообщение для пользователя
            if new_tracks_count > 0:
                flash(f"Запампавана {new_tracks_count} новых трэкаў!", "success")
            else:
                flash("Новых трэкаў няма!", "info")
            logging.info(f"Запампавана {new_tracks_count} новых трэкаў {current_user.login}.")

        except requests.exceptions.RequestException as e:
            logging.error(f"Памылка пры атрыманні дадзеных са Страва ў {current_user.login}: {e}")
            strava_profile_url = None
            activities = None
            flash("Памылка пры запампаванні дадзеных у Strava.", "danger")

    return render_template(
        'profile.html',
        username=current_user.login,
        tracks=formatted_tracks,
        created_challenges=created_challenges,
        participant_challenges=participant_challenges_list,
        user=user,
        strava_profile_url=strava_profile_url,
        activities=activities,
        strava_profile_data=access_token
    )

