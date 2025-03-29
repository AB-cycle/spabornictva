from kod import app
from flask import render_template

from kod.models import Challenge

@app.route('/archive')
def archive():
    # Сортировка по дате создания в убывающем порядке
    challenges = Challenge.query.order_by(Challenge.end_date.desc()).all()
    return render_template('archive.html', challenges=challenges)

