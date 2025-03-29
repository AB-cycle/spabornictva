from flask import render_template
from kod import app, db
from kod.models import User, Challenge, UserPosition


from sqlalchemy import func
from sqlalchemy.orm import aliased

from kod.user_statistics import calculate_total_distance_user, get_longest_ride_streak, get_ride_days_count, get_ride_streak_count, get_track_count, get_percentile_of_longest_streak, get_percentile_of_total_distance, get_percentile_of_ride_days, get_percentile_of_total_tracks, get_percentile_of_ride_streak
from kod.filtres import get_filtered_tracks

@app.route('/public_profile/<int:user_id>')
def public_profile(user_id):
    """Отображение публичного профиля участника."""
    user = User.query.get_or_404(user_id)

    # Получаем ссылку на профиль Strava из данных пользователя
    strava_profile_url = user.strava_data and user.strava_data.strava_url

    # Получаем информацию о последней синхронизации
    synchron = user.strava_data.synchron if user.strava_data else None

    # Подсчитываем статистику пользователя
    total_distance_user = calculate_total_distance_user(user_id)
    ride_days_count = get_ride_days_count(user_id)
    ride_streak_count = get_ride_streak_count(user_id)
    longest_ride_streak = get_longest_ride_streak(user_id)
    track_count = get_track_count(user_id)
    filtered_tracks = get_filtered_tracks(user_id)
    streak_percentile = get_percentile_of_longest_streak(user_id)  # Процентиль по серии
    distance_percentile = get_percentile_of_total_distance(user_id)  # Процентиль по дистанции
    ride_days_percentile = get_percentile_of_ride_days(user_id)  # Процентиль по дням с поездками
    track_percentile = get_percentile_of_total_tracks(user_id)  # Процентиль по трекам
    ride_streak_percentile = get_percentile_of_ride_streak(user_id)  # Процентиль по серии

    # Создаем алиас для таблицы UserPosition
    user_position_alias = aliased(UserPosition)

    # Извлекаем только последнюю позицию для каждого челленджа
    user_positions = (
        db.session.query(
            UserPosition,
            Challenge
        )
        .join(Challenge, UserPosition.challenge_id == Challenge.id)
        .filter(UserPosition.user_id == user_id)
        .filter(UserPosition.date_position == db.session.query(func.max(user_position_alias.date_position))
                .filter(user_position_alias.challenge_id == Challenge.id)
                .filter(user_position_alias.user_id == user_id)
                .correlate(Challenge)
                .scalar_subquery())
        .order_by(Challenge.start_date.desc())
        .all()
    )

    # Для поиска самой высокой и самой низкой позиции
    min_position = None
    max_position = None

    for position, challenge in user_positions:
        if min_position is None or position.position < min_position:
            min_position = position.position
        if max_position is None or position.position > max_position:
            max_position = position.position

    # Если у пользователя нет позиций, возвращаем профиль без позиций
    if not user_positions:
        return render_template(
            'public_profile.html',
            user=user,
            strava_profile_url=strava_profile_url,
            positions=None,
            min_position=None,
            max_position=None,
            total_distance_user=total_distance_user,
            ride_days_count=ride_days_count,
            ride_days_percentile=ride_days_percentile,  # Процентиль по дням
            ride_streak_count=ride_streak_count,
            longest_ride_streak=longest_ride_streak,
            streak_percentile=streak_percentile,
            distance_percentile=distance_percentile,  # Процентиль по дистанции
            track_count=track_count,
            track_percentile=track_percentile,  # Процентиль по трекам
            ride_streak_percentile=ride_streak_percentile,  # Процентиль по сериями
            filtered_tracks=None,
            synchron=synchron
        )

    # Отображаем профиль пользователя с полной статистикой
    return render_template(
        'public_profile.html',
        user=user,
        strava_profile_url=strava_profile_url,
        positions=user_positions,
        min_position=min_position,
        max_position=max_position,
        total_distance_user=total_distance_user,
        ride_days_count=ride_days_count,
        ride_days_percentile=ride_days_percentile,  # Процентиль по дням
        ride_streak_count=ride_streak_count,
        longest_ride_streak=longest_ride_streak,
        streak_percentile=streak_percentile,  # Процентиль по серии
        distance_percentile=distance_percentile,  # Процентиль по дистанции
        track_count=track_count,
        track_percentile=track_percentile,  # Процентиль по трекам
        ride_streak_percentile=ride_streak_percentile,  # Процентиль по сериями
        filtered_tracks=filtered_tracks,
        synchron=synchron
    )
