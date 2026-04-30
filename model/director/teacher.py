from flask import Flask, render_template, redirect, url_for, request, flash, session
import os
from db import mysql
from model.director.student import calculate_age

from datetime import datetime

def model_director_teacher():
    cur = mysql.connection.cursor()

    # =========================
    # CURRENT PERIOD
    # =========================
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    # Determine term
    if current_month <= 3:
        current_term = 1
    elif current_month <= 6:
        current_term = 2
    elif current_month <= 9:
        current_term = 3
    else:
        current_term = 4

    # =========================
    # FILTERS
    # =========================
    branch = request.args.get('branch')
    search = request.args.get('search')
    sort = request.args.get('sort', 'name')  # default sort

    query = """
        SELECT
            t.id_teacher,
            t.name,
            b.branch_name
        FROM tbl_teacher t
        JOIN tbl_admin a ON t.id_admin = a.id_admin
        JOIN tbl_branch b ON a.id_branch = b.id_branch
        WHERE b.id_director = %s
    """

    params = [session['id_director']]

    if branch and branch != "all":
        query += " AND b.branch_name = %s"
        params.append(branch)

    if search:
        query += " AND t.name LIKE %s"
        params.append(f"%{search}%")

    query += " ORDER BY b.branch_name, t.name"

    cur.execute(query, tuple(params))
    teachers = cur.fetchall()

    updated_teachers = []

    for row in teachers:
        teacher_id = row[0]

        # =========================
        # GET ALL STUDENT RECORDS (NO TEACHER FILTER)
        # =========================
        student_query = """
            SELECT 
                s.id_student,
                s.name,
                s.dob,
                l.level_name,
                sp.id_teacher,
                sp.year,
                sp.month,
                sp.status
            FROM tbl_student_period sp
            JOIN tbl_student s ON sp.id_student = s.id_student
            JOIN tbl_level l ON s.id_level = l.id_level
        """

        cur.execute(student_query)
        students = cur.fetchall()

        # =========================
        # GET LATEST VALID RECORD PER STUDENT
        # =========================
        student_latest = {}

        target_ym = current_year * 100 + current_month

        for s in students:
            sid = s[0]
            name = s[1]
            dob = s[2]
            level = s[3]
            teacher_id_sp = s[4]
            year = s[5]
            month = s[6]
            status = s[7]

            ym = year * 100 + month

            # ignore future records
            if ym > target_ym:
                continue

            # keep latest record per student
            if sid not in student_latest or ym > student_latest[sid]["ym"]:
                student_latest[sid] = {
                    "ym": ym,
                    "name": name,
                    "dob": dob,
                    "level": level,
                    "status": status,
                    "id_teacher": teacher_id_sp
                }

        # =========================
        # BUILD FINAL STUDENT LIST (FILTER BY CURRENT TEACHER)
        # =========================
        student_list = []

        for sid, info in student_latest.items():
            if info["status"] != "Current Student":
                continue

            # ✅ ONLY show student under their LATEST teacher
            if info["id_teacher"] != teacher_id:
                continue

            student_list.append({
                "name": info["name"],
                "age": calculate_age(info["dob"]),
                "level": info["level"]
            })

        # =========================
        # SORTING (PYTHON SIDE)
        # =========================
        if sort == "name":
            student_list.sort(key=lambda x: x['name'])
        elif sort == "age":
            student_list.sort(key=lambda x: x['age'])
        elif sort == "level":
            student_list.sort(key=lambda x: x['level'])

        updated_teachers.append({
            "id": teacher_id,
            "name": row[1],
            "branch": row[2],
            "students": student_list
        })

    # =========================
    # BRANCH DROPDOWN
    # =========================
    cur.execute("""
        SELECT DISTINCT branch_name 
        FROM tbl_branch 
        WHERE id_director = %s
    """, (session['id_director'],))
    branches = cur.fetchall()

    cur.close()

    return render_template(
        'director/teacher/teacher.html',
        data_teacher=updated_teachers,
        branches=branches,
        current_year=current_year,
        current_term=current_term,
        current_month=current_month,
        sort=sort
    )
