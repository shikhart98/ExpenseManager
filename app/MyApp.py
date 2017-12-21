from flask import Flask, render_template, flash, request, url_for, redirect, session,  get_flashed_messages
from calendar import Calendar, HTMLCalendar
from flask_sqlalchemy import SQLAlchemy
from Forms.forms import RegistrationForm, LoginForm
from Models._user import User, Budget, Category, Expenditure, db, connect_to_db  #To make Models seperated folder!
from content_manager import Content, CategoriesText
from passlib.hash import sha256_crypt
from functools import wraps
from datetime import datetime
import gc, os
import pygal


app = Flask(__name__)
app.secret_key = os.urandom(24)
file_path = os.path.abspath(os.getcwd())+"/DataBases/test.db"
_database = 'sqlite:///'+file_path
connect_to_db(app,_database)


TOPIC_DICT = Content()
CATS = CategoriesText()

def admin_access_required(f):
	@wraps(f)
	def wrap(*args, **kwargs):
		if session['username'] == 'admin':
			return f(*args, **kwargs)
		else:
			flash("Access Denied, login as admin")
			return redirect(url_for('login_page'))
	return wrap

def login_required(f):
	@wraps(f)
	def wrap(*args, **kwargs):
		if 'logged_in' in session:
			return f(*args,*kwargs)
		else:
			flash('You need to login first!')
			return redirect(url_for('login_page'))
	return wrap

def initialize_categories():
	#check if its not created yet!
	if Category.query.first() == None:

		categories_daily = ['Food', 'Travel', 'Clothing', 'Entertainment', 'Online Shopping']
		categories_monthly = ['Electricity Bill', 'Water Bill', 'Gas', 'Groceries']
		for cat in categories_daily:
			category_obj = Category(category=cat, category_daily=True, category_primary=True)
			db.session.add(category_obj)
			
		for cat in categories_monthly:
			category_obj = Category(category=cat, category_daily=False, category_primary=True)
			db.session.add(category_obj)
		
		db.session.commit()
		db.session.close()
		gc.collect()
		flash("Categories Initialized!")
		return True
	return False

def pie_chart(_categories, _values, _title='Expenditure'):
	pie_chart = pygal.Pie()
	pie_chart.title = _title
	for cat, val in zip(_categories, _values):
		pie_chart.add(cat, val)
	return pie_chart.render_data_uri()

@app.route('/logout/')
@login_required
def logout():
	flash("You have been logged out!")
	session.clear()
	flash("You have been logged out!")
	gc.collect()
	return redirect(url_for('main'))

def verify(_username, _password):
	if User.query.filter_by(username=_username).first() is None:
		flash("No such user found with this username")
		return False
	if not sha256_crypt.verify(_password, User.query.filter_by(username=_username).first().password):
		flash("Invalid Credentials, password isn't correct!")
		return False
	return True

def calculate_expenditure(category_id, userid, today= True):
	sum = 0
	if today:
		for obj in Expenditure.query.filter_by(expenditure_userid= userid).all():
			if obj.category_id == category_id and obj.date_of_expenditure.day == datetime.today().day:
				sum += obj.spent
		return sum
	else:
		for obj in Expenditure.query.filter_by(expenditure_userid= userid).all():
			if obj.category_id == category_id:
				sum += obj.spent
		return sum

@app.route('/', methods=['GET','POST'])
def main():
	#app.logger.debug(get_flashed_messages())
	return render_template('main.html')

