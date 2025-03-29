from flask import render_template, jsonify

from kod import app, db
from kod.models import UserPosition, User, Challenge, ChallengeParticipants

@app.route('/user_positions/<int:user_id>/<int:challenge_id>')
def user_positions_by_user(user_id, challenge_id):
    """Отображение истории позиций для конкретного участника в конкретном челлендже."""
    user = User.query.get_or_404(user_id)
    challenge = Challenge.query.get_or_404(challenge_id)

    # Сортировка от новых к старым
    positions = UserPosition.query.filter_by(user_id=user_id, challenge_id=challenge_id).order_by(UserPosition.date_position.desc()).all()

    # Вычисление минимальной и максимальной позиции
    min_position = db.session.query(db.func.min(UserPosition.position)).filter_by(user_id=user_id, challenge_id=challenge_id).scalar()
    max_position = db.session.query(db.func.max(UserPosition.position)).filter_by(user_id=user_id, challenge_id=challenge_id).scalar()

    return render_template(
        'user_positions.html',
        positions=positions,
        user=user,
        challenge=challenge,
        min_position=min_position,
        max_position=max_position,
    )

@app.route('/get_positions_data/<int:user_id>/<int:challenge_id>', methods=['GET'])
def get_positions_data(user_id, challenge_id):
    try:
        # Извлекаем позиции для пользователя по заданному челленджу
        positions = UserPosition.query.filter_by(user_id=user_id, challenge_id=challenge_id).order_by(UserPosition.date_position).all()

        # Получаем количество уникальных участников в челлендже
        num_participants = db.session.query(ChallengeParticipants.user_id).filter_by(challenge_id=challenge_id).distinct().count()

        # Подготовка данных для графика
        timestamps = []
        positions_data = []

        for position in positions:
            # Пропускаем записи, где дата или позиция отсутствуют
            if position.date_position and position.position is not None:
                timestamps.append(position.date_position.strftime('%Y-%m-%d %H:%M:%S'))
                positions_data.append(position.position)

        # Переворачиваем данные, чтобы самая первая позиция была сверху
        timestamps.reverse()
        positions_data.reverse()

        # Отправляем данные как JSON
        return jsonify({
            'timestamps': timestamps,
            'positions_data': positions_data,
            'num_participants': num_participants  # Отправляем количество участников
        })
    except Exception as e:
        print(f"Error in get_positions_data: {str(e)}")
        return jsonify({'error': str(e)}), 500  # Отправляем ошибку в ответ

