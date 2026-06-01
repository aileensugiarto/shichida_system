from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
import os
from db import mysql
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

def indo_time_today():
    return datetime.now(
        ZoneInfo("Asia/Jakarta")
    ).date()

def calculate_age(dob):
    if not dob:
        return "-"

    if isinstance(dob, str):
        if dob.strip() == "":
            return "-"
        dob = datetime.strptime(dob, "%Y-%m-%d").date()

    today = indo_time_today()
    years = today.year - dob.year
    months = today.month - dob.month

    if today.day < dob.day:
        months -= 1

    if months < 0:
        years -= 1
        months += 12

    return f"{years}.{months:02d}"


# TRIAL
def model_trial():

    today = indo_time_today()

    # Default: current year and current month
    selected_year = request.args.get(
        "year",
        str(today.year)
    )

    selected_month = request.args.get(
        "month",
        str(today.month)
    )

    cur = mysql.connection.cursor()

    # If "All Months" selected
    if selected_month == "all":

        cur.execute("""
            SELECT
                id_trial_student,
                name,
                dob,
                parent_name,
                parent_telp,
                trial_date
            FROM tbl_trial_student
            WHERE
                id_admin = %s
                AND YEAR(trial_date) = %s
            ORDER BY trial_date DESC
        """, (
            session['id_admin'],
            selected_year
        ))

    else:

        cur.execute("""
            SELECT
                id_trial_student,
                name,
                dob,
                parent_name,
                parent_telp,
                trial_date
            FROM tbl_trial_student
            WHERE
                id_admin = %s
                AND YEAR(trial_date) = %s
                AND MONTH(trial_date) = %s
            ORDER BY trial_date DESC
        """, (
            session['id_admin'],
            selected_year,
            selected_month
        ))

    rows = cur.fetchall()

    trial_student_data = []

    for row in rows:

        age = calculate_age(row[2])

        trial_student_data.append({
            "id_trial_student": row[0],
            "name": row[1],
            "dob": row[2],
            "age": age,
            "parent_name": row[3],
            "parent_telp": row[4],
            "trial_date": row[5]
        })

    cur.close()

    # Dynamic year options
    selected_year_int = int(selected_year)

    year_options = [
        selected_year_int - 1,
        selected_year_int,
        selected_year_int + 1
    ]

    return render_template(
        "admin/trial/trial.html",
        trial_student_data=trial_student_data,
        selected_year=selected_year_int,
        selected_month=selected_month,
        year_options=year_options
    )

# ADD TRIAL
def model_add_trial():
    if request.method == 'POST':
        name = request.form['form_name']
        dob = request.form['form_dob']
        parent_name = request.form['form_parent_name']
        parent_telp = request.form['form_parent_telp']
        trial_date = request.form['form_trial_date']

        age = calculate_age(dob)

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO tbl_trial_student (name, dob, parent_name, parent_telp, trial_date, id_admin) VALUES (%s, %s, %s, %s, %s, %s)",
                    (name, dob, parent_name, parent_telp, trial_date, session['id_admin'], ))
        mysql.connection.commit()
        cur.close()

        flash("Trial student successfully added", "success")
        return redirect(url_for('trial'))
    return render_template('admin/trial/add_trial.html')


# EDIT TRIAL
def model_edit_trial(id):

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT *
        FROM tbl_trial_student
        WHERE id_trial_student=%s
        AND id_admin=%s
    """, (
        id,
        session['id_admin']
    ))

    data = cur.fetchone()

    cur.close()

    return render_template(
        "admin/trial/edit_trial.html",
        data_trial=data
    )

# PROCESS EDIT TRIAL
def model_process_edit_trial():

    id_trial_student = request.form['form_id_trial_student']

    name = request.form['form_name']
    dob = request.form['form_dob']
    parent_name = request.form['form_parent_name']
    parent_telp = request.form['form_parent_telp']
    trial_date = request.form['form_trial_date']

    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE tbl_trial_student
        SET
            name=%s,
            dob=%s,
            parent_name=%s,
            parent_telp=%s,
            trial_date=%s
        WHERE id_trial_student=%s
        AND id_admin=%s
    """, (
        name,
        dob,
        parent_name,
        parent_telp,
        trial_date,
        id_trial_student,
        session['id_admin']
    ))

    mysql.connection.commit()
    cur.close()

    flash(
        "Trial student successfully updated",
        "success"
    )

    return redirect(url_for("trial"))

def model_delete_trial(id):

    cur = mysql.connection.cursor()

    cur.execute("""
        DELETE FROM tbl_trial_student
        WHERE id_trial_student=%s
        AND id_admin=%s
    """, (
        id,
        session['id_admin']
    ))

    mysql.connection.commit()
    cur.close()

    flash(
        "Trial student successfully deleted",
        "success"
    )

    return redirect(url_for("trial"))