@app.route('/dashboard/',methods=['GET','POST'])
@login_required
def dashboard():
	html_cal = HTMLCalendar()
	html_code =  html_cal.formatmonth(datetime.today().year, datetime.today().month, True)
	username = session['username']
	pie_data = pie_chart([cat for cat in CATS['Daily']], [calculate_expenditure(category_object.id, userid=User.query.filter_by(username=username).first().id, today= False) for category_object in Category.query.all()] )

	try:
		if request.method == 'POST':
			initialize_categories()
			if request.form['submit'] == "Set Budget":
				username = session['username']
				_budget_userid = User.query.filter_by(username = username).first().id 
				_budget_amount = request.form['amount']
				_budget_month = datetime.today().month
				_budget_year = datetime.today().year
				budget_object = Budget(budget_userid = _budget_userid, budget_year = _budget_year, budget_month = _budget_month,  budget_amount = _budget_amount)
				db.session.add(budget_object)
				db.session.commit()
				session['current_budget_id'] = budget_object.id
				flash(session['current_budget_id'])
				flash(_budget_userid)
				db.session.close()
				gc.collect()
				flash("Budget Set!")
			
			for key in CATS.keys():
				for cat in CATS[key]:
					if request.form['submit'] == "Set {} amount".format(cat):
						username = session['username']
						_expenditure_userid = User.query.filter_by(username = username).first().id
						_spent = request.form['amount']
						_where_spent = request.form['location']
						_category_id = Category.query.filter_by(category = cat).first().id
						_date_of_expenditure = datetime.today()
						_description = request.form['comment']
						expenditure_object = Expenditure(expenditure_userid = _expenditure_userid, spent = _spent, where_spent= _where_spent, category_id = _category_id, date_of_expenditure = _date_of_expenditure, description = _description)
						db.session.add(expenditure_object)
						db.session.commit()
						db.session.close()
						gc.collect()
						flash("Expenditure recorded of {}!".format(cat))
						if Category.query.filter_by(category = cat).first().category_daily == True:
							flash(calculate_expenditure(_category_id, _expenditure_userid, True))
							return render_template('dashboard.html',CATS = CATS, html_code = html_code, active_tab = 'expense', isDaily=True)
						else:
							flash(calculate_expenditure(_category_id, _expenditure_userid, False))
							return render_template('dashboard.html',CATS = CATS, html_code = html_code, active_tab = 'expense', isDaily=False)
					
			
			return render_template('dashboard.html',CATS = CATS, html_code = html_code, active_tab = 'Home')
		else:
			flash("Welcome!")
			#flash(db.session.query(Budget).all()[-1])
			return render_template('dashboard.html',CATS = CATS, html_code = html_code, active_tab = 'Home', pie_data = pie_data)
	except Exception as e:
		return render_template('error.html',e=e)

@app.route('/login/', methods=['GET','POST'])
def login_page():
	try:
		form = LoginForm(request.form)
		if request.method == 'POST':
			# to create data base first!
			_username = form.username.data
			_password = form.password.data

			# check if username and password are correct
			if verify(_username, _password) is False:
				return render_template('login.html', form=form)
			session['logged_in'] = True
			session['username'] = _username
			gc.collect()
			return redirect(url_for('dashboard'))
			
		return render_template('login.html', form=form)
	except Exception as e:
		return render_template('error.html',e=e)

@app.route('/register/', methods=['GET','POST'])
def register_page():
	try:
		form = RegistrationForm(request.form)
		if request.method == 'POST' and form.validate():
			_username = form.username.data
			_github_username = form.github_username.data
			_email = form.email.data
			_password = sha256_crypt.encrypt(str(form.password.data))
			flash(form.example.data)
			user = User(username = _username, github_username = _github_username, email = _email, password = _password)
			db.create_all()
			if User.query.filter_by(username=_username).first() is not None:
				flash('User Already registered with github username {}'.format(User.query.filter_by(username=_username).first().github_username))
				return render_template('register.html', form=form)
			if User.query.filter_by(email=_email).first() is not None:
				flash('Email is already registered with us with github username {}'.format(User.query.filter_by(email=_email).first().username))
				return render_template('register.html', form=form)
			if User.query.filter_by(github_username=_github_username).first() is not None:
				flash('Email is already registered with us with github username {}'.format(User.query.filter_by(github_username=_github_username).first().username))
				return render_template('register.html', form=form)		
			flash("Thank you for registering!")

			db.session.add(user)
			db.session.commit()
			db.session.close()
			gc.collect()
			session['logged_in'] = True
			session['username'] = _username
			session.modified = True
			return redirect(url_for('dashboard'))
		return render_template('register.html', form=form)
	except Exception as e:
		return render_template('error.html',e=e)

@app.route('/database/', methods=['GET','POST'])
@login_required
@admin_access_required
def database():
	try:
		return render_template('databse.html',data= User.query.first())
	except Exception as e:
		return render_template('error.html',e=e)		


@app.errorhandler(500)
@app.errorhandler(404)
def page_not_found(e):
	return render_template('error.html',e=e)

if __name__ == "__main__":
	db.create_all()
	app.run(debug=True)