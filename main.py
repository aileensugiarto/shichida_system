from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
import os, requests
from db import mysql
from flask_mysqldb import MySQL
from datetime import datetime, date
from zoneinfo import ZoneInfo

from model.admin.auth import model_signup, model_login, model_logout, login_required
from model.admin.student import model_student, model_add_student, model_edit_student, model_process_edit_student, model_delete_student
from model.admin.teacher import model_teacher, model_add_teacher, model_edit_teacher, model_process_edit_teacher, model_delete_teacher
# from model.admin.schedule import model_schedule, model_add_schedule, model_edit_schedule, model_process_edit_schedule, model_delete_schedule, model_get_attendance, model_update_attendance, model_edit_master_schedule, model_process_edit_master_schedule, model_delete_master_schedule, model_get_attendance_by_attendance, model_print_schedule
from model.admin.schedule import (
    model_schedule,
    model_add_teacher_schedule,
    model_edit_teacher_schedule,
    model_delete_teacher_schedule,
    model_get_schedule_students,
    model_get_student_attendance,
    model_get_student_attendance_record,
    model_save_student_attendance,
    model_delete_student_attendance,
    model_print_schedule
)
from model.admin.payment import model_payment, model_edit_payment, model_process_edit_payment, model_delete_payment, model_add_payment, check_registration_status
from model.admin.level import model_level, model_add_level, model_edit_level, model_process_edit_level, model_delete_level
from model.admin.recap import model_recap
from model.admin.account import model_edit_account, model_process_edit_account
from model.admin.trial import model_trial, model_edit_trial, model_process_edit_trial, model_delete_trial, model_add_trial

from model.director.auth import model_director_signup, model_director_login, model_director_logout, login_required_director
from model.director.branch import model_branch, model_add_branch, model_edit_branch, model_process_edit_branch, model_delete_branch
from model.director.admin import model_admin, model_add_admin, model_edit_admin, model_process_edit_admin, model_delete_admin
from model.director.student import model_director_student
from model.director.teacher import model_director_teacher
from model.director.payment import model_director_payment
from model.director.schedule import model_director_schedule
from model.director.account import model_edit_director_account, model_process_edit_director_account

# from model.teacher.teacher_schedule_ori import model_teacher_schedule
from model.teacher.teacher_schedule import model_teacher_schedule

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
@login_required
def edit_account():
    return model_edit_account()

# PROCESS EDIT ACCOUNT
@app.route('/process_edit_account', methods=['POST'])
@login_required
def process_edit_account():
    return model_process_edit_account()

# DASHBOARD
# @app.route('/dashboard_admin')
# @login_required
# def dashboard_admin():
#   if "loggedin" in session:
#     cur = mysql.connection.cursor()

#     today = datetime.now(ZoneInfo("Asia/Jakarta")).date()
#     cur.execute("""
#       SELECT 
#         tbl_schedule.date, 
#         tbl_schedule.start_time, 
#         tbl_schedule.end_time, 
#         tbl_teacher.name AS teacher, 
#         tbl_level.level_name,
#         GROUP_CONCAT(tbl_student.name SEPARATOR ', ') AS students
#       FROM tbl_schedule
#       JOIN tbl_teacher ON tbl_schedule.id_teacher = tbl_teacher.id_teacher
#       JOIN tbl_level ON tbl_schedule.id_level = tbl_level.id_level
#       LEFT JOIN tbl_attendance ON tbl_schedule.id_schedule = tbl_attendance.id_schedule
#       LEFT JOIN tbl_student ON tbl_attendance.id_student = tbl_student.id_student
#       WHERE tbl_schedule.date = %s 
#       AND tbl_schedule.id_admin = %s
#       GROUP BY 
#         tbl_schedule.date,
#         tbl_schedule.start_time,
#         tbl_schedule.end_time,
#         tbl_teacher.name,
#         tbl_level.level_name
#       ORDER BY 
#         tbl_schedule.start_time ASC
#       """, (today, session['id_admin']))
#     data = cur.fetchall()

