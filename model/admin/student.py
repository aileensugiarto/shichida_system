from flask import Flask, render_template, redirect, url_for, request, flash, session
import os
from db import mysql
from datetime import date, datetime
import calendar

TERM_MONTHS = {
    1: [1, 2, 3],
    2: [4, 5, 6],
    3: [7, 8, 9],
    4: [10, 11, 12],
}

# GET STUDENT PERIOD
def get_student_period(cur, student_id, year, month):
    ym = year * 100 + month
    cur.execute("""
        SELECT
            sp.term,
            sp.month,
            sp.status,
            t.name
        FROM tbl_student_period sp
        LEFT JOIN tbl_teacher t
            ON sp.id_teacher = t.id_teacher
        WHERE sp.id_student = %s
          AND (sp.year * 100 + sp.month) <= %s
        ORDER BY sp.year DESC, sp.month DESC
        LIMIT 1
    """, (student_id, ym))
    return cur.fetchone()


# STUDENT
def model_student():
    cur = mysql.connection.cursor()
    today = date.today()

    # 🔹 FILTERS
    filter_year = int(request.args.get("year", today.year))
    raw_term = request.args.get("term", "")
    raw_month = request.args.get("month", "")

    is_all_terms = (raw_term == "all")

    if not is_all_terms:
        filter_month = int(raw_month) if raw_month else today.month
        filter_term = get_term_from_month(filter_month)
    else:
        filter_month = None
        filter_term = "all"

    # 🔹 FETCH LEVELS (SORT BY AGE RANGE)
    cur.execute("""
        SELECT 
            level_name,
            age_range,
            CAST(SUBSTRING_INDEX(age_range, '-', 1) AS DECIMAL(4,2)) AS min_age
        FROM tbl_level
        WHERE id_admin = %s
        ORDER BY min_age ASC
    """, (session["id_admin"],))

    levels = [row[0] for row in cur.fetchall()]

    # 🔹 FETCH STUDENTS
    cur.execute("""
        SELECT
            id_student,
            name,
            dob,
            join_date,
            parent_name,
            parent_telp,
            address
        FROM tbl_student
        WHERE id_admin = %s AND (is_trial = 0 OR is_trial IS NULL)
        ORDER BY name
    """, (session["id_admin"],))

    rows = cur.fetchall()
    students = []

    for r in rows:
        (
            id_student,
            name,
            dob,
            join_date,
            parent_name,
            parent_telp,
            address
        ) = r

        age = calculate_age(dob)

        # 🔹 FIX join_date format
        if isinstance(join_date, str) and join_date.strip():
            join_date = datetime.strptime(join_date, "%Y-%m-%d").date()
        else:
            join_date = None

        # 🔹 TERM LOOP
        if is_all_terms:
            term_month_pairs = [(None, m) for m in range(1, 13)]
        else:
            term_month_pairs = [(filter_term, filter_month)]

        for _, month in term_month_pairs:
            term = get_term_from_month(month)

            # 🔹 GET LATEST PERIOD DATA (IMPORTANT LOGIC)
            cur.execute("""
                SELECT
                    sp.status,
                    sp.id_teacher,
                    sp.id_level,
                    sp.class_type,
                    t.name
                FROM tbl_student_period sp
                LEFT JOIN tbl_teacher t
                    ON sp.id_teacher = t.id_teacher
                WHERE sp.id_student = %s
                AND (sp.year < %s OR (sp.year = %s AND sp.month <= %s))
                ORDER BY sp.year DESC, sp.month DESC
                LIMIT 1
            """, (id_student, filter_year, filter_year, month))

            period = cur.fetchone()

            # 🔹 SAFE COPY
            display_join_date = join_date
            display_parent_name = parent_name

            # 🔹 CHECK IF STUDENT HAS JOINED
            if not join_date:
                joined = False
            else:
                joined = not (
                    join_date.year > filter_year or
                    (join_date.year == filter_year and join_date.month > month)
                )

            # =========================
            # ✅ FINAL STATUS LOGIC
            # =========================
            if not joined:
                display_status = "Not Joined"
                teacher_name = ""
                level_name = ""
                class_type = ""

            else:
                if period:
                    status, id_teacher, id_level, class_type, teacher_name = period

                    # ✅ KEY FIX: USE DB STATUS DIRECTLY
                    display_status = status if status else "Current Student"
                    teacher_name = teacher_name if teacher_name else ""

                    # 🔹 GET LEVEL NAME
                    if id_level:
                        cur.execute("""
                            SELECT level_name
                            FROM tbl_level
                            WHERE id_level = %s
                        """, (id_level,))
                        lvl = cur.fetchone()
                        level_name = lvl[0] if lvl else ""
                    else:
                        level_name = ""

                    class_type = class_type if class_type else ""

                else:
                    display_status = "Current Student"
                    teacher_name = ""
                    level_name = ""
                    class_type = ""

            # 🔹 APPEND RESULT
            students.append({
                "id": id_student,
                "name": name,
                "dob": dob,
                "age": age,
                "level": level_name,
                "class_type": class_type,
                "join_date": display_join_date,
                "parent_name": display_parent_name,
                "parent_telp": parent_telp,
                "address": address,
                "year": filter_year,
                "term": term,
                "month_num": month,
                "month_name": month_to_word(month),
                "teacher": teacher_name,
                "status": display_status
            })

    filter_month_name = month_to_word(filter_month) if filter_month else ""

    return render_template(
        "admin/student/student.html",
        data_student=students,
        filter_year=filter_year,
        filter_term=filter_term,
        filter_month=filter_month,
        filter_month_name=filter_month_name,
        levels=levels
    )
