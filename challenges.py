from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from itertools import groupby
from operator import itemgetter
import bleach



from kod import app, db
from kod.models import Challenge, ChallengeParticipants, User, Track, UserPosition, Comment
from kod.positions import update_user_positions

from kod.create_challenges import create_challenge

@app.route('/challenges', methods=['GET', 'POST'])
def challenges():
    error = None

    if request.method == 'POST':
        # Получение данных из формы
        name = request.form.get('name')
        description = request.form.get('description')  # Добавляем описание
        distance = request.form.get('distance')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        is_private = request.form.get('is_private') == 'on'
        challenge_type = request.form.get('challenge_type', 'talaka')

        # Проверка данных
        if not start_date or not end_date:
            error = 'Выберите даты начала и окончания'
        else:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                error = 'Неверный формат даты'

        if error:
            return render_template('challenges.html', challenges=Challenge.query.all(), error=error)

        # Создание челленджа
        create_challenge(
            name=name,
            description=description,  # Передаем описание
            distance=distance,
            start_date=start_date,
            end_date=end_date,
            is_private=is_private,
            creator_id=current_user.id,
            challenge_type=challenge_type
        )

        return redirect(url_for('profile'))

    challenges = Challenge.query.all()
    return render_template('challenges.html', challenges=challenges, error=error)


@app.route('/challenge/<int:challenge_id>')
def challenge_detail(challenge_id):
    update_user_positions(challenge_id)  # Обновляем позиции участников

    # Получаем данные челенджа
    challenge = Challenge.query.get_or_404(challenge_id)

    # Преобразуем описание в HTML с активными ссылками
    if challenge.description:
        challenge.description = bleach.linkify(challenge.description)

    # Преобразуем тип для отображения
    challenge.type_display = {
        'talaka': 'Талака',
        'individual': 'Мая мэта'
    }.get(challenge.type, challenge.type)

    creator = User.query.get(challenge.creator_id)
    participants = ChallengeParticipants.query.filter_by(challenge_id=challenge_id).all()
    start_date = challenge.start_date
    end_date = challenge.end_date
    today = datetime.today().date()

    # Инициализация переменных
    total_distance_covered = 0
    daily_distance_covered = 0
    participant_contributions = {}
    participants_data = []
    participants_no_distance = 0  # Количество участников, не проехавших ни километра

    # Обработка данных участников
    for participant in participants:
        filtered_tracks = Track.query.filter_by(user_id=participant.user_id).filter(
            Track.record_time >= start_date,
            Track.record_time <= end_date + timedelta(days=1),
            (Track.type == 'ride') | (Track.type == 'virtualride') | (Track.type.is_(None))
        ).all()

        participant_distance = sum(track.distance for track in filtered_tracks)
        total_distance_covered += participant_distance

        if participant_distance == 0:
            participants_no_distance += 1

        contribution_percentage = (participant_distance / challenge.distance * 100) if challenge.distance > 0 else 0
        participant_contributions[participant.user_id] = round(contribution_percentage, 2)

        daily_tracks = [track for track in filtered_tracks if track.upload_time.date() == today]
        daily_distance = sum(track.distance for track in daily_tracks)
        daily_distance_covered += daily_distance

        last_position_today = (
            UserPosition.query.filter_by(user_id=participant.user_id, challenge_id=challenge_id)
            .filter(UserPosition.date_position >= datetime.combine(today, datetime.min.time()))
            .filter(UserPosition.date_position <= datetime.combine(today, datetime.max.time()))
            .order_by(UserPosition.date_position.desc())
            .first()
        )

        last_position_before_today = (
            UserPosition.query.filter_by(user_id=participant.user_id, challenge_id=challenge_id)
            .filter(UserPosition.date_position < datetime.combine(today, datetime.min.time()))
            .order_by(UserPosition.date_position.desc())
            .first()
        )

        position_change = 0
        arrow = None
        position_change_text = None

        if last_position_today and last_position_before_today:
            position_change = last_position_today.position - last_position_before_today.position

        if position_change > 0:
            arrow = "down-arrow"
        elif position_change < 0:
            arrow = "up-arrow"

        if position_change != 0:
            position_change_text = f"{'+' if position_change < 0 else '-'}{abs(position_change)}"

        participants_data.append({
            'participant': participant,
            'total_distance': participant_distance,
            'arrow': arrow,
            'position_change': abs(position_change),
            'position_change_text': position_change_text
        })

    sorted_participants = sorted(participants_data, key=lambda x: x['total_distance'], reverse=True)

    total_percentage = (total_distance_covered / challenge.distance * 100) if challenge.distance > 0 else 0
  

    daily_percentage = (daily_distance_covered / challenge.distance * 100) if challenge.distance > 0 else 0
    daily_percentage = min(daily_percentage, 100)

    daily_total_distances = {}
    tracks = Track.query.filter(
        Track.record_time >= start_date,
        Track.record_time <= end_date + timedelta(days=1),
        (Track.type == 'ride') | (Track.type == 'virtualride') | (Track.type.is_(None))
    )
    if challenge.type == 'individual':
        tracks = tracks.filter_by(user_id=creator.id)

    for track in tracks.all():
        record_date = track.record_time.date()
        daily_total_distances[record_date] = daily_total_distances.get(record_date, 0) + track.distance

    # Получаем треки для создателя (или всех участников в случае группового челенджа)
    tracks_info = get_tracks_for_challenge(challenge_id, user_id=creator.id)

    is_participant = False
    if current_user.is_authenticated:
        is_participant = ChallengeParticipants.query.filter_by(challenge_id=challenge_id, user_id=current_user.id).first() is not None

    invite_url = None
    if current_user.is_authenticated:
        invite_url = url_for('join_challenge', challenge_id=challenge_id, _external=True)

    comments = Comment.query.filter_by(challenge_id=challenge_id).all()

    template = 'challenge_meta.html' if challenge.type == 'individual' else 'challenge_detail.html'

    return render_template(
        template,
        challenge=challenge,
        creator=creator,
        participants=sorted_participants,
        total_distance_covered=round(total_distance_covered),
        total_percentage=total_percentage,
        daily_distance_covered=round(daily_distance_covered),
        daily_percentage=daily_percentage,
        is_participant=is_participant,
        invite_url=invite_url,
        participant_contributions=participant_contributions,
        daily_total_distances=daily_total_distances,
        comments=comments,
        participants_count=len(participants),
        participants_no_distance=participants_no_distance,
        tracks_info=tracks_info  # Передаем данные о треках
    )