#     # Total Students
#     cur.execute("SELECT COUNT(id_student) FROM tbl_student WHERE id_admin = %s AND (is_trial IS NULL OR is_trial = 0)", (session['id_admin'], ))
#     data_student = cur.fetchone()[0]

#     # Total Teachers
#     cur.execute("SELECT COUNT(id_teacher) FROM tbl_teacher WHERE id_admin = %s", (session['id_admin'], ))
#     data_teacher = cur.fetchone()[0]

#     # Total Classes Today
#     cur.execute("""
#     SELECT COUNT(DISTINCT CONCAT(
#         start_time,
#         end_time,
#         id_teacher,
#         id_level,
#         date
#     ))
#     FROM tbl_schedule
#     WHERE date=%s
#     AND id_admin=%s
# """, (
#     today,
#     session['id_admin']
# ))
#     data_classes_today = cur.fetchone()[0]

#     cur.close()

#     return render_template('admin/dashboard.html', total_student=data_student, total_teacher=data_teacher, data_schedule=data, total_classes_today=data_classes_today)

#   flash("Please Login", "danger")
#   return redirect(url_for('login'))
@app.route('/dashboard_admin')
@login_required
def dashboard_admin():
    if "loggedin" in session:
        cur = mysql.connection.cursor()

        # =====================================================
        # TODAY'S DATE & DAY
        # =====================================================
        today = datetime.now(
            ZoneInfo("Asia/Jakarta")
        ).date()

        today_day = today.strftime("%a").upper()

        # =====================================================
        # TODAY'S SCHEDULE
        # Uses the NEW recurring tbl_teacher_schedule
        # =====================================================
        cur.execute("""
            SELECT
                ts.id_teacher_schedule,
                ts.start_time,
                ts.end_time,

                t.name AS teacher,

                l.level_name,

                st.name AS student_name,
                tr.name AS trial_name,

                CASE
                    WHEN ts.id_trial_student IS NOT NULL
                    THEN 'trial'
                    ELSE 'current'
                END AS student_type,

                ts.notes

            FROM tbl_teacher_schedule ts

            JOIN tbl_teacher t
                ON ts.id_teacher = t.id_teacher

            JOIN tbl_level l
                ON ts.id_level = l.id_level

            LEFT JOIN tbl_student st
                ON ts.id_student = st.id_student

            LEFT JOIN tbl_trial_student tr
                ON ts.id_trial_student = tr.id_trial_student

            WHERE ts.class_day = %s
              AND ts.id_admin = %s

            ORDER BY
                ts.start_time ASC,
                t.name ASC,
                COALESCE(st.name, tr.name) ASC
        """, (
            today_day,
            session['id_admin']
        ))

        schedule_rows = cur.fetchall()

        # =====================================================
        # GROUP STUDENTS BY TEACHER + TIME
        # =====================================================
        schedule_classes = {}

        for row in schedule_rows:

            (
                schedule_id,
                start_time,
                end_time,
                teacher,
                level_name,
                student_name,
                trial_name,
                student_type,
                notes
            ) = row

            # Each teacher + time slot becomes one class card
            key = (
                teacher,
                start_time,
                end_time
            )

            if key not in schedule_classes:
                schedule_classes[key] = {
                    "start_time": start_time,
                    "end_time": end_time,
                    "teacher": teacher,
                    "levels": [],
                    "students": []
                }

            # =================================================
            # ADD LEVEL
            # =================================================
            if (
                level_name
                and level_name not in schedule_classes[key]["levels"]
            ):
                schedule_classes[key]["levels"].append(
                    level_name
                )

            # =================================================
            # ADD STUDENT
            # =================================================
            student_name = student_name or trial_name

            if student_name:
                schedule_classes[key]["students"].append({
                    "name": student_name,
                    "type": student_type,
                    "notes": notes
                })

        data = list(schedule_classes.values())

        # =====================================================
        # TOTAL STUDENTS
        # =====================================================
        cur.execute("""
            SELECT COUNT(id_student)
            FROM tbl_student
            WHERE id_admin = %s
              AND (is_trial IS NULL OR is_trial = 0)
        """, (
            session['id_admin'],
        ))

        data_student = cur.fetchone()[0]

        # =====================================================
        # TOTAL TEACHERS
        # =====================================================
        cur.execute("""
            SELECT COUNT(id_teacher)
            FROM tbl_teacher
            WHERE id_admin = %s
        """, (
            session['id_admin'],
        ))

        data_teacher = cur.fetchone()[0]

        # =====================================================
        # TOTAL CLASSES TODAY
        # =====================================================
        cur.execute("""
            SELECT COUNT(DISTINCT CONCAT(
                start_time,
                end_time,
                id_teacher
            ))
            FROM tbl_teacher_schedule

            WHERE class_day = %s
              AND id_admin = %s
        """, (
            today_day,
            session['id_admin']
        ))

        data_classes_today = cur.fetchone()[0]

        cur.close()

        # =====================================================
        # SEND DATA TO DASHBOARD
        # =====================================================
        return render_template(
            'admin/dashboard.html',
            total_student=data_student,
            total_teacher=data_teacher,
            data_schedule=data,
            total_classes_today=data_classes_today
        )

    flash("Please Login", "danger")
    return redirect(url_for('login'))

