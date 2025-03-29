from flask import render_template, flash, url_for, redirect
from flask_login import login_required, current_user
import logging
from datetime import datetime, date
from kod import db, app
from kod.models import ChallengeParticipants, Track, UserPosition, Challenge

def update_user_positions(challenge_id):
    try:
        participants = ChallengeParticipants.query.filter_by(challenge_id=challenge_id).all()
        challenge = Challenge.query.get(challenge_id)
        start_date = challenge.start_date
        end_date = challenge.end_date

        current_positions = {}

        # Собираем общее расстояние для каждого участника
        for participant in participants:
            # Фильтруем треки по типу (ride, virtualride или NULL)
            tracks = Track.query.filter_by(user_id=participant.user_id).filter(
                Track.record_time >= start_date, Track.record_time <= end_date
            ).filter(
                (Track.type == 'ride') | (Track.type == 'virtualride') | (Track.type == None)
            ).all()

            # Рассчитываем общее расстояние участника
            total_distance = sum(track.distance for track in tracks if track.distance > 0)
            current_positions[participant.user_id] = total_distance


        # Сортируем участников по расстоянию (по убыванию)
        sorted_participants = sorted(current_positions.items(), key=lambda x: (-x[1], x[0]))

        # Обновляем позиции в базе данных, используя индекс после сортировки
        for idx, (user_id, _) in enumerate(sorted_participants):
            new_position = idx + 1  # Позиция равна индексу в списке + 1

            last_position = (
                UserPosition.query.filter_by(user_id=user_id, challenge_id=challenge_id)
                .order_by(UserPosition.date_position.desc())
                .first()
            )

            # Проверяем, изменялась ли позиция
            if not last_position or last_position.position != new_position:
                new_user_position = UserPosition(
                    user_id=user_id,
                    challenge_id=challenge_id,
                    position=new_position,
                    date_position=datetime.now()
                )
                db.session.add(new_user_position)
                logging.info(f"Новая позиция для пользователя {user_id} ({new_position}) записана для челленджа с ID: {challenge_id}")

        db.session.commit()
        logging.info(f"Все позиции успешно обновлены для челленджа с ID: {challenge_id}")
    except Exception as e:
        logging.error(f"Ошибка при обновлении позиций для челленджа с ID: {challenge_id}: {e}")
        db.session.rollback()

@app.route('/challenge/<int:challenge_id>/detail', endpoint='challenge_detail_page')
def challenge_detail(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)

    # Обновляем позиции участников
    update_user_positions(challenge_id)

    participants = ChallengeParticipants.query.filter_by(challenge_id=challenge_id).all()

    # Собираем данные участников для отображения
    participants_data = []
    today = date.today()

    for participant in participants:
        # Получаем последнюю запись за сегодняшний день
        last_position_today = (
            UserPosition.query.filter_by(user_id=participant.user_id, challenge_id=challenge_id)
            .filter(UserPosition.date_position >= datetime.combine(today, datetime.min.time()))
            .filter(UserPosition.date_position <= datetime.combine(today, datetime.max.time()))
            .order_by(UserPosition.date_position.desc())
            .first()
        )

        # Получаем последнюю запись до сегодняшнего дня
        last_position_before_today = (
            UserPosition.query.filter_by(user_id=participant.user_id, challenge_id=challenge_id)
            .filter(UserPosition.date_position < datetime.combine(today, datetime.min.time()))
            .order_by(UserPosition.date_position.desc())
            .first()
        )

        # Инициализация переменных для вычисления изменения позиции
        position_change = 0
        arrow = None

        if last_position_today and last_position_before_today:
            position_change = last_position_today.position - last_position_before_today.position

        if position_change > 0:
            arrow = "down-arrow"  # Ухудшение позиции (передвинулся вниз)
        elif position_change < 0:
            arrow = "up-arrow"  # Улучшение позиции (передвинулся вверх)

        # Логируем изменения позиции
        logging.info(f"Изменение позиции для участника {participant.user_id}: {position_change}")

        # Добавляем участника в список
        participants_data.append({
            'participant': participant,
            'arrow': arrow,
            'position_change': abs(position_change),
        })

    return render_template(
        'challenge_detail.html',
        participants=participants_data,
        challenge=challenge
    )

