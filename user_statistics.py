from kod import db
from kod.models import Track
from datetime import timedelta

from kod.filtres import get_filtered_tracks


def calculate_total_distance_user(user_id):
    """Подсчёт общего количества километров для пользователя."""
    filtered_tracks = get_filtered_tracks(user_id)
    total_distance = sum(track.distance for track in filtered_tracks)
    return total_distance or 0



def get_ride_days_count(user_id):
    """
    Подсчёт количества уникальных дней, в которые пользователь записал поездки.
    :param user_id: ID пользователя
    :return: количество уникальных дней
    """
    filtered_tracks = get_filtered_tracks(user_id)
    ride_days = {track.record_time.date() for track in filtered_tracks}
    return len(ride_days) or 0


def get_ride_streak_count(user_id):
    """
    Подсчёт количества серий дней с поездками (минимум 2 дня подряд).
    :param user_id: ID пользователя
    :return: количество серий дней с поездками
    """
    filtered_tracks = get_filtered_tracks(user_id)
    ride_days = sorted({track.record_time.date() for track in filtered_tracks})

    if len(ride_days) < 2:
        return 0

    streak_count = 0
    current_streak = 1

    for i in range(1, len(ride_days)):
        if (ride_days[i] - ride_days[i - 1]).days == 1:
            current_streak += 1
        else:
            if current_streak >= 2:
                streak_count += 1
            current_streak = 1

    if current_streak >= 2:
        streak_count += 1

    return streak_count


def get_longest_ride_streak(user_id):
    """Подсчитывает самую длинную серию дней подряд с поездками для пользователя."""
    filtered_tracks = get_filtered_tracks(user_id)
    ride_days = sorted({track.record_time.date() for track in filtered_tracks})

    if not ride_days:
        return 0

    longest_streak = 1
    current_streak = 1

    for i in range(1, len(ride_days)):
        if ride_days[i] == ride_days[i - 1] + timedelta(days=1):
            current_streak += 1
        else:
            longest_streak = max(longest_streak, current_streak)
            current_streak = 1  # сбросить счётчик для новой серии

    longest_streak = max(longest_streak, current_streak)

    return longest_streak


def get_track_count(user_id):
    """Подсчитывает количество треков для пользователя."""
    filtered_tracks = get_filtered_tracks(user_id)
    return len(filtered_tracks)

def get_percentile_of_longest_streak(user_id):
    """
    Вычисляет процент участников, у которых самая длинная серия дней с поездками меньше, чем у текущего пользователя.
    :param user_id: ID пользователя
    :return: процент участников
    """
    # Вычисляем самую длинную серию текущего пользователя
    current_user_streak = get_longest_ride_streak(user_id)

    # Получаем всех пользователей, у которых есть треки
    all_user_ids = (
        db.session.query(Track.user_id)
        .distinct()
        .all()
    )

    # Если список пользователей пустой
    if not all_user_ids:
        return 0

    # Для каждого пользователя получаем фильтрованные треки и вычисляем самую длинную серию
    user_streaks = []
    for user in all_user_ids:
        user_tracks = get_filtered_tracks(user[0])  # Получаем треки пользователя
        user_streak = get_longest_ride_streak(user[0])  # Вычисляем самую длинную серию для этого пользователя
        user_streaks.append(user_streak)

    # Подсчитываем, сколько пользователей имеют серию меньшую, чем у текущего пользователя
    less_count = sum(1 for streak in user_streaks if streak < current_user_streak)

    # Общий процент
    percentile = (less_count / len(user_streaks)) * 100

    return round(percentile)



def get_percentile_of_total_distance(user_id):
    """
    Вычисляет процент участников, у которых общий километраж меньше, чем у текущего пользователя.
    :param user_id: ID пользователя
    :return: процент участников
    """
    # Общий километраж текущего пользователя
    user_tracks = get_filtered_tracks(user_id)
    user_distance = sum(track.distance for track in user_tracks if track.distance)

    # Получаем список всех пользователей и их общего километража
    all_distances = []
    all_user_ids = (
        db.session.query(Track.user_id)
        .distinct()
        .all()
    )

    # Для каждого пользователя получаем фильтрованные треки и вычисляем общий километраж
    for user in all_user_ids:
        user_tracks = get_filtered_tracks(user[0])  # Получаем фильтрованные треки
        total_distance = sum(track.distance for track in user_tracks if track.distance)
        all_distances.append(total_distance)

    # Если список пуст
    if not all_distances:
        return 0

    # Подсчитываем процент пользователей, чей километраж меньше, чем у текущего
    below_count = sum(1 for d in all_distances if d < user_distance)
    percentile = (below_count / len(all_distances)) * 100

    return round(percentile)