# STUDENT
@app.route('/student')
@login_required
def student():
  return model_student()

# ADD STUDENT
@app.route('/add_student', methods=['GET', 'POST'])
@login_required
def add_student():
  return model_add_student()

# EDIT STUDENT
@app.route('/edit_student/<int:id>', methods=['GET'])
@login_required
def edit_student(id):
  return model_edit_student(id)

# PROCESS EDIT STUDENT
@app.route('/process_edit_student', methods=['POST'])
@login_required
def process_edit_student():
  return model_process_edit_student()

# DELETE STUDENT
@app.route('/delete_student/<int:id>', methods=['GET'])
@login_required
def delete_student(id):
  return model_delete_student(id)


# TEACHER
@app.route('/teacher')
@login_required
def teacher():
  return model_teacher()

# ADD TEACHER
@app.route('/add_teacher', methods=['GET', 'POST'])
@login_required
def add_teacher():
  return model_add_teacher()

# EDIT TEACHER
@app.route('/edit_teacher/<int:id>', methods=['GET'])
@login_required
def edit_teacher(id):
  return model_edit_teacher(id)

# PROCESS EDIT TEACHER
@app.route('/process_edit_teacher', methods=['POST'])
@login_required
def process_edit_teacher():
  return model_process_edit_teacher()

# DELETE TEACHER
@app.route('/delete_teacher/<int:id>', methods=['GET'])
@login_required
def delete_teacher(id):
  return model_delete_teacher(id)


# # SCHEDULE
# @app.route('/schedule')
# @login_required
# def schedule():
#   return model_schedule()

# @app.route ('/add_schedule', methods=['GET', 'POST'])
# @login_required
# def add_schedule():
#   return model_add_schedule()

# @app.route('/edit_schedule/<int:id>', methods=['GET'])
# @login_required
# def edit_schedule(id):
#   return model_edit_schedule(id)

# @app.route('/process_edit_schedule', methods=['POST'])
# @login_required
# def process_edit_schedule():
#   return model_process_edit_schedule()

# @app.route('/edit_master_schedule/<int:id>', methods=['GET'])
# @login_required
# def edit_master_schedule(id):
#   return model_edit_master_schedule(id)

# @app.route('/process_edit_master_schedule', methods=['POST'])
# @login_required
# def process_edit_master_schedule():
#   return model_process_edit_master_schedule()

# @app.route('/delete_schedule/<int:id>', methods=['GET'])
# @login_required
# def delete_schedule(id):
#   return model_delete_schedule(id)

# @app.route('/delete_master_schedule/<int:id>', methods=['GET'])
# @login_required
# def delete_master_student(id):
#   return model_delete_master_schedule(id)

# @app.route('/get_attendance/<int:id>', methods=['GET'])
# @login_required
# def get_attendance(id):
#   return model_get_attendance(id)

# @app.route('/update_attendance', methods=['POST'])
# @login_required
# def update_attendance():
#   return model_update_attendance()

# @app.route('/get_attendance_by_attendance/<int:id>')
# @login_required
# def get_attendance_by_attendance(id):
#     return model_get_attendance_by_attendance(id)

