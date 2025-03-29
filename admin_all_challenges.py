from kod import app, db
from flask import render_template, redirect, url_for, flash
from flask_login import current_user
from functools import wraps

from kod.models import Challenge, UserPosition, Comment

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('home'))
        elif not current_user.is_admin:
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/all_challenges')
@admin_required  # Проверка админских прав
def all_challenges():
    challenges = Challenge.query.all()  # Получаем все треки
    return render_template('all_challenges.html', challenges=challenges)

@app.route('/delete_challenge/<int:challenge_id>', methods=['POST'])
@admin_required
def delete_challenge(challenge_id):
    challenge = Challenge.query.get(challenge_id)
    
    if challenge:
        # Удаляем все записи в таблице user_position, связанные с этим челенджем
        UserPosition.query.filter_by(challenge_id=challenge_id).delete(synchronize_session=False)

        # Удаляем все комментарии, связанные с челенджем
        Comment.query.filter_by(challenge_id=challenge_id).delete(synchronize_session=False)
        
        # Удаляем челендж
        db.session.delete(challenge)
        db.session.commit()
        
        flash('Спаборніцтва выдалена.', 'success')
    else:
        flash('Челендж не найден.', 'danger')
    
    return redirect(url_for('all_challenges'))



@app.route('/challenge/<int:challenge_id>/remove', methods=['POST'])
@admin_required
def remove_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    challenge.is_closed = False
    db.session.commit()
    flash('Чэлендж закрыт для новых участников.', 'success')
    return redirect(url_for('challenge_detail', challenge_id=challenge_id))