def get_percentile_of_ride_days(user_id):
    """
    Вычисляет процент участников, у которых количество уникальных дней с поездками меньше, чем у текущего пользователя.
    :param user_id: ID пользователя
    :return: процент участников
    """
    # Количество уникальных дней с поездками у текущего пользователя
    user_tracks = get_filtered_tracks(user_id)
    user_ride_days = len(set(track.record_time.date() for track in user_tracks))

    # Получаем количество уникальных дней с поездками для всех пользователей
    all_ride_days = []
    all_user_ids = (
        db.session.query(Track.user_id)
        .distinct()
        .all()
    )

    # Для каждого пользователя получаем фильтрованные треки и вычисляем количество уникальных дней
    for user in all_user_ids:
        user_tracks = get_filtered_tracks(user[0])  # Получаем фильтрованные треки
        ride_days = len(set(track.record_time.date() for track in user_tracks))
        all_ride_days.append(ride_days)

    # Если данных нет, возвращаем 0%
    if not all_ride_days:
        return 0

    # Добавляем количество дней с поездками текущего пользователя в список
    all_ride_days.append(user_ride_days)

    # Подсчитываем, сколько пользователей имеют меньше дней с поездками
    below_count = sum(1 for days in all_ride_days if days < user_ride_days)

    # Количество пользователей (включая текущего)
    total_users = len(all_ride_days)

    # Рассчитываем процент
    percentile = (below_count / total_users) * 100

    # Гарантируем, что процент не превышает 100%
    return min(round(percentile), 100)

def get_percentile_of_total_tracks(user_id):
    """
    Вычисляет процент участников, у которых количество треков меньше, чем у текущего пользователя.
    :param user_id: ID пользователя
    :return: процент участников
    """
    # Количество треков текущего пользователя
    user_tracks_count = len(get_filtered_tracks(user_id))

    # Получаем список всех пользователей и их количества треков
    all_tracks_counts = []
    all_user_ids = (
        db.session.query(Track.user_id)
        .distinct()
        .all()
    )

    # Для каждого пользователя получаем фильтрованные треки и вычисляем количество треков
    for user in all_user_ids:
        user_tracks = get_filtered_tracks(user[0])  # Получаем фильтрованные треки
        tracks_count = len(user_tracks)
        all_tracks_counts.append(tracks_count)

    # Если список пуст
    if not all_tracks_counts:
        return 0

    # Подсчитываем процент пользователей, у которых количество треков меньше, чем у текущего
    below_count = sum(1 for count in all_tracks_counts if count < user_tracks_count)
    percentile = (below_count / len(all_tracks_counts)) * 100

    return round(percentile)

def get_percentile_of_ride_streak(user_id):
    """
    Вычисляет процент участников, у которых самая длинная серия дней с поездками меньше или равна самой длинной
    серии текущего пользователя.
    :param user_id: ID пользователя
    :return: процент участников
    """
    # Самая длинная серия дней с поездками текущего пользователя
    current_user_streak = get_longest_ride_streak(user_id)

    # Получаем всех пользователей, у которых есть треки
    all_user_ids = (
        db.session.query(Track.user_id)
        .distinct()
        .all()
    )

    # Если список пользователей пустой
    if not all_user_ids:
        return 0

    # Вычисляем самую длинную серию для каждого пользователя
    user_streaks = [
        get_longest_ride_streak(user[0]) for user in all_user_ids
    ]

    # Подсчитываем, сколько пользователей имеют серию меньшую или равную текущему пользователю
    less_equal_count = sum(1 for streak in user_streaks if streak <= current_user_streak)

    # Общий процент
    percentile = (less_equal_count / len(user_streaks)) * 100

    return round(percentile)