# @app.route('/print_schedule')
# @login_required
# def print_schedule():
#   return model_print_schedule()
# =========================================================
# SCHEDULE
# =========================================================
@app.route('/schedule')
@login_required
def schedule():
    return model_schedule()

# =========================================================
# ADD STUDENT TO RECURRING TEACHER SCHEDULE
# =========================================================
@app.route('/add_teacher_schedule', methods=['POST'])
@login_required
def add_teacher_schedule():
    return model_add_teacher_schedule()

# =========================================================
# EDIT STUDENT FROM RECURRING TEACHER SCHEDULE
# =========================================================
@app.route('/edit_teacher_schedule/<int:schedule_id>', methods=['POST'])
@login_required
def edit_teacher_schedule(schedule_id):
    return model_edit_teacher_schedule(schedule_id)

# =========================================================
# DELETE STUDENT FROM RECURRING TEACHER SCHEDULE
# =========================================================
@app.route('/delete_teacher_schedule/<int:id>', methods=['POST'])
@login_required
def delete_teacher_schedule(id):
    return model_delete_teacher_schedule(id)


# =========================================================
# GET STUDENTS FOR ADD STUDENT MODAL
# =========================================================
@app.route('/get_schedule_students', methods=['GET'])
@login_required
def get_schedule_students():
    return model_get_schedule_students()


# =========================================================
# GET ATTENDANCE
# =========================================================
@app.route('/get_student_attendance', methods=['GET'])
@login_required
def get_student_attendance():
    return model_get_student_attendance()


# =========================================================
# GET ONE ATTENDANCE RECORD
# =========================================================
@app.route('/get_student_attendance_record', methods=['GET'])
@login_required
def get_student_attendance_record():
    return model_get_student_attendance_record()


# =========================================================
# SAVE ATTENDANCE
# =========================================================
@app.route('/save_student_attendance', methods=['POST'])
@login_required
def save_student_attendance():
    return model_save_student_attendance()


# =========================================================
# DELETE / CLEAR ATTENDANCE
# =========================================================
@app.route('/delete_student_attendance', methods=['POST'])
@login_required
def delete_student_attendance():
    return model_delete_student_attendance()

# =========================================================
# PRINT SCHEDULE
# =========================================================
@app.route('/print_schedule')
@login_required
def print_schedule():
    return model_print_schedule()


# TEACHER SCHEDULE PAGE
@app.route('/teacher_schedule/<branch_name>')
def teacher_schedule(branch_name):
  return model_teacher_schedule(branch_name)

# PAYMENT
@app.route('/payment')
@login_required
def payment():
  return model_payment()

# ADD PAYMENT
@app.route('/add_payment', methods=['GET', 'POST'])
@login_required
def add_payment():
  return model_add_payment()

# EDIT PAYMENT
@app.route('/edit_payment/<int:id>', methods=['GET'])
@login_required
def edit_payment(id):
  return model_edit_payment(id)

# PROCESS EDIT PAYMENT
@app.route('/process_edit_payment', methods=['POST'])
@login_required
def process_edit_payment():
  return model_process_edit_payment()

# DELETE PAYMENT
@app.route('/delete_payment/<int:id>', methods=['GET'])
@login_required
def delete_payment(id):
  return model_delete_payment(id)

app.add_url_rule('/check_registration_status', 'check_registration_status', check_registration_status)


# LEVEL
@app.route('/level')
@login_required
def level():
  return model_level()

# ADD LEVEL
@app.route('/add_level', methods=['GET', 'POST'])
@login_required
def add_level():
  return model_add_level()

# EDIT LEVEL
@app.route('/edit_level/<int:id>', methods=['GET'])
@login_required
def edit_level(id):
  return model_edit_level(id)

# PROCESS EDIT LEVEL
@app.route('/process_edit_level', methods=['POST'])
@login_required
def process_edit_level():
  return model_process_edit_level()

# DELETE LEVEL
@app.route('/delete_level/<int:id>', methods=['GET'])
@login_required
def delete_level(id):
  return model_delete_level(id)


# RECAP
@app.route('/recap')
@login_required
def recap():
  return model_recap()


