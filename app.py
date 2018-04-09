#! /usr/bin/python3.5
# -*- coding:utf-8 -*-


from flask import Flask, render_template, request, g, session, url_for
from flask import redirect
import requests
import mysql.connector
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
import datetime


# Construct app
app = Flask(__name__)
app.config.from_object('config')
app.config.from_object('secret_config')


# Database functions
def connect_db () :
    g.mysql_connection = mysql.connector.connect(
        host=app.config['DATABASE_HOST'],
        user=app.config['DATABASE_USER'],
        password=app.config['DATABASE_PASSWORD'],
        database=app.config['DATABASE_NAME']
    )

    g.mysql_cursor = g.mysql_connection.cursor()
    return g.mysql_cursor


def get_db():
    if not hasattr(g, 'db'):
        g.db = connect_db()
    return g.db


def commit():
    g.mysql_connection.commit()

# historique fonction
def Recup_status(adresse):
    status_code = 999
    try:
        r = requests.get(adresse, timeout=60)
        r.raise_for_status()
        status_code = r.status_code
    except requests.exceptions.HTTPError as errh:
        status_code = r.status_code
    except requests.exceptions.ConnectionError as errc:
        pass
    except requests.exceptions.Timeout as errt:
        pass
    except requests.exceptions.RequestException as err:
        pass
    return str(status_code)


def status_all():
    with app.app_context():
        db = get_db()
        db.execute('SELECT id, url FROM url')
        site = db.fetchall()
        f = "%Y-%m-%d %H:%M:%S"
        for site in site:
            id = site[0]
            adresse_web = site[1]
            status = Recup_status(adresse_web)
            dateTime = datetime.datetime.now()
            date = dateTime.strftime(f)

            db = get_db()
            db.execute('INSERT INTO historique (id_web, reponse_requete, date_derniere_requete) VALUES (%(id)s, %(status)s, %(date_requete)s)', {'id': id, 'status': status, 'date_requete': date})
        commit()


scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(
    func=status_all,
    trigger=IntervalTrigger(seconds=5),
    id='status_all',
    name='Ajout status',
    replace_existing=True)
atexit.register(lambda: scheduler.shutdown())


@app.teardown_appcontext
def close_db (error) :
    if hasattr(g, 'db'):
        g.db.close()


# Pages
@app.route('/')
def index():
    db = get_db()
    db.execute('SELECT u.id, u.url, h.reponse_requete from historique h, url u where h.id_web = u.id group by u.id, u.url, h.reponse_requete having max(h.date_derniere_requete)')
    sites = db.fetchall()
    return render_template('index.html', site=sites)


# Pages
@app.route('/ajout', methods=['GET', 'POST'])
def ajout():
    if request.method == 'POST':
        dataLink = request.form.get('url')
        cnx = mysql.connector.connect(user='root', password='root', database='flask')
        cursor = cnx.cursor()
        query = "INSERT INTO url VALUES ('', '%s')" % (dataLink)
        cursor.execute(query)
        cnx.commit()

        return redirect(url_for('admin'))
    if request.method == 'GET':
        return render_template('ajout.html')


@app.route('/fiche/<int:id>/')
def fiche(id):
    if request.method == 'GET':
        db = get_db()
        db.execute('SELECT u.url, h.reponse_requete, h.date_derniere_requete FROM url u, historique h WHERE u.id=h.id_web AND u.id=%(id)s', {'id':id})
        logs = db.fetchall()
        return render_template('fiche.html', logs=logs)



@app.route('/login/', methods=['GET', 'POST'])
def login():
    email = str(request.form.get('email'))
    password = str(request.form.get('password'))

    db = get_db()
    db.execute('SELECT email, password, is_admin FROM user WHERE email = %(email)s', {'email': email})
    users = db.fetchall()

    valid_user = False
    for user in users:
            valid_user = user
    if valid_user:
        session['user'] = valid_user
        return redirect(url_for('admin'))

    return render_template('login.html')


@app.route('/admin/', methods=['GET', 'POST'])
def admin():
    if not session.get('user') or not session.get('user')[2]:
        return redirect(url_for('login'))
    db = get_db()
    db.execute('SELECT * FROM url')
    sites = db.fetchall()

    return render_template('admin.html', user=session['user'], sites=sites)


@app.route('/admin/remove/<id>/')
def delete(id):
    if request.method == 'GET':
        db = get_db()
        db.execute('SELECT * FROM url')
        sites = db.fetchall()
        cnx = mysql.connector.connect(user='root', password='root', database='flask')
        cursor = cnx.cursor()
        print(sites[0][0])
        query = "DELETE FROM url WHERE id=%s" % (id)
        cursor.execute(query)
        cnx.commit()
        return redirect(url_for('admin', user=session['user'], id=id))


@app.route('/admin/update/<id>/',methods=['GET', 'POST'] )
def modif(id):
    db = get_db()
    if request.method == 'POST':
        url = str(request.form.get('edit'))
        query_data = {'link': url, 'id': id}
        db.execute('UPDATE url SET url = %(link)s WHERE id = %(id)s', query_data)
        commit()
        return redirect(url_for('admin'))
    else:
        query = 'select id, url from url where url.id = %(website.id)s'
        db.execute(query, {'website.id': id})
        website = db.fetchone()
        return render_template('edit.html')


@app.route('/admin/logout/')
def admin_logout():
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
