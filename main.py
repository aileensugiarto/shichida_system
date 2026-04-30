from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
import os, requests
from db import mysql
from flask_mysqldb import MySQL
from datetime import datetime, date
import webbrowser

from model.admin.auth import model_signup, model_login, model_logout
from model.admin.student import model_student, model_add_student, model_edit_student, model_process_edit_student, model_delete_student
from model.admin.teacher import model_teacher, model_add_teacher, model_edit_teacher, model_process_edit_teacher, model_delete_teacher
from model.admin.schedule import model_schedule, model_add_schedule, model_edit_schedule, model_process_edit_schedule, model_delete_schedule, model_get_attendance, model_update_attendance, model_edit_master_schedule, model_process_edit_master_schedule, model_delete_master_schedule
from model.admin.payment import model_payment, model_edit_payment, model_process_edit_payment, model_delete_payment, model_add_payment, check_registration_status
from model.admin.level import model_level, model_add_level, model_edit_level, model_process_edit_level, model_delete_level
from model.admin.recap import model_recap
from model.admin.account import model_edit_account, model_process_edit_account

from model.director.auth import model_director_signup, model_director_login, model_director_logout
from model.director.branch import model_branch, model_add_branch, model_edit_branch, model_process_edit_branch, model_delete_branch
from model.director.admin import model_admin, model_add_admin, model_edit_admin, model_process_edit_admin, model_delete_admin
from model.director.student import model_director_student
from model.director.teacher import model_director_teacher
from model.director.payment import model_director_payment
from model.director.schedule import model_director_schedule
from model.director.account import model_edit_director_account, model_process_edit_director_account

app = Flask(__name__)

app.secret_key = 'aileen'
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'shichida_system'
app.config['MYSQL_PORT'] = 3306

mysql.init_app(app)

# SIGNUP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
  return model_signup()

# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
  return model_login()

# LOGOUT
@app.route('/logout')
def logout():
  return model_logout()

# EDIT ACCOUNT
@app.route('/edit_account', methods=['GET'])
def edit_account():
    return model_edit_account()

# PROCESS EDIT ACCOUNT
@app.route('/process_edit_account', methods=['POST'])
def process_edit_account():
    return model_process_edit_account()

# DASHBOARD
@app.route('/dashboard')
def dashboard():
  if "loggedin" in session:
    cur = mysql.connection.cursor()

    today = date.today()
    cur.execute("""
      SELECT 
        tbl_schedule.date, 
        tbl_schedule.start_time, 
        tbl_schedule.end_time, 
        tbl_teacher.name AS teacher, 
        tbl_level.level_name,
        GROUP_CONCAT(tbl_student.name SEPARATOR ', ') AS students
      FROM tbl_schedule
      JOIN tbl_teacher ON tbl_schedule.id_teacher = tbl_teacher.id_teacher
      JOIN tbl_level ON tbl_schedule.id_level = tbl_level.id_level
      LEFT JOIN tbl_attendance ON tbl_schedule.id_schedule = tbl_attendance.id_schedule
      LEFT JOIN tbl_student ON tbl_attendance.id_student = tbl_student.id_student
      WHERE tbl_schedule.date = %s 
      AND tbl_schedule.id_admin = %s
      GROUP BY 
        tbl_schedule.date,
        tbl_schedule.start_time,
        tbl_schedule.end_time,
        tbl_teacher.name,
        tbl_level.level_name
      ORDER BY 
        tbl_schedule.start_time ASC
      """, (today, session['id_admin']))
    data = cur.fetchall()

    # Total Students
    cur.execute("SELECT COUNT(id_student) FROM tbl_student WHERE id_admin = %s AND (is_trial IS NULL OR is_trial = 0)", (session['id_admin'], ))
    data_student = cur.fetchone()[0]

    # Total Teachers
    cur.execute("SELECT COUNT(id_teacher) FROM tbl_teacher WHERE id_admin = %s", (session['id_admin'], ))
    data_teacher = cur.fetchone()[0]

    # Total Classes Today
    cur.execute("SELECT COUNT(id_schedule) FROM tbl_schedule WHERE date=%s AND id_admin=%s", (today, session['id_admin'], ))
    data_classes_today = cur.fetchone()[0]

    cur.close()

    return render_template('admin/dashboard.html', total_student=data_student, total_teacher=data_teacher, data_schedule=data, total_classes_today=data_classes_today)

  flash("Please Login", "danger")
  return redirect(url_for('login'))


