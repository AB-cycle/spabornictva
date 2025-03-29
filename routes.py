from flask import render_template, redirect, url_for, request, session, flash
from flask_login import login_user, login_required, logout_user, LoginManager
from werkzeug.security import check_password_hash, generate_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadData
from flask_mail import Message
from sqlalchemy.exc import SQLAlchemyError
from kod import app, db, mail
from kod.models import User, Challenge, ChallengeParticipants

from kod.statistics import count_challenges, count_total_distance, count_tracks, count_users

login_manager = LoginManager()
login_manager.init_app(app)

# Указываем страницу логина
login_manager.login_view = 'login_page'

# Сообщение для неавторизованных пользователей
login_manager.login_message_category = "warning"

# Инициализация сериализатора для создания токенов
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

@app.route('/')
def home():
    try:
        app.logger.debug("Соединение с базой данных: начало запроса к Challenge и ChallengeParticipants")

        # Статистика
        users_count = count_users()
        tracks_count = count_tracks()
        challenges_count = count_challenges()
        total_distance = count_total_distance()

        # Челленджи
        challenges = Challenge.query.all()

        challenges_data = []
        for challenge in challenges:
            creator = User.query.get(challenge.creator_id)
            challenge_total_distance = sum(participant.get_total_distance() for participant in challenge.participants)
            participants_count = ChallengeParticipants.query.filter_by(challenge_id=challenge.id).count()

            challenges_data.append({
                'challenge': challenge,
                'creator': creator,
                'total_distance': challenge_total_distance,
                'participants_count': participants_count  # Добавляем количество участников
            })

        app.logger.debug("Запрос к базе данных завершён успешно.")

        # Передача статистики и данных о челленджах
        return render_template(
            'home.html',
            challenges=challenges_data,
            stats={  # Передаем статистику в шаблон
                'users_count': users_count,
                'tracks_count': tracks_count,
                'challenges_count': challenges_count,
                'total_distance': total_distance  # Общее расстояние для всех треков
            }
        )
    except SQLAlchemyError as e:
        db.session.rollback()  # Откатываем транзакцию при ошибке
        app.logger.error(f"Ошибка при работе с базой данных: {e}")
        flash('Ошибка при работе с базой данных.', 'error')
        return render_template('home.html', challenges=[], stats={})
    finally:
        db.session.remove()  # Закрытие сессии
        app.logger.debug("Сессия с базой данных закрыта.")


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    next_page = request.args.get('next')  # Получаем, куда нужно вернуться после входа
    login = request.form.get('login')
    password = request.form.get('password')
    error = None

    try:
        if login and password:
            user = User.query.filter_by(login=login).first()
            if user and check_password_hash(user.password, password):
                login_user(user, remember=True)
                session['id'] = user.login
                app.logger.info(f'Пользователь {session["id"]} вошел в систему.')

                    # Добавляем лог для отладки
                app.logger.info(f"После логина session['id']: {session.get('id')}")

                 # Логируем, куда будет идти редирект
                app.logger.info(f"Redirecting to: {next_page if next_page else url_for('profile')}")

                # Перенаправляем на страницу, откуда пришёл пользователь
                return redirect(next_page) if next_page else redirect(url_for('profile'))

            else:
                error = 'Хібны логін ці пароль!'
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Ошибка при работе с базой данных: {e}")
        error = 'Ошибка при работе с базой данных.'
    finally:
        db.session.remove()

    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    login = request.form.get('login')
    email = request.form.get('email')  # Получаем email
    password = request.form.get('password')
    password2 = request.form.get('password2')
    error = None

    if request.method == 'POST':
        try:
            app.logger.debug("Соединение с базой данных: начало запроса для регистрации нового пользователя")
            if not (login and password and password2 and email):  # Добавляем проверку на email
                error = 'Калі ласка, запоўніце ўсе палі!'
            elif password != password2:
                error = 'Паролі не супадаюць!'
            else:
                existing_user = User.query.filter_by(email=email).first()
                if existing_user:
                    error = 'Гэты email ўжо зарэгістраваны!'
                else:
                    hash_pwd = generate_password_hash(password)
                    new_user = User(login=login, email=email, password=hash_pwd)
                    db.session.add(new_user)
                    db.session.commit()
                    flash('Вы зарэгістраваліся! Цяпер можаце ўвайсці на старонку!', 'success')
                    app.logger.debug("Новый пользователь зарегистрирован и изменения сохранены в базе данных.")
                    return redirect(url_for('login_page'))
        except SQLAlchemyError as e:
            db.session.rollback()
            app.logger.error(f"Ошибка при работе с базой данных: {e}")
            error = 'Ошибка при работе с базой данных.'
        finally:
            db.session.remove()  # Закрытие сессии
            app.logger.debug("Сессия с базой данных закрыта.")

    return render_template('register.html', error=error)

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    app.logger.debug(f"Пользователь {session['id']} вышел из системы.")
    logout_user()
    return redirect(url_for('home'))

@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            # Генерация токена сброса пароля
            token = serializer.dumps(email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)

            # Отправка email с ссылкой на сброс пароля
            msg = Message("Змена паролю ў спаборніцтвах", recipients=[email])
            msg.body = f"Вітаем! Калі ласка, перайдзіце па гэтай спасылцы для змены паролю: {reset_url}"
            mail.send(msg)

            flash('Спасылка для аднаўлення паролю была выслана на ваш email.', 'info')
            app.logger.debug(f"Ссылка для сброса пароля отправлена на email {email}.")
            return render_template('reset_password_request.html')
        else:
            flash('Раварыста з такім email не знойдзены.', 'error')

    return render_template('reset_password_request.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        # Проверка токена и извлечение email
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)  # max_age можно настроить по необходимости
    except (SignatureExpired, BadData):
        flash('Срок действия токена истёк или токен недействителен.', 'error')
        return redirect(url_for('reset_password_request'))

    if request.method == 'POST':
        password = request.form.get('password')
        password2 = request.form.get('password2')

        if password != password2:
            flash('Паролі не супадаюць!', 'error')
            return render_template('reset_password.html', token=token)

        # Обновление пароля пользователя
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = generate_password_hash(password)
            db.session.commit()
            flash('Пароль паспяхова адноўлены!', 'success')
            app.logger.debug(f"Пароль пользователя с email {email} успешно обновлён.")
            return render_template('reset_password.html', token=token)
        else:
            flash('Раварыст з такім email не знойдзены!', 'error')

    return render_template('reset_password.html', token=token)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))