# TRIAL
@app.route('/trial')
@login_required
def trial():
  return model_trial()

# ADD TRIAL
@app.route('/add_trial', methods=['GET', 'POST'])
@login_required
def add_trial():
  return model_add_trial()

# EDIT TRIAL
@app.route('/edit_trial/<int:id>', methods=['GET'])
@login_required
def edit_trial(id):
  return model_edit_trial(id)

# PROCESS EDIT TRIAL
@app.route('/process_edit_trial', methods=['POST'])
@login_required
def process_edit_trial():
  return model_process_edit_trial()

# DELETE TRIAL
@app.route('/delete_trial/<int:id>', methods=['GET'])
@login_required
def delete_trial(id):
  return model_delete_trial(id)


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
@login_required_director
def director_dashboard():
  if "director_loggedin" in session:
    cur = mysql.connection.cursor()

    # Total Students
    # cur.execute("SELECT COUNT(s.id_student) FROM tbl_student s JOIN tbl_admin a ON s.id_admin = a.id_admin WHERE a.id_director = %s", (session['id_director'], ))
    cur.execute("""
    SELECT COUNT(*)
    FROM tbl_student s
    JOIN tbl_admin a
        ON s.id_admin = a.id_admin

    LEFT JOIN tbl_student_period sp
        ON sp.id_student = s.id_student
        AND (sp.year * 100 + sp.month) = (
            SELECT MAX(sp2.year * 100 + sp2.month)
            FROM tbl_student_period sp2
            WHERE sp2.id_student = s.id_student
        )

    WHERE a.id_director = %s
    AND sp.status IN (
        'Current Student',
        'Waiting List',
        'Past Student'
    )
""", (session['id_director'], ))
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
@login_required_director
def branch():
  return model_branch()

# ADD BRANCH
@app.route('/add_branch', methods=['GET', 'POST'])
@login_required_director
def add_branch():
  return model_add_branch()

# EDIT BRANCH
@app.route('/edit_branch/<int:id>', methods=['GET'])
@login_required_director
def edit_branch(id):
  return model_edit_branch(id)

# PROCESS EDIT BRANCH
@app.route('/process_edit_branch', methods=['POST'])
@login_required_director
def process_edit_branch():
  return model_process_edit_branch()

# DELETE BRANCH
@app.route('/delete_branch/<int:id>', methods=['GET'])
@login_required_director
def delete_branch(id):
  return model_delete_branch(id)


# ADMIN
@app.route('/admin')
@login_required_director
def admin():
  return model_admin()

# ADD ADMIN
@app.route('/add_admin', methods=['GET', 'POST'])
@login_required_director
def add_admin():
  return model_add_admin()

# EDIT ADMIN
@app.route('/edit_admin/<int:id>', methods=['GET'])
@login_required_director
def edit_admin(id):
  return model_edit_admin(id)

# PROCESS EDIT ADMIN
@app.route('/process_edit_admin', methods=['POST'])
@login_required_director
def process_edit_admin():
  return model_process_edit_admin()

# DELETE ADMIN
@app.route('/delete_admin/<int:id>', methods=['GET'])
@login_required_director
def delete_admin(id):
  return model_delete_admin(id)


# STUDENT
@app.route('/director_student')
@login_required_director
def director_student():
  return model_director_student()


# TEACHER
@app.route('/director_teacher')
@login_required_director
def director_teacher():
  return model_director_teacher()


# PAYMENT
@app.route('/director_payment')
@login_required_director
def director_payment():
  return model_director_payment()


# SCHEDULE
@app.route('/director_schedule')
@login_required_director
def director_schedule():
  return model_director_schedule()

# EDIT DIRECTOR
@app.route('/edit_director_account', methods=['GET'])
@login_required_director
def edit_director_account():
    return model_edit_director_account()

# PROCESS EDIT DIRECTOR ACCOUNT
@app.route('/process_edit_director_account', methods=['POST'])
@login_required_director
def process_edit_director_account():
    return model_process_edit_director_account()


if __name__ == '__main__':
  # webbrowser.open('http://127.0.0.1:5000/login')
  app.run(debug=True)
  