from kod import app
from flask import render_template
from kod.models import User, Strava
from kod.admin_all_challenges import admin_required

# Функция для получения информации о Strava для каждого пользователя
def get_strava_data_for_user(user_id):
    """Получаем данные о Strava для пользователя."""
    strava_info = Strava.query.filter_by(user_id=user_id).first()  # Получаем запись Strava для пользователя
    return strava_info.strava_url if strava_info else None

@app.route('/admin_all_users')
@admin_required  # Проверка админских прав
def admin_all_users():
    all_users = User.query.all()  # Получаем все пользователей
    users_with_strava = []

    for user in all_users:
        # Для каждого пользователя получаем ссылку на его Strava (если она есть)
        strava_url = get_strava_data_for_user(user.id)
        users_with_strava.append({
            'id': user.id,
            'email': user.email,
            'name': user.login,
            'strava_url': strava_url
        })

    return render_template('admin_all_users.html', users_with_strava=users_with_strava)
