from kod import db, app
from kod.models import User, Track, Challenge  # Убедитесь, что путь к модели User правильный

def count_users():
    """Подсчитывает количество всех пользователей (участников)."""
    try:
        return db.session.query(User).count()
    except Exception as e:
        app.logger.error(f"Ошибка при подсчете пользователей: {e}")
        return 0

def count_tracks():
    """Подсчитывает количество всех треков (записей в таблице gpx)."""
    try:
        return db.session.query(Track).count()
    except Exception as e:
        app.logger.error(f"Ошибка при подсчете треков: {e}")
        return 0
    
def count_challenges():
    """Подсчитывает количество всех челленджей (записей в таблице Challenge)."""
    try:
        return db.session.query(Challenge).count()
    except Exception as e:
        app.logger.error(f"Ошибка при подсчете челленджей: {e}")
        return 0
    
def count_total_distance():
    """Подсчитывает общее расстояние треков с определенными типами."""
    try:
        total_distance = db.session.query(
            db.func.sum(Track.distance)
        ).filter(
            (Track.type == 'ride') | 
            (Track.type == 'virtualride') | 
            (Track.type.is_(None))  # Фильтрация по колонке 'type'
        ).scalar()  # Суммируем расстояние только для подходящих треков
        return total_distance if total_distance else 0
    except Exception as e:
        app.logger.error(f"Ошибка при подсчете общего расстояния: {e}")
        return 0
