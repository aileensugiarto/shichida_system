from flask import Flask, render_template, redirect, url_for, request, flash, session
import os
from db import mysql
from datetime import date, datetime

# LEVEL
def model_level():
    cur = mysql.connection.cursor()

    # cur.execute("""
    #     SELECT id_level, level_name, age_range
    #     FROM tbl_level
    #     WHERE id_admin = %s
    # """, (session['id_admin'],))
    # levels = cur.fetchall()

    cur.execute("""
    SELECT id_level, level_name, age_range
    FROM tbl_level
    WHERE id_admin = %s
    ORDER BY CAST(TRIM(SUBSTRING_INDEX(age_range, '-', 1)) AS DECIMAL(4,2))
    """, (session['id_admin'],))
    levels = cur.fetchall()

    cur.execute("""
        SELECT id_student, name, dob, id_level
        FROM tbl_student
        WHERE id_admin = %s
    """, (session['id_admin'],))
    students = cur.fetchall()

    # Process students
    student_map = {}

    for s in students:
        age = calculate_age(s[2])
        level_id = int(s[3]) if s[3] else None

        student_map.setdefault(level_id, []).append({
            "name": s[1],
            "age": age
        })

    cur.close()

    return render_template(
        "admin/level/level.html",
        data_level=levels,
        student_map=student_map
    )

# ADD LEVEL
def model_add_level():
  if request.method == "POST":
    level_name = request.form['form_level_name']
    age_range = request.form['form_age_range']

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO tbl_level (level_name, age_range, id_admin) VALUES (%s, %s, %s)", (level_name, age_range, session['id_admin'], ))
    mysql.connection.commit()
    cur.close()

    flash("Level successfully added", "success")
    return redirect(url_for('level'))
  return render_template('admin/level/add_level.html')

# EDIT LEVEL
def model_edit_level(id):
  cur = mysql.connection.cursor()
  cur.execute("SELECT id_level, level_name, age_range FROM tbl_level WHERE id_level=%s AND id_admin=%s", (id, session['id_admin'], ))
  data_level = cur.fetchone()
  cur.close()
  return render_template('admin/level/edit_level.html', data_level=data_level)

# PROCESS EDIT LEVEL
def model_process_edit_level():
  id_level = request.form['form_id_level']
  level_name = request.form['form_level_name']
  age_range = request.form['form_age_range']

  cur = mysql.connection.cursor()
  cur.execute("UPDATE tbl_level SET level_name=%s, age_range=%s WHERE id_level=%s AND id_admin=%s", (level_name, age_range, id_level, session['id_admin'], ))
  mysql.connection.commit()
  cur.close()

  flash("Level successfully updated", "success")
  return redirect(url_for('level'))

# DELETE LEVEL
def model_delete_level(id):
  cur = mysql.connection.cursor()
  cur.execute("DELETE FROM tbl_level WHERE id_level=%s AND id_admin=%s", (id, session['id_admin'], ))
  mysql.connection.commit()
  cur.close()
  flash("Level successfully deleted", "success")
  return redirect(url_for('level'))

# CALCULATE AGE BASED ON DOB
def calculate_age(dob):
  if isinstance(dob, str):
    dob = datetime.strptime(dob, "%Y-%m-%d").date()

  today = date.today()

  years = today.year - dob.year
  months = today.month - dob.month

  if today.day < dob.day:
    months -= 1

  if months < 0:
    years -= 1
    months += 12

  return f"{years}.{months:02d}"