# ADD STUDENT
def model_add_student():
    cur = mysql.connection.cursor()

    # Load dropdown data
    cur.execute(
        "SELECT id_level, level_name, age_range FROM tbl_level WHERE id_admin = %s",
        (session['id_admin'],)
    )
    levels = cur.fetchall()

    cur.execute(
        "SELECT id_teacher, name FROM tbl_teacher WHERE id_admin = %s",
        (session['id_admin'],)
    )
    teachers = cur.fetchall()

    if request.method == "POST":
        try:
            # ===== FORM DATA =====
            name = request.form['form_name']
            dob = request.form['form_dob']
            id_level = request.form['form_id_level']  # ✅ MANUAL LEVEL
            class_type = request.form['form_class_type']
            id_teacher = request.form['form_id_teacher']
            join_date_str = request.form['form_join_date']
            status = request.form['form_status']
            parent_name = request.form['form_parent_name']
            parent_telp = request.form['form_parent_telp']
            address = request.form['form_address']

            # ===== DATE PROCESSING =====
            join_date = datetime.strptime(join_date_str, "%Y-%m-%d").date()
            join_year = join_date.year
            join_month = join_date.month
            join_term = get_term_from_month(join_month)

            # ===== 1️⃣ INSERT STUDENT (GLOBAL) =====
            cur.execute("""
                INSERT INTO tbl_student
                (name, dob, id_level, is_manual_level, class_type, id_admin, join_date, parent_name, parent_telp, address)
                VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,%s)
            """, (
                name,
                dob,
                id_level,
                class_type,
                session['id_admin'],
                join_date,
                parent_name,
                parent_telp,
                address
            ))

            id_student = cur.lastrowid

            # ===== 2️⃣ INSERT STUDENT PERIOD =====
            cur.execute("""
                INSERT INTO tbl_student_period
                (id_student, year, term, month, id_teacher, status, id_level, class_type)
                VALUES (%s,%s,%s,%s,%s,%s, %s, %s)
            """, (
                id_student,
                join_year,
                join_term,
                join_month,
                id_teacher,
                status,
                id_level,
                class_type
            ))

            mysql.connection.commit()
            flash("Student successfully added", "success")
            return redirect(url_for('student'))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error adding student: {str(e)}", "danger")

        finally:
            cur.close()

    return render_template(
        'admin/student/add_student.html',
        data_level=levels,
        data_teacher=teachers
    )


def safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