# STUDENT
@app.route('/student')
def student():
  return model_student()

# ADD STUDENT
@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
  return model_add_student()

# EDIT STUDENT
@app.route('/edit_student/<int:id>', methods=['GET'])
def edit_student(id):
  return model_edit_student(id)

# PROCESS EDIT STUDENT
@app.route('/process_edit_student', methods=['POST'])
def process_edit_student():
  return model_process_edit_student()

# DELETE STUDENT
@app.route('/delete_student/<int:id>', methods=['GET'])
def delete_student(id):
  return model_delete_student(id)


# TEACHER
@app.route('/teacher')
def teacher():
  return model_teacher()

# ADD TEACHER
@app.route('/add_teacher', methods=['GET', 'POST'])
def add_teacher():
  return model_add_teacher()

# EDIT TEACHER
@app.route('/edit_teacher/<int:id>', methods=['GET'])
def edit_teacher(id):
  return model_edit_teacher(id)

# PROCESS EDIT TEACHER
@app.route('/process_edit_teacher', methods=['POST'])
def process_edit_teacher():
  return model_process_edit_teacher()

# DELETE TEACHER
@app.route('/delete_teacher/<int:id>', methods=['GET'])
def delete_teacher(id):
  return model_delete_teacher(id)


# SCHEDULE
@app.route('/schedule')
def schedule():
  return model_schedule()

@app.route ('/add_schedule', methods=['GET', 'POST'])
def add_schedule():
  return model_add_schedule()

@app.route('/edit_schedule/<int:id>', methods=['GET'])
def edit_schedule(id):
  return model_edit_schedule(id)

@app.route('/process_edit_schedule', methods=['POST'])
def process_edit_schedule():
  return model_process_edit_schedule()

@app.route('/edit_master_schedule/<int:id>', methods=['GET'])
def edit_master_schedule(id):
  return model_edit_master_schedule(id)

@app.route('/process_edit_master_schedule', methods=['POST'])
def process_edit_master_schedule():
  return model_process_edit_master_schedule()

@app.route('/delete_schedule/<int:id>', methods=['GET'])
def delete_schedule(id):
  return model_delete_schedule(id)

@app.route('/delete_master_schedule/<int:id>', methods=['GET'])
def delete_master_student(id):
  return model_delete_master_schedule(id)

# @app.route('/reschedule/<int:id>', methods=['GET'])
# def reschedule(id):
#   return model_reschedule(id)
# @app.route('/process_reschedule', methods=['POST'])
# def process_reschedule():
#   return model_process_reschedule()

@app.route('/get_attendance/<int:id>', methods=['GET'])
def get_attendance(id):
  return model_get_attendance(id)
@app.route('/update_attendance', methods=['POST'])
def update_attendance():
  return model_update_attendance()


# PAYMENT
@app.route('/payment')
def payment():
  return model_payment()

# ADD PAYMENT
@app.route('/add_payment', methods=['GET', 'POST'])
def add_payment():
  return model_add_payment()

# EDIT PAYMENT
@app.route('/edit_payment/<int:id>', methods=['GET'])
def edit_payment(id):
  return model_edit_payment(id)

# PROCESS EDIT PAYMENT
@app.route('/process_edit_payment', methods=['POST'])
def process_edit_payment():
  return model_process_edit_payment()

# DELETE PAYMENT
@app.route('/delete_payment/<int:id>', methods=['GET'])
def delete_payment(id):
  return model_delete_payment(id)

app.add_url_rule('/check_registration_status', 'check_registration_status', check_registration_status)
# LEVEL
@app.route('/level')
def level():
  return model_level()

# ADD LEVEL
@app.route('/add_level', methods=['GET', 'POST'])
def add_level():
  return model_add_level()

# EDIT LEVEL
@app.route('/edit_level/<int:id>', methods=['GET'])
def edit_level(id):
  return model_edit_level(id)

