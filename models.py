from kod import db, manager
from flask_login import UserMixin
from datetime import timedelta, datetime


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(128), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    email = db.Column(db.String(120), nullable=True, unique=True)
    remember_token = db.Column(db.String(200), nullable=True)  # Токен для cookies

    # Отношения с Strava
    strava_data = db.relationship('Strava', back_populates='user', uselist=False)

@manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

class Track(db.Model):
    __tablename__ = 'gpx'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(128), nullable=False)
    filename = db.Column(db.String(128), nullable=False, unique=True)
    name_track = db.Column(db.String(128), nullable=True)
    distance = db.Column(db.Float)
    duration = db.Column(db.String)
    upload_time = db.Column(db.DateTime)
    record_time = db.Column(db.DateTime)
    height = db.Column(db.Integer)
    net_duration = db.Column(db.String)
    type = db.Column(db.String(128), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


class Challenge(db.Model):
    __tablename__ = 'challenge'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    distance = db.Column(db.Integer, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    participants = db.relationship('ChallengeParticipants', backref='challenge', lazy=True)
    is_private = db.Column(db.Boolean, default=False)
    is_closed = db.Column(db.Boolean, default=False)
    description = db.Column(db.String(255), nullable=True)
    creator = db.relationship('User', backref='challenges_created')
    type = db.Column(db.String(255), nullable=True)


class ChallengeParticipants(db.Model):
    __tablename__ = 'challenge_participants'
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenge.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    track_id = db.Column(db.Integer, db.ForeignKey('gpx.id'))

    track = db.relationship('Track', backref='participants')
    user = db.relationship('User', backref='challenge_participants')

    def get_total_distance(self):
        challenge = Challenge.query.get(self.challenge_id)

        # Фильтруем треки по нужным типам
        gpx_tracks = Track.query.filter(
            Track.user_id == self.user_id,
            Track.record_time >= challenge.start_date,
            Track.record_time <= challenge.end_date,
            (Track.type == 'ride') | (Track.type == 'virtualride') | (Track.type.is_(None))
        ).all()

        # Возвращаем сумму дистанций по отфильтрованным трекам
        return sum(track.distance for track in gpx_tracks)


    def get_total_duration(self):
        challenge = Challenge.query.get(self.challenge_id)
        gpx_tracks = Track.query.filter(
            Track.user_id == self.user_id,
            Track.record_time >= challenge.start_date,
            Track.record_time <= challenge.end_date + timedelta(days=1),
            (Track.type == 'ride') | (Track.type == 'virtualride') | (Track.type.is_(None))
        ).all()

        total_duration = timedelta()
        for track in gpx_tracks:
            if track.duration:
                h, m, s = map(int, track.duration.split(':'))
                total_duration += timedelta(hours=h, minutes=m, seconds=s)

        total_seconds = int(total_duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def get_tracks_info(self):
        challenge = Challenge.query.get(self.challenge_id)
        gpx_tracks = Track.query.filter(
            Track.user_id == self.user.login,
            Track.record_time >= challenge.start_date,
            Track.record_time <= challenge.end_date
        ).all()

        return [
            {
                'distance': track.distance,
                'record_time': track.record_time,
                'net_duration': track.net_duration,
                'upload_time': track.upload_time,
                'name_track': track.name_track
            }
            for track in gpx_tracks
        ]

class Strava(db.Model):
    __tablename__ = 'strava'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    access_token = db.Column(db.String(255), nullable=False)
    refresh_token = db.Column(db.String(255), nullable=False)
    token_expires_at = db.Column(db.DateTime, nullable=False)
    last_synced_at = db.Column(db.DateTime, default=datetime.utcnow)
    strava_url = db.Column(db.String(255), nullable=True)
    synchron = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', back_populates='strava_data')

class UserPosition(db.Model):
    __tablename__ = 'user_position'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenge.id'), nullable=True)
    date_position = db.Column(db.DateTime, nullable=True)  # Добавленная колонка для даты позиции
    position = db.Column(db.Integer, nullable=True)

    user = db.relationship('User', backref=db.backref('user_positions', lazy=True))
    challenge = db.relationship('Challenge', backref=db.backref('user_positions', lazy=True))

    def __repr__(self):
        return f'<UserPosition user_id={self.user_id}, challenge_id={self.challenge_id}, now_position={self.now_position}, old_position={self.old_position}, position={self.position}>'

class Comment(db.Model):
    __tablename__ = 'comments'  # Имя таблицы должно соответствовать имени в базе данных
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)  # Добавлен индекс
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenge.id'), nullable=False, index=True)  # Добавлен индекс
    user_comment = db.Column(db.Text, nullable=False)

    user = db.relationship('User', backref=db.backref('comments', lazy=True))
    challenge = db.relationship('Challenge', backref=db.backref('comments', lazy=True))
