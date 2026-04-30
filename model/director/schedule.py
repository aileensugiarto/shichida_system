from flask import render_template, session
from db import mysql

def model_director_schedule():
    cur = mysql.connection.cursor()

    # =========================
    # MAIN SCHEDULE QUERY
    # =========================
    cur.execute("""
        SELECT 
            YEAR(m.start_date) AS year,
            m.term,
            m.class_day,
            m.start_time,
            m.end_time,
            st.name AS student,
            l.level_name AS level,
            t.name AS teacher,
            m.start_date,
            b.branch_name
        FROM tbl_master_schedule m
        JOIN tbl_student st ON m.id_student = st.id_student
        JOIN tbl_teacher t ON m.id_teacher = t.id_teacher
        JOIN tbl_level l ON m.id_level = l.id_level
        JOIN tbl_admin a ON m.id_admin = a.id_admin
        JOIN tbl_branch b ON a.id_branch = b.id_branch
        WHERE a.id_director = %s AND st.is_trial=0
        ORDER BY b.branch_name, m.start_date, m.class_day, m.start_time
    """, (session['id_director'],))

    schedules = cur.fetchall()

    # =========================
    # GET ALL BRANCHES
    # =========================
    cur.execute("""
        SELECT branch_name
        FROM tbl_branch
        WHERE id_director = %s
    """, (session['id_director'],))
    branches = [row[0] for row in cur.fetchall()]

    # =========================
    # GET ALL TEACHERS (DIRECTOR SCOPE)
    # =========================
    cur.execute("""
        SELECT DISTINCT t.name
        FROM tbl_teacher t
        JOIN tbl_admin a ON t.id_admin = a.id_admin
        WHERE a.id_director = %s
        ORDER BY t.name
    """, (session['id_director'],))
    teachers = [row[0] for row in cur.fetchall()]

    cur.close()

    return render_template(
        'director/schedule/schedule.html',
        data_schedule=schedules,
        branches=branches,
        teachers=teachers
    )