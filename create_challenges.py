from kod import db
from kod.models import Challenge, Track, ChallengeParticipants
from flask_login import current_user

def create_challenge(name, description, distance, start_date, end_date, is_private, creator_id, challenge_type="talaka"):
    """Создание нового челленджа."""
    # Создание челленджа
    new_challenge = Challenge(
        name=name,
        description=description,  # Добавлено описание
        distance=distance,
        start_date=start_date,
        end_date=end_date,
        is_private=is_private,
        creator_id=creator_id,
        type=challenge_type
    )
    db.session.add(new_challenge)
    db.session.commit()

    # Присоединение создателя к челленджу
    user_tracks = Track.query.filter_by(user_id=current_user.id).all()  # Исправлено на current_user.id
    track_id = user_tracks[0].id if user_tracks else None

    participant = ChallengeParticipants(
        challenge_id=new_challenge.id,
        user_id=creator_id,
        track_id=track_id
    )
    db.session.add(participant)
    db.session.commit()

    return new_challenge

