# kod/filters.py
from kod.models import Track  # Убедитесь, что импорт корректен
from sqlalchemy import or_

def get_filtered_tracks(user_id):
    """Фильтрует треки по типу: ride, virtualride и NULL."""
    return Track.query.filter(
        Track.user_id == user_id,
        or_(
            Track.type == 'ride',
            Track.type == 'virtualride',
            Track.type.is_(None)
        )
    ).all()