@app.route('/challenge/<int:challenge_id>/close', methods=['POST'])
@login_required
def close_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    if challenge.creator_id != current_user.id and not current_user.is_admin:
        flash('У вас нет прав на закрытие этого чэленджа', 'error')
        return redirect(url_for('challenge_detail', challenge_id=challenge_id))

    challenge.is_closed = True
    db.session.commit()
    flash('Чэлендж закрыт для новых участников.', 'success')
    return redirect(url_for('challenge_detail', challenge_id=challenge_id))

@app.route('/join_challenge/<int:challenge_id>', methods=['POST'])
@login_required
def join_challenge(challenge_id):
    
    # Проверяем, есть ли уже участник с таким user_id и challenge_id
    existing_participant = ChallengeParticipants.query.filter_by(challenge_id=challenge_id, user_id=current_user.id).first()
    if not existing_participant:
        # Получаем все треки пользователя по user_id
        user_tracks = Track.query.filter_by(user_id=current_user.id).all()

        # Присваиваем track_id, если есть доступные треки
        track_id = user_tracks[0].id if user_tracks else None

        # Добавляем нового участника с track_id
        participant = ChallengeParticipants(challenge_id=challenge_id, user_id=current_user.id, track_id=track_id)
        db.session.add(participant)
        db.session.commit()
    
    update_user_positions(challenge_id)

    return redirect(url_for('profile'))


