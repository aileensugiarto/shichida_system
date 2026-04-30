from flask import Flask, render_template, redirect, url_for, request, flash, session
import os
from datetime import date
from db import mysql
from model.admin.student import get_effective_student_period, get_term_from_month

# RECAP
def model_recap():
    cur = mysql.connection.cursor()

    today = date.today()
    year = today.year
    month = today.month
    term = get_term_from_month(month)

    month_names = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
    month_name = month_names[month]

    # Get all students for this admin
    cur.execute("""
            SELECT
                s.id_student,
                s.name,
                s.parent_name,
                s.join_date
            FROM tbl_student s
            WHERE s.id_admin=%s
            ORDER BY s.name ASC
    """, (session["id_admin"], ))
    rows = cur.fetchall()

    recap_data = []
    for row in rows:
        id_student, student_name, parent_name, join_date = row

        # convert join date if needed
        if isinstance(join_date, str):
            join_date = date.fromisoformat(join_date)
        
        # Check join date
        if join_date and (join_date.year > year or (join_date.year == year and join_date.month > month)):
            continue # not joined yet

        # Get effective period
        period = get_effective_student_period(cur, id_student, year, month)
        if not period:
            continue
        id_teacher, status, _, _ = period

        # Only ACTIVE students
        if status != "Current Student":
            continue

        # Get teacher name
        teacher_name = "-"
        if id_teacher:
            cur.execute("SELECT name FROM tbl_teacher WHERE id_teacher=%s", (id_teacher, ))
            t = cur.fetchone()
            if t:
                teacher_name = t[0]
        
        recap_data.append({
            "student_name":student_name,
            "parent_name": parent_name,
            "teacher_name": teacher_name,
            "year": year,
            "term": term,
            "month": month,
        })

    # 🔥 Get teacher list for filter
    cur.execute("""
        SELECT id_teacher, name 
        FROM tbl_teacher 
        WHERE id_admin = %s
    """, (session["id_admin"],))
    teachers = cur.fetchall()

    cur.close()

    return render_template("admin/recap/recap.html", recap_data=recap_data, year=year, term=term, month=month, month_name=month_name, teachers=teachers)