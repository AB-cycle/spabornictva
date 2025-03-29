from kod import app, db
from flask import redirect, url_for, render_template, flash, request
from flask_login import current_user
from functools import wraps

from kod.models import Track, User

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('home'))
        elif not current_user.is_admin:
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/all_tracks')
@admin_required  # Проверка админских прав
def all_tracks():
    tracks = Track.query.order_by(Track.upload_time.desc()).all()  # Сортировка по upload_time (от новых к старым)
    
    # Получаем логины пользователей для каждого трека
    tracks_with_user = []
    for track in tracks:
        user = User.query.filter_by(id=track.user_id).first()  # Получаем пользователя по user_id
        user_login = user.login if user else 'Неизвестный пользователь'
        tracks_with_user.append({
            'id': track.id,
            'user_login': user_login,
            'filename': track.filename,
            'distance': track.distance,
            'record_time': track.record_time,
            'upload_time': track.upload_time,
            'type': track.type,
            'duration': track.duration
        })

    return render_template('all_tracks.html', tracks=tracks_with_user)


@app.route('/delete_track/<int:track_id>', methods=['POST'])
@admin_required
def delete_track(track_id):
    track = Track.query.get(track_id)
    if track:
        db.session.delete(track)
        db.session.commit()
        flash('Трек успешно удален.', 'success')
    else:
        flash('Трек не найден.', 'danger')
    return redirect(url_for('all_tracks'))

@app.route('/delete_tracks', methods=['POST'])
@admin_required
def delete_tracks():
    track_ids = request.form.getlist('track_ids')  # Получаем список выбранных ID треков
    if not track_ids:
        flash('Не выбраны треки для удаления.', 'danger')
        return redirect(url_for('all_tracks'))

    # Преобразуем ID в целые числа
    track_ids = [int(track_id) for track_id in track_ids]

    # Получаем все треки с этими ID
    tracks_to_delete = Track.query.filter(Track.id.in_(track_ids)).all()

    if not tracks_to_delete:
        flash('Треки не найдены для удаления.', 'danger')
        return redirect(url_for('all_tracks'))

    # Удаляем все найденные треки
    for track in tracks_to_delete:
        db.session.delete(track)
    db.session.commit()

    flash(f'{len(tracks_to_delete)} треков успешно удалено.', 'success')
    return redirect(url_for('all_tracks'))