@app.route('/leave_challenge/<int:challenge_id>', methods=['POST'])
@login_required
def leave_challenge(challenge_id):
    
    existing_participant = ChallengeParticipants.query.filter_by(challenge_id=challenge_id, user_id=current_user.id).first()

    if existing_participant:
        db.session.delete(existing_participant)
        db.session.commit()
        flash('Вы успешно вышли из челенджа.', 'info')  # Уведомление
    
    update_user_positions(challenge_id)
    
    return redirect(url_for('challenges'))

@app.route('/view_tracks/<int:challenge_id>/<int:user_id>')
def view_tracks(challenge_id, user_id):
    # Получаем челендж
    challenge = Challenge.query.get_or_404(challenge_id)

    # Получаем пользователя
    user = User.query.get_or_404(user_id)

    # Получаем треки участника, связанные с конкретным челенджем
    participant = ChallengeParticipants.query.filter_by(challenge_id=challenge_id, user_id=user_id).first()

    # Фильтруем треки по дате и типу (ride, virtualride или NULL)
    tracks_info = []
    if participant:
        tracks = Track.query.filter(
            Track.user_id == user_id,  # Заменили Track.username на Track.user_id
            (Track.type == 'ride') | (Track.type == 'virtualride') | (Track.type.is_(None))  # Фильтрация по типам
        ).order_by(Track.record_time.desc()).all()

        tracks_info = [
            {'name_track': track.name_track, 'distance': track.distance, 'record_time': track.record_time, 'duration': track.duration, 'type': track.type}
            for track in tracks
            if challenge.start_date <= track.record_time.date() <= challenge.end_date
        ]

    return render_template('view_tracks.html', challenge=challenge, tracks_info=tracks_info, user=user)



@app.route('/delete_challenge/<int:challenge_id>', methods=['POST'])
def delete_challenge_user(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    
    # Обновляем все записи в user_position, где challenge_id = challenge.id
    user_positions = UserPosition.query.filter_by(challenge_id=challenge.id).all()
    for user_position in user_positions:
        user_position.challenge_id = None  # Обнуляем связь с челленджем

    # Теперь можно безопасно удалить челлендж
    db.session.delete(challenge)
    db.session.commit()

    flash('Спаборніцтва паспяхова выдалена! Стварайце яшчэ!', 'success')
    return redirect(url_for('archive'))


def calculate_daily_distances(participants, start_date, end_date):
    # Словарь для хранения общего расстояния по дням
    daily_total_distances = {}

    for participant in participants:
        # Фильтруем треки по user_id вместо username
        tracks = Track.query.filter_by(user_id=participant.user.id).all()

        # Фильтруем треки по дате
        filtered_tracks = [
            track for track in tracks
            if start_date <= track.record_time.date() <= end_date + timedelta(days=1) # Используем record_time для фильтрации
        ]

        # Группируем треки по дням
        grouped_tracks = groupby(sorted(filtered_tracks, key=lambda x: x.record_time.date()), key=lambda x: x.record_time.date())

        # Суммируем дистанцию для каждого дня
        for date, group in grouped_tracks:
            day_distance = sum(track.distance for track in group)
            if date in daily_total_distances:
                daily_total_distances[date] += day_distance
            else:
                daily_total_distances[date] = day_distance

    # Сортируем по дате (от старой к новой)
    sorted_daily_distances = sorted(daily_total_distances.items(), key=itemgetter(0))

    return sorted_daily_distances


def get_tracks_for_challenge(challenge_id, user_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    start_date = challenge.start_date
    end_date = challenge.end_date

    # Фильтруем только те треки, которые относятся к созданию прогресса (например, с типом 'ride' и в нужном диапазоне дат)
    tracks_info = Track.query.filter_by(user_id=user_id).filter(
        Track.record_time >= start_date,
        Track.record_time <= end_date + timedelta(days=1),
        (Track.type == 'ride') | (Track.type == 'virtualride') | (Track.type.is_(None))  # Фильтрация по типу трека
    ).all()

    return tracks_info

