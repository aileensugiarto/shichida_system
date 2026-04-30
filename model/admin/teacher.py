from flask import Flask, render_template, redirect, url_for, request, flash, session
import os
from db import mysql
from model.admin.student import calculate_age, get_level_by_age, get_term_from_month


# TEACHER
from datetime import date, datetime
from collections import defaultdict

TERM_MONTHS = {
    1: [1, 2, 3],
    2: [4, 5, 6],
    3: [7, 8, 9],
    4: [10, 11, 12]
}
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

def model_teacher():
    today = date.today()

    current_year = today.year
    current_month = today.month
    if current_month in [1, 2, 3]:
      current_term = "1"
    elif current_month in [4, 5, 6]:
        current_term = "2"
    elif current_month in [7, 8, 9]:
        current_term = "3"
    else:
        current_term = "4"

    filter_year = int(request.args.get("year", today.year))
    filter_term = str(request.args.get("term", current_term))
    filter_month = request.args.get("month")

    if filter_month:
        filter_month = int(filter_month)
    else:
        filter_month = current_month

    # =========================
    # TEACHERS (GLOBAL)
    # =========================
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id_teacher, name
        FROM tbl_teacher
        WHERE id_admin = %s
        ORDER BY name
    """, (session["id_admin"],))
    teachers = cur.fetchall()
    cur.close()

    teacher_periods = []

    for id_teacher, teacher_name in teachers:
        if filter_term == "all":
            for term, months in TERM_MONTHS.items():
                for m in months:
                    teacher_periods.append({
                        "id_teacher": id_teacher,
                        "name": teacher_name,
                        "year": filter_year,
                        "term": term,
                        "month": m
                            })
        else:
            term = int(filter_term)

            months = [filter_month]

            for m in months:
                teacher_periods.append({
                    "id_teacher": id_teacher,
                    "name": teacher_name,
                    "year": filter_year,
                    "term": term,
                    "month": m
                })

    # =========================
    # STUDENT PERIODS (RAW)
    # =========================
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT
            s.id_student,
            s.name,
            s.dob,
            sp.id_teacher,
            sp.year,
            sp.month,
            sp.status,
            sp.id_level,
            l.level_name
        FROM tbl_student s
        JOIN tbl_student_period sp
            ON sp.id_student = s.id_student
        LEFT JOIN tbl_level l
            ON sp.id_level = l.id_level
        WHERE s.id_admin = %s
    """, (session["id_admin"],))
    rows = cur.fetchall()
    cur.close()

    # =========================
    # BUILD LATEST STATUS PER STUDENT (PER SELECTED MONTH)
    # =========================
    student_latest = {}

    target_ym = filter_year * 100 + filter_month

    for r in rows:
        id_student = r[0]
        name = r[1]
        dob = r[2]
        id_teacher = r[3]
        year = r[4]
        month = r[5]
        status = r[6]

        ym = year * 100 + month

        # ignore future records
        if ym > target_ym:
            continue

        # keep latest record <= selected month
        if id_student not in student_latest or ym > student_latest[id_student]["ym"]:
            student_latest[id_student] = {
                "ym": ym,
                "id_teacher": id_teacher,
                "status": status,
                "dob": dob,
                "name": name,
                "level": r[8] if r[8] else "-"
            }

    # =========================
    # BUILD STUDENT LIST (ONLY ACTIVE)
    # =========================
    students = []

    for sid, info in student_latest.items():

        # 🔴 THIS is the rule you wanted
        if info["status"] != "Current Student":
            continue

        age = calculate_age(info["dob"])
        # level_data = get_level_by_age(age)

        students.append({
            "id_student": sid,
            "name": info["name"],
            "age": age,
            "level": info['level'],
            "id_teacher": info["id_teacher"],
            "month": filter_month
        })
        # SORT STUDENTS BY NAME
        students = sorted(students, key=lambda x: x["name"].lower())

    # =========================
    # GET LEVEL LIST (FOR FILTER)
    # =========================
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT level_name,
        age_range,
        CAST(SUBSTRING_INDEX(age_range, '-', 1) AS DECIMAL(4,2)) AS min_age
        FROM tbl_level
        WHERE id_admin = %s
        ORDER BY min_age ASC
    """, (session["id_admin"],))
    levels = [row[0] for row in cur.fetchall()]
    cur.close()

    # =========================
    # RENDER
    # =========================
    return render_template(
        "admin/teacher/teacher.html",
        data_teacher=teacher_periods,
        data_student=students,
        filter_year=filter_year,
        filter_term=filter_term,
        filter_month=filter_month,
        current_year=datetime.now().year,
        current_term=current_term,
        current_month=current_month,
        month_names=MONTH_NAMES,
        levels=levels
    )

# ADD TEACHER
def model_add_teacher():
    if request.method == 'POST':
        name = request.form['form_name']

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO tbl_teacher (name, id_admin) VALUES (%s, %s)",
                    (name, session['id_admin'], ))
        mysql.connection.commit()
        cur.close()

        flash("Teacher successfully added", "success")
        return redirect(url_for("teacher"))

    return render_template('admin/teacher/add_teacher.html')

# EDIT TEACHER
def model_edit_teacher(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM tbl_teacher WHERE id_teacher = %s AND id_admin = %s", (id, session['id_admin'], ))
    data = cur.fetchone()
    cur.close()
    return render_template('admin/teacher/edit_teacher.html', data_teacher=data)

# PROCESS EDIT TEACHER
def model_process_edit_teacher():
    id_teacher = request.form['form_id_teacher']
    name = request.form['form_name']

    cur = mysql.connection.cursor()
    cur.execute("UPDATE tbl_teacher SET name=%s WHERE id_teacher=%s AND id_admin=%s", (name, id_teacher, session['id_admin'], ))
    mysql.connection.commit()
    cur.close()

    flash("Teacher successfully updated", "success")
    return redirect(url_for("teacher"))

# DELETE TEACHER
def model_delete_teacher(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM tbl_teacher WHERE id_teacher = %s AND id_admin=%s", (id, session['id_admin'], ))
    mysql.connection.commit()
    cur.close()

    flash("Teacher successfully deleted", "success")
    return redirect(url_for("teacher"))