# PROCESS EDIT PAYMENT
@app.route('/process_edit_level', methods=['POST'])
def process_edit_level():
  return model_process_edit_level()

# DELETE PAYMENT
@app.route('/delete_level/<int:id>', methods=['GET'])
def delete_level(id):
  return model_delete_level(id)


# RECAP
@app.route('/recap')
def recap():
  return model_recap()


#################################################################################
################################## DIRECTOR #####################################
#################################################################################

# SIGNUP
@app.route('/director_signup', methods=['GET', 'POST'])
def director_signup():
  return model_director_signup()

# LOGIN
@app.route('/director_login', methods=['GET', 'POST'])
def director_login():
  return model_director_login()

# LOGOUT
@app.route('/director_logout')
def director_logout():
  return model_director_logout()


# DASHBOARD DIRECTOR
@app.route('/director_dashboard')
def director_dashboard():
  if "director_loggedin" in session:
    cur = mysql.connection.cursor()

    # Total Students
    cur.execute("SELECT COUNT(s.id_student) FROM tbl_student s JOIN tbl_admin a ON s.id_admin = a.id_admin WHERE a.id_director = %s", (session['id_director'], ))
    data_student = cur.fetchone()[0]

    # Total Teachers
    cur.execute("SELECT COUNT(t.id_teacher) FROM tbl_teacher t JOIN tbl_admin a ON t.id_admin = a.id_admin WHERE a.id_director = %s", (session['id_director'], ))
    data_teacher = cur.fetchone()[0]

    # Total Branches
    cur.execute("SELECT COUNT(id_branch) FROM tbl_branch WHERE id_director = %s", (session['id_director'], ))
    data_branch = cur.fetchone()[0]

    cur.close()

    return render_template(
      'director/dashboard.html',
      total_student=data_student, total_teacher=data_teacher, total_branch=data_branch
      )

  flash("Please Login", "danger")
  return redirect(url_for('director_login'))


# BRANCH
@app.route('/branch')
def branch():
  return model_branch()

# ADD BRANCH
@app.route('/add_branch', methods=['GET', 'POST'])
def add_branch():
  return model_add_branch()

# EDIT BRANCH
@app.route('/edit_branch/<int:id>', methods=['GET'])
def edit_branch(id):
  return model_edit_branch(id)

# PROCESS EDIT BRANCH
@app.route('/process_edit_branch', methods=['POST'])
def process_edit_branch():
  return model_process_edit_branch()

# DELETE BRANCH
@app.route('/delete_branch/<int:id>', methods=['GET'])
def delete_branch(id):
  return model_delete_branch(id)


# ADMIN
@app.route('/admin')
def admin():
  return model_admin()

# ADD ADMIN
@app.route('/add_admin', methods=['GET', 'POST'])
def add_admin():
  return model_add_admin()

# EDIT ADMIN
@app.route('/edit_admin/<int:id>', methods=['GET'])
def edit_admin(id):
  return model_edit_admin(id)

# PROCESS EDIT ADMIN
@app.route('/process_edit_admin', methods=['POST'])
def process_edit_admin():
  return model_process_edit_admin()

# DELETE ADMIN
@app.route('/delete_admin/<int:id>', methods=['GET'])
def delete_admin(id):
  return model_delete_admin(id)


# STUDENT
@app.route('/director_student')
def director_student():
  return model_director_student()


# TEACHER
@app.route('/director_teacher')
def director_teacher():
  return model_director_teacher()


# PAYMENT
@app.route('/director_payment')
def director_payment():
  return model_director_payment()


# SCHEDULE
@app.route('/director_schedule')
def director_schedule():
  return model_director_schedule()

# EDIT DIRECTOR
@app.route('/edit_director_account', methods=['GET'])
def edit_director_account():
    return model_edit_director_account()

# PROCESS EDIT DIRECTOR ACCOUNT
@app.route('/process_edit_director_account', methods=['POST'])
def process_edit_director_account():
    return model_process_edit_director_account()


if __name__ == '__main__':
  # webbrowser.open('http://127.0.0.1:5000/login')
  app.run(debug=True)
  