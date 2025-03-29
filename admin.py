from kod import app
from flask import redirect, url_for, render_template
from flask_login import current_user
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('home'))
        elif not current_user.is_admin:
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin')
@admin_required  # Проверка админских прав
def admin_dashboard():
    return render_template('admin.html')


