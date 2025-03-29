from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from kod import app, db
from kod.models import Comment, Challenge

@app.route('/challenge/<int:challenge_id>', methods=['GET', 'POST'])
@login_required
def add_comment(challenge_id):
    """Добавление, редактирование и удаление комментариев к челленджу и отображение комментариев на странице челенджа."""

    # Получаем информацию о челендже
    challenge = Challenge.query.get_or_404(challenge_id)
    # Получаем все комментарии для текущего челленджа
    comments = Comment.query.filter_by(challenge_id=challenge_id).all()

    if request.method == 'POST':
        user_comment = request.form.get('user_comment')
        comment_id = request.form.get('comment_id')

        # Если comment_id существует, значит мы редактируем комментарий
        if comment_id:
            comment = Comment.query.get_or_404(comment_id)
            if comment.user_id == current_user.id:  # Проверяем, что пользователь — автор комментария
                comment.user_comment = user_comment
                db.session.commit()
                flash('Комментарий обновлен!', 'success')
            else:
                flash('Вы не можете редактировать чужой комментарий.', 'danger')
        else:
            # Создание нового комментария
            if user_comment:
                app.logger.debug(f"Добавление комментария: {user_comment}")
                new_comment = Comment(
                    user_id=current_user.id,
                    challenge_id=challenge_id,
                    user_comment=user_comment
                )
                db.session.add(new_comment)
                db.session.commit()
                flash('Комментарий добавлен!', 'success')


        # Перенаправление обратно на страницу с челенджем
        return redirect(url_for('add_comment', challenge_id=challenge_id))

    # Рендерим страницу с деталями челенджа и комментариями
    return render_template('challenge_detail.html', challenge=challenge, comments=comments)

@app.route('/comment/delete/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    """Удаление комментария."""
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id == current_user.id:  # Проверяем, что пользователь — автор комментария
        db.session.delete(comment)
        db.session.commit()
        flash('Комментарий удален!', 'success')
    else:
        flash('Вы не можете удалить чужой комментарий.', 'danger')
    
    return redirect(url_for('add_comment', challenge_id=comment.challenge_id))
