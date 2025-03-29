import logging
from flask import redirect, url_for, flash
from kod import app
from kod.models import Strava
from kod.strava import get_activities, save_tracks_to_db, refresh_access_token
from datetime import datetime
import os

from kod.admin import admin_required
from kod.strava import update_strava_sync_time

# Путь к подпапке для логов
log_dir = 'logs'

# Проверяем, существует ли папка, если нет - создаем
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Настройка логирования
logging.basicConfig(
    filename=os.path.join(log_dir, 'sync_tracks.log'),  # Указываем файл для логов внутри папки logs
    level=logging.INFO,  # Уровень логирования
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def sync_tracks():
    with app.app_context():
        users = Strava.query.all()  # Получаем всех пользователей
        for user in users:
            logging.info(f"Начинаем синхронизацию для пользователя {user.user_id}")

            # Проверка на отсутствие данных Strava
            if not user.access_token or not user.refresh_token:
                logging.warning(f"Нет данных Strava для пользователя {user.user_id}. Пропускаем.")
                continue  # Пропускаем пользователей без данных Strava

            # Проверяем, истек ли токен
            if user.token_expires_at and user.token_expires_at < datetime.utcnow():
                new_token = refresh_access_token(user.user_id)  # Обновляем токен
                if not new_token:
                    logging.error(f"Ошибка обновления токена для пользователя {user.user_id}")
                    continue

            access_token = user.access_token
            activities = get_activities(access_token)
            if activities:
                new_tracks_count = save_tracks_to_db(user.user_id, activities)
                logging.info(f"Добавлено {new_tracks_count} новых треков для пользователя {user.user_id}")
            else:
                logging.info(f"Нет новых активностей для пользователя {user.user_id}")

@app.route('/sync_strava', methods=['GET'])
@admin_required  # Добавьте проверку на админские права
def sync_strava():
    try:
        flash("Синхронизация с Strava началась...", "info")
        # Начинаем синхронизацию
        with app.app_context():
            users = Strava.query.all()  # Получаем всех пользователей
            total_users = len(users)
            total_tracks = 0

            for user in users:
                logging.info(f"Начинаем синхронизацию для пользователя {user.user_id}")

                if not user.access_token or not user.refresh_token:
                    logging.warning(f"Нет данных Strava для пользователя {user.user_id}. Пропускаем.")
                    continue  # Пропускаем пользователей без данных Strava

                if user.token_expires_at and user.token_expires_at < datetime.utcnow():
                    new_token = refresh_access_token(user.user_id)
                    if not new_token:
                        logging.error(f"Ошибка обновления токена для пользователя {user.user_id}")
                        continue

                access_token = user.access_token
                activities = get_activities(access_token)
                if activities:
                    new_tracks_count = save_tracks_to_db(user.user_id, activities)
                    total_tracks += new_tracks_count
                    logging.info(f"Добавлено {new_tracks_count} новых треков для пользователя {user.user_id}")
                    
                    # Обновляем время последней синхронизации
                    update_strava_sync_time(user.user_id)

                else:
                    logging.info(f"Нет новых активностей для пользователя {user.user_id}")

            flash(f"Синхронизация завершена: {total_users} пользователей и {total_tracks} треков синхронизировано.", "success")

    except Exception as e:
        flash(f'Произошла ошибка при синхронизации: {str(e)}', 'danger')

    return redirect(url_for('admin_dashboard'))  # Перенаправляем на админскую страницу
