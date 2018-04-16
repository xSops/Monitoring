#!/usr/bin/python3.5

from flask import Flask, request, g, url_for, session, \
	render_template, redirect
import mysql.connector
from passlib.hash import argon2
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import requests
import atexit
import datetime

app = Flask(__name__)
app.config.from_object('config')
app.config.from_object('secret_config')


def commit():
	g.mysql_connection.commit()

def connect_db():
	g.mysql_connection = mysql.connector.connect(
		host=app.config['DATABASE_HOST'],
		user=app.config['DATABASE_USER'],
		password=app.config['DATABASE_PASSWORD'],
		database=app.config['DATABASE_NAME'],
		)

	g.mysql_cursor = g.mysql_connection.cursor()
	return g.mysql_cursor

def get_status(url):
    status_code = 999
    try:
        r = requests.get(url, timeout=4)
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

def status():
    with app.app_context():
        db = get_db()
        db.execute('SELECT id, url FROM websitelist')
        sites = db.fetchall()
        for website in websitelist:
            id = website[0]
            url = website[1]
            status = get_status(url)
            now = datetime.datetime.now()
            date = now.strftime('%Y-%m-%d %H:%M:%S')
            if (int(status) != 200):
                erreur = "Une erreur à été rencontrée sur votre site"
            db = get_db()
            db.execute('INSERT INTO historic (website, last_request, answer) VALUES (%(id)s, %(date)s, %(status)s)', {'id': id, 'date': date, 'status': status})
        commit()


scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(
    func=status,
    trigger=IntervalTrigger(seconds=30),
    id='status',
    name='Ajout status',
    replace_existing=True)
atexit.register(lambda: scheduler.shutdown())


def get_db():
	if not hasattr(g, 'db'):
		g.db = connect_db()
	return g.db


def get_database():
	cnx = mysql.connector.connect(
		host=app.config['DATABASE_HOST'],
		user=app.config['DATABASE_USER'],
		password=app.config['DATABASE_PASSWORD'],
		database=app.config['DATABASE_NAME'],
		)
	cursor = cnx.cursor()
	return cnx, cursor

def insert_results(query):
	try:
		db = get_db()
		db.execute(query)
		commit()
		return True
	except Exception as e:
		return False

def get_results(query):
	try:
		db, cursor = get_database()
		cursor.execute(query)
		results = cursor.fetchall()
		return results
	except Exception as e:
		print(e)
		return None



@app.route('/addwebsite/', methods=['GET', 'POST'])
def addwebsite():
	if not session['auth_user']:
		return redirect(url_for('login'))
	if request.method == 'POST':
		html = str(request.form.get('Page'))
		db = get_db()
		#gd = get_database()
		#gd.execute('INSERT INTO websitelist (url) values (%(html)s)', {'html' : html})
		db.execute('INSERT INTO websitelist (url) VALUES (%(html)s)', {'html' : html})
		commit()
		return redirect(url_for('admin'))
	return render_template('addwebsite.html')

@app.route('/edit/<int:id>', methods=['GET','POST'])
def modif(id):

	db = get_db()
	if not session['auth_user']:
		return redirect(url_for('login'))
	if request.method == 'POST':
		html = str(request.form.get('Page'))
		#gd = get_database()
		#gd.execute('UPDATE websitelist SET url = %(html)s WHERE id = %(id)s', {'id': id})
		db.execute('UPDATE websitelist SET url = %(html)s WHERE id = %(id)s', {'html' : html, 'id': id})
		commit()
		return redirect(url_for('admin'))
	else:
		db.execute('SELECT id, url FROM websitelist WHERE id = %(id)s', {'id' : id})		
		sites = db.fetchone()
		return render_template('edit.html', auth_user=session['auth_user'], sites = sites)

@app.route('/admin/')
def admin():
	if not session['auth_user']:
		return redirect(url_for('login'))

	db = get_db()
	#gd = get_database()
	db.execute('SELECT id, url FROM websitelist')
	sites = db.fetchall()

	return render_template('admin.html', auth_user=session['auth_user'], sites = sites)



@app.route('/login/', methods=['GET', 'POST'])
def login():
	if request.method == 'GET':
		return render_template('login.html')
	
	email = request.form.get('email')
	password = request.form.get('password')
	
	print("email={}, password={}".format(email, password))
	
	users = get_results("""
		SELECT email, password FROM users
		WHERE email = "{}"
		""".format(email))
	if not users:
		return render_template('login.html', message="Invalid id.")
	for user in users:
		if argon2.verify(password, user[1]):
			session['auth_user'] = user[0]
			return redirect(url_for('admin'))
	return render_template('login.html', message="Invalid id.")

@app.route('/logout/')
def logout():
	session.clear()
	return redirect(url_for('index'))



@app.route('/')
def index():
	
	db = get_db()
	#gd = get_database()
	db.execute('SELECT h.answer, w.url, w.id FROM websitelist w, historic h WHERE w.id = h.website and h.last_request=(SELECT MAX(last_request) from historic hi where hi.website = w.id) GROUP BY w.id, w.url, h.answer') 
	listes = db.fetchall()
	return render_template("index.html", listes = listes)

@app.route('/listsite/<int:id>/')
def idlist(id):
	db = get_db()
	#gd = get_database()
	db.execute('SELECT w.url, h.answer, h.last_request from websitelist w, historic h WHERE w.id = h.website AND w.id = %(id)w ORDER BY last_request DESC', {'id': id}) 
	status = db.fetchall()
	return render_template("statuslist.html", status = status)


#@app.route('/admin/add' methods=['GET', 'POST'])
@app.route('/delete/<int:id>', methods=['GET', 'POST'])
def delete(id):
	if not session['auth_user']:
		return redirect(url_for('login'))
	if request.method == 'POST':
		db = get_db()
		db.execute('DELETE FROM websitelist WHERE id = %(id)s', {'id': id})
		commit()
		return redirect(url_for('admin'))
	else:
		db = get_db()
		db.execute('SELECT id, url FROM websitelist WHERE id = %(id)s', {'id': id})
		sites = db.fetchone()
		return render_template('delete.html', auth_user=session['auth_user'], sites = sites)

if __name__ == "__main__":
	app.run(debug=True, host='0.0.0.0')