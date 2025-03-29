from flask import Flask, render_template, request
from config import Configuration
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from datetime import timedelta
import locale
from flask_mail import Mail
import logging
import os

app = Flask(__name__)
app.config.from_object(Configuration)
app.secret_key = 'va_usiu_moc'

app.config['SESSION_PERMANENT'] = False  # Чтобы сессия сохранялась на время работы браузера
app.config['REMEMBER_COOKIE_DURATION'] =  timedelta(days=300)  # Чтоб "запомнить" пользователя на 7 дней


MAINTENANCE_MODE = os.getenv('MAINTENANCE_MODE', 'off') == 'on'


@app.before_request
def maintenance_mode():
    if not MAINTENANCE_MODE:  # Если режим обслуживания выключен
        return None

    # Исключаем страницу входа (проверка по имени маршрута)
    if request.endpoint == 'login_page':  # Это маршрут для входа
        return None

    # Пропускаем запросы к static/
    if request.path.startswith('/static/'):
        return None

    # Если пользователь администратор, пропускаем
    if current_user.is_authenticated and current_user.is_admin:  # Проверяем атрибут is_admin
        return None

    # Показываем страницу заглушки
    return render_template('maintenance.html'), 503



app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'aroundbelarusklub@gmail.com'
app.config['MAIL_PASSWORD'] = 'zsyfqitezcvgursy'

app.config['MAIL_DEFAULT_SENDER'] = 'aroundbelarusklub@gmail.com'
mail = Mail(app)




# Настройка логирования
log_folder = 'logs'
log_file = os.path.join(log_folder, 'error.log')

# Проверяем, существует ли папка для логов, если нет, то создаем её
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

# Создаем обработчик для записи ошибок в лог
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)  # Уровень логирования, можно изменить на ERROR для ошибок

# Форматирование сообщений лога
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Добавляем обработчик в логгер Flask
app.logger.addHandler(file_handler)

db = SQLAlchemy(app)
manager = LoginManager(app)

locale.setlocale(locale.LC_TIME, 'be_BY')

from kod import (
    admin_all_tracks,
    models,
    routes,
    profile,
    tracks,
    challenges,
    admin,
    admin_all_challenges,
    archive,
    strava,
    edit_profile,
    user_tracks,
    positions,
    positions_details,
    public_profile,
    comments,
    sync_tracks,
    admin_all_users,
    user_statistics
)