# EDIT STUDENT
def model_edit_student(id):
    today = date.today()

    year = safe_int(request.args.get("year"), today.year)
    term = safe_int(request.args.get("term"), 1)
    month = safe_int(request.args.get("month"), today.month)

    cur = mysql.connection.cursor()

    # STUDENT DATA
    cur.execute("""
        SELECT
            id_student,
            name,
            dob,
            class_type,
            join_date,
            parent_name,
            parent_telp,
            address
        FROM tbl_student
        WHERE id_student = %s AND id_admin = %s
    """, (id, session['id_admin']))
    student = cur.fetchone()

    cur.execute("""
        SELECT id_teacher, status, id_level
        FROM tbl_student_period
        WHERE id_student = %s
          AND year = %s
          AND month = %s
        LIMIT 1
    """, (id, year, month))

    period_data = cur.fetchone()

    # 2️⃣ FALLBACK
    if not period_data:
        cur.execute("""
            SELECT id_teacher, status, id_level
            FROM tbl_student_period
            WHERE id_student = %s
              AND (year < %s OR (year = %s AND month < %s))
            ORDER BY year DESC, month DESC
            LIMIT 1
        """, (id, year, year, month))

        period_data = cur.fetchone()

    # 3️⃣ ASSIGN VALUES
    if period_data:
        period_teacher_id = period_data[0]
        period_status = period_data[1]
        period_level_id = period_data[2]
    else:
        period_teacher_id = None
        period_status = "Current Student"
        period_level_id = None

    # ✅ DROPDOWNS (OUTSIDE IF/ELSE)
    cur.execute("""
        SELECT id_level, level_name, age_range
        FROM tbl_level
        WHERE id_admin=%s
    """, (session['id_admin'],))
    levels = cur.fetchall()

    cur.execute("""
        SELECT id_teacher, name
        FROM tbl_teacher
        WHERE id_admin=%s
    """, (session['id_admin'],))
    teachers = cur.fetchall()

    cur.close()

    # FORMAT JOIN DATE
    join_date = student[4]
    if join_date:
        if isinstance(join_date, str):
            join_date = datetime.strptime(join_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        else:
            join_date = join_date.strftime("%Y-%m-%d")
    else:
        join_date = ""

    return render_template(
        "admin/student/edit_student.html",
        data_student=student,
        period_teacher_id=period_teacher_id,
        period_status=period_status,
        period_level_id=period_level_id,
        selected_year=year,
        selected_term=term,
        selected_month=month,
        data_level=levels,
        data_teacher=teachers
    )


# PROCESS EDIT STUDENT
def model_process_edit_student():
    cur = mysql.connection.cursor()

    try:
        id_student = request.form["form_id_student"]

        year = int(request.form["form_year"])
        term = int(request.form["form_term"])
        month = int(request.form["form_month"])

        # GLOBAL DATA (NO LEVEL HERE ❌)
        name = request.form["form_name"]
        dob = request.form["form_dob"]
        class_type = request.form["form_class_type"]
        join_date = request.form["form_join_date"]
        parent_name = request.form["form_parent_name"]
        parent_telp = request.form["form_parent_telp"]
        address = request.form["form_address"]

        # PERIOD DATA
        id_teacher = request.form["form_id_teacher"]
        status = request.form["form_status"]
        id_level = request.form["form_id_level"]  # ✅ ONLY HERE

        # ✅ UPDATE STUDENT (NO LEVEL)
        cur.execute("""
            UPDATE tbl_student
            SET
                name=%s,
                dob=%s,
                class_type=%s,
                join_date=%s,
                parent_name=%s,
                parent_telp=%s,
                address=%s
            WHERE id_student=%s
              AND id_admin=%s
        """, (
            name,
            dob,
            class_type,
            join_date,
            parent_name,
            parent_telp,
            address,
            id_student,
            session["id_admin"]
        ))

        # CHECK PERIOD EXISTS
        cur.execute("""
            SELECT 1 FROM tbl_student_period
            WHERE id_student=%s
              AND year=%s
              AND term=%s
              AND month=%s
        """, (id_student, year, term, month))

        exists = cur.fetchone()

        if exists:
            # ✅ UPDATE ONLY THIS MONTH
            cur.execute("""
                UPDATE tbl_student_period
                SET id_teacher=%s, status=%s, id_level=%s, class_type=%s
                WHERE id_student=%s
                  AND year=%s
                  AND term=%s
                  AND month=%s
            """, (id_teacher, status, id_level, class_type,
                  id_student, year, term, month))
        else:
            # ✅ INSERT NEW MONTH
            cur.execute("""
                INSERT INTO tbl_student_period
                (id_student, year, term, month, id_teacher, status, id_level, class_type)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (id_student, year, term, month,
                  id_teacher, status, id_level, class_type))

        mysql.connection.commit()

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error updating student: {str(e)}", "danger")

    finally:
        cur.close()

    return redirect(url_for(
        "student",
        year=year,
        term=term,
        month=month
    ))

# DELETE STUDENT
def model_delete_student(id):
    cur = mysql.connection.cursor()

    try:
        # 1️⃣ Get all schedule IDs linked to this student
        cur.execute("""
            SELECT id_schedule
            FROM tbl_attendance
            WHERE id_student = %s
              AND id_admin = %s
        """, (id, session['id_admin']))

        schedule_ids = [row[0] for row in cur.fetchall()]

        # 2️⃣ Delete attendance for this student
        cur.execute("""
            DELETE FROM tbl_attendance
            WHERE id_student = %s
              AND id_admin = %s
        """, (id, session['id_admin']))

        # 3️⃣ Delete orphan schedules (no students left)
        if schedule_ids:
            ids = ",".join(map(str, schedule_ids))

            cur.execute(f"""
                DELETE FROM tbl_schedule
                WHERE id_schedule IN ({ids})
                  AND id_admin = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM tbl_attendance a
                      WHERE a.id_schedule = tbl_schedule.id_schedule
                  )
            """, (session['id_admin'],))

        # 4️⃣ Delete student period
        cur.execute("""
            DELETE FROM tbl_student_period
            WHERE id_student = %s
        """, (id,))

        # 5️⃣ Delete student
        cur.execute("""
            DELETE FROM tbl_student
            WHERE id_student = %s
              AND id_admin = %s
        """, (id, session['id_admin']))

        mysql.connection.commit()
        flash("Student successfully deleted", "success")

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error deleting student: {str(e)}", "danger")

    finally:
        cur.close()

    return redirect(url_for("student"))


# CALCULATE AGE BASED ON DOB (Decimal format)
def calculate_age(dob):

    if not dob or dob == "":
        return ""

    if isinstance(dob, str):
        try:
            dob = datetime.strptime(dob, "%Y-%m-%d").date()
        except ValueError:
            return ""

    today = date.today()

    years = today.year - dob.year
    months = today.month - dob.month

    if today.day < dob.day:
        months -= 1

    if months < 0:
        years -= 1
        months += 12

    return f"{years}.{months:02d}"

# GET LEVEL BY AGE
def get_level_by_age(age):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id_level, level_name
        FROM tbl_level
        WHERE %s BETWEEN
            CAST(SUBSTRING_INDEX(age_range, ' - ', 1) AS DECIMAL(4,2))
            AND CAST(SUBSTRING_INDEX(age_range, ' - ', -1) AS DECIMAL(4,2))
        LIMIT 1
    """, (age,))
    result = cur.fetchone()
    cur.close()
    return result


# GET TERM FROM MONTH
def get_term_from_month(month):
    if 1 <= month <= 3:
        return 1
    elif 4 <= month <= 6:
        return 2
    elif 7 <= month <= 9:
        return 3
    else:
        return 4

# MONTH TO WORD
def month_to_word(month_number):
    return calendar.month_name[int(month_number)]

# GET EFFECTIVE STUDENT PERIOD
def get_effective_student_period(cur, id_student, year, month):
    """
    Returns the latest period <= given year+month
    """
    cur.execute("""
        SELECT id_teacher, status, year, month
        FROM tbl_student_period
        WHERE id_student = %s
          AND (year < %s OR (year = %s AND month <= %s))
        ORDER BY year DESC, month DESC
        LIMIT 1
    """, (id_student, year, year, month))

    return cur.fetchone()
