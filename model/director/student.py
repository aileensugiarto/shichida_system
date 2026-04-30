from flask import render_template, request, session
from db import mysql
from datetime import date, datetime

# =========================
# STUDENT PAGE (DIRECTOR)
# =========================
def model_director_student():
    cur = mysql.connection.cursor()

    today = date.today()

    # =========================
    # GET FILTER DATE
    # =========================
    filter_year = int(request.args.get("year", today.year))
    filter_month = int(request.args.get("month", today.month))

    # =========================
    # AUTO DETECT TERM
    # =========================
    if filter_month in [1, 2, 3]:
        filter_term = 1
    elif filter_month in [4, 5, 6]:
        filter_term = 2
    elif filter_month in [7, 8, 9]:
        filter_term = 3
    else:
        filter_term = 4

    # =========================
    # MONTH NAME
    # =========================
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    month_name = month_names[filter_month - 1]

    # =========================
    # MAIN STUDENT QUERY
    # =========================
    cur.execute("""
        SELECT 
            s.id_student, 
            s.name, 
            s.dob, 
            s.parent_name, 
            s.parent_telp, 
            s.address, 
            s.class_type, 
            s.join_date, 
            sp.status, 
            l.level_name, 
            t.name AS teacher_name, 
            b.branch_name
        FROM tbl_student s
        LEFT JOIN tbl_level l ON s.id_level = l.id_level
        JOIN tbl_admin a ON s.id_admin = a.id_admin
        LEFT JOIN tbl_branch b ON a.id_branch = b.id_branch

        -- ✅ GET LATEST PERIOD UP TO SELECTED MONTH
        LEFT JOIN tbl_student_period sp 
          ON sp.id_student = s.id_student
          AND (sp.year * 100 + sp.month) = (
              SELECT MAX(sp2.year * 100 + sp2.month)
              FROM tbl_student_period sp2
              WHERE sp2.id_student = s.id_student
                AND (sp2.year * 100 + sp2.month) <= (%s * 100 + %s)
          )

        LEFT JOIN tbl_teacher t 
          ON sp.id_teacher = t.id_teacher

        WHERE a.id_director = %s
        AND (sp.status IS NULL OR sp.status != 'Trial')
        ORDER BY b.branch_name, s.name
    """, (filter_year, filter_month, session['id_director']))

    students = cur.fetchall()

    # =========================
    # GET ALL BRANCHES
    # =========================
    cur.execute("""
        SELECT branch_name 
        FROM tbl_branch 
        WHERE id_director = %s
    """, (session['id_director'], ))
    branches = [row[0] for row in cur.fetchall()]

    # =========================
    # GET ALL TEACHERS UNDER DIRECTOR
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

    # =========================
    # FORMAT DATA
    # =========================
    updated_students = []

    for row in students:
        student = {
            "id": row[0],
            "name": row[1],
            "dob": row[2],
            "age": calculate_age(row[2]),
            "parent": row[3],
            "telp": row[4],
            "address": row[5],
            "class_type": row[6],
            "join_date": row[7],
            "status": row[8] if row[8] else "-",
            "level": row[9] if row[9] else "-",
            "teacher": row[10] if row[10] else "-",
            "branch": row[11] if row[11] else "-"
        }
        updated_students.append(student)

    # =========================
    # RENDER
    # =========================
    return render_template(
        'director/student/student.html',
        data_student=updated_students,
        filter_year=filter_year,
        filter_term=filter_term,
        month_name=month_name,
        branches=branches,
        teachers=teachers
    )


# =========================
# CALCULATE AGE
# =========================
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