from flask import render_template, url_for, redirect, flash, request, jsonify
from flask_login import login_required, current_user

from kod import app, db
from kod.models import Track

import logging

@app.route('/user_tracks')
@login_required
def all_user_tracks():
    """Страница для отображения всех треков пользователя в хронологическом порядке (от новых к старым)."""
    user_tracks = Track.query.filter(
        Track.user_id == current_user.id,  # Фильтруем по user_id
        (Track.type == 'ride') | (Track.type == 'virtualride') | (Track.type == None)  # Фильтрация по типам
    ).order_by(Track.upload_time.desc()).all()
    
    return render_template('user_tracks.html', tracks=user_tracks)



@app.route('/user/delete_track/<int:track_id>', methods=['POST'])
@login_required
def delete_track_user(track_id):
    """Удаление трека пользователем."""
    logging.debug('Запрос на удаление трека с ID: %s', track_id)
    track = Track.query.get_or_404(track_id)

    # Проверяем, является ли текущий пользователь владельцем трека
    if track.user_id != current_user.id:  # Заменили track.username на track.user_id
        flash("Вы не можаце выдаліць гэты трэк.", "danger")
        logging.warning('Вы хочаце выдаліць трэк, які вам не належыць, а належыць: %s', current_user.login)
        return redirect(url_for('all_user_tracks'))
    
    # Удаляем трек из базы данных
    db.session.delete(track)
    db.session.commit()
    
    flash("Трэк паспяхова выдалены.", "success")
    logging.info('Трэк з ID %s паспяхова выдалены карыстальнікам %s.', track_id, current_user.login)
    return redirect(url_for('all_user_tracks'))


@app.route('/update_track_name', methods=['POST'])
@login_required
def update_track_name():
    """Обновляет название трека."""
    data = request.get_json()
    track_id = data.get('track_id')
    new_name = data.get('new_name')

    logging.debug(f'Запрос на обновление трека с ID {track_id} до нового имени "{new_name}"')

    if not track_id or not new_name:
        return jsonify({'error': 'Отсутствуют данные для обновления'}), 400

    track = Track.query.get(track_id)

    if not track:
        logging.error(f'Трек с ID {track_id} не найден')
        return jsonify({'error': 'Трек не найден'}), 404

    # Проверка прав доступа
    if track.user_id != current_user.id:  # Здесь мы сравниваем числовые идентификаторы
        logging.warning(f'Попытка изменения трека {track_id} не владельцем {current_user.id}')
        return jsonify({'error': 'У вас нет прав на изменение этого трека'}), 403

    track.name_track = new_name
    db.session.commit()

    logging.info(f'Трек с ID {track_id} успешно обновлен до нового имени "{new_name}"')
    return jsonify({'success': 'Название трека обновлено', 'new_name': new_name}), 200
