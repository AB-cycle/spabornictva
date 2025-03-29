from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from kod import app, db
from kod.models import User

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Страница редактирования профиля."""
    if request.method == 'POST':
        new_name = request.form.get('login')
        new_email = request.form.get('email')

        # Флаг для отслеживания необходимости коммита
        changes_made = False

        # Проверка и обновление имени, если оно изменилось и не пустое
        if new_name is not None and new_name != current_user.login:
            if new_name == "":
                flash('Імя не можа быць пустым.', 'error')
            else:
                current_user.login = new_name
                flash('Імя паспяхова зменена.', 'success')
                changes_made = True

        # Проверка и обновление email, если он изменился и корректный
        if new_email is not None and new_email != current_user.email:
            if "@" not in new_email:
                flash('Некарэктны email.', 'error')
            elif User.query.filter_by(email=new_email).first():
                flash('Email ужо кімсці заняты.', 'error')
            else:
                current_user.email = new_email
                flash('Email паспяхова зменены.', 'success')
                changes_made = True
        elif new_email is not None and not new_email:
            flash('Email ня можы быць пустым.', 'error')

        # Сохранение изменений в базе данных, если есть обновления
        if changes_made:
            try:
                db.session.commit()
                return redirect(url_for('edit_profile'))
            except Exception as e:
                db.session.rollback()
                flash(f'Памылка падчас аднаўлення профіля: {str(e)}', 'error')

    return render_template('edit_profile.html', user=current_user)
