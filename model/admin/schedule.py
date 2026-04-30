from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
import os
from db import mysql
from datetime import date, datetime, timedelta

TIME_SLOTS = [
    ("09:00", "10:00"),
    ("10:00", "11:00"),
    ("11:00", "12:00"),
    ("12:00", "13:00"),
    ("13:00", "14:00"),
    ("14:00", "15:00"),
    ("15:00", "16:00"),
    ("16:00", "17:00"),
]

# SCHEDULE
def model_schedule():

    cur = mysql.connection.cursor()

    # ============================
    # 1️⃣ SELECTED DATE
    # ============================

    selected_date = request.args.get("date")

    if not selected_date:
        selected_date = date.today().strftime("%Y-%m-%d")

    # ============================
    # 2️⃣ GET TEACHERS
    # ============================

    cur.execute("""
        SELECT id_teacher, name
        FROM tbl_teacher
        WHERE id_admin = %s
    """, (session['id_admin'],))

    teachers = cur.fetchall()

    # ============================
    # 3️⃣ GET SCHEDULES FOR DATE
    # ============================

    cur.execute("""
        SELECT 
            s.id_schedule,
            s.start_time,
            s.end_time,
            s.id_teacher,
            t.name,
            l.level_name,
            st.id_student,
            st.name,
            st.dob,
            a.status,
            s.is_rescheduled,
            s.rescheduled_from,
            s.reschedule_date,
            st.is_trial
        FROM tbl_schedule s
        JOIN tbl_teacher t ON s.id_teacher = t.id_teacher
        LEFT JOIN tbl_level l ON s.id_level = l.id_level
        JOIN tbl_attendance a ON s.id_schedule = a.id_schedule
        LEFT JOIN tbl_student st ON a.id_student = st.id_student
        WHERE DATE(s.date) = %s
        AND s.id_admin = %s
        ORDER BY s.id_teacher, s.start_time
    """, (selected_date, session['id_admin']))

    schedule_rows = cur.fetchall()

    # ============================
    # 4️⃣ MASTER SCHEDULE TABLE
    # ============================

    term_filter = request.args.get("term")
    student_filter = request.args.get("student")
    day_filter = request.args.get("day")
    level_filter = request.args.get("level")
    teacher_filter = request.args.get("teacher")

    query = """
    SELECT 
        m.id_master_schedule,
        YEAR(m.start_date) AS year,
        m.term,
        m.start_date,
        m.class_day,
        m.start_time,
        m.end_time,
        l.level_name,
        st.name,
        t.name,
        m.total_meetings
    FROM tbl_master_schedule m
    JOIN tbl_level l ON m.id_level = l.id_level
    JOIN tbl_student st ON m.id_student = st.id_student
    JOIN tbl_teacher t ON m.id_teacher = t.id_teacher
    WHERE m.id_admin = %s
"""

    params = [session['id_admin']]

    if term_filter:
        query += " AND m.term = %s"
        params.append(term_filter)

    if student_filter:
        query += " AND st.name LIKE %s"
        params.append(f"%{student_filter}%")

    if day_filter:
        query += " AND m.class_day = %s"
        params.append(day_filter)

    if level_filter:
        query += " AND m.id_level = %s"
        params.append(level_filter)

    if teacher_filter:
        query += " AND m.id_teacher = %s"
        params.append(teacher_filter)

    query += " ORDER BY FIELD(m.class_day,'MON','TUE','WED','THU','FRI','SAT'), m.start_time"

    cur.execute(query, params)

    data_master_schedule = cur.fetchall()

    # ============================
    # FILTER DROPDOWN DATA
    # ============================

    cur.execute("""
        SELECT id_level, level_name, age_range,
        CAST(SUBSTRING_INDEX(age_range, '-', 1) AS DECIMAL(4,2)) AS min_age
        FROM tbl_level
        WHERE id_admin=%s
        ORDER BY min_age ASC
    """, (session['id_admin'],))
    levels = cur.fetchall()

    cur.execute("""
        SELECT id_teacher, name
        FROM tbl_teacher
        WHERE id_admin=%s
    """, (session['id_admin'],))
    teachers_filter = cur.fetchall()

    # ============================
    # 5️⃣ ATTENDANCE TRACKER
    # ============================

    cur.execute("""
        SELECT 
            m.id_master_schedule,
            YEAR(m.start_date) AS year,
            m.term,
            st.name,
            s.date,
            a.status
        FROM tbl_master_schedule m
        JOIN tbl_schedule s 
            ON m.id_master_schedule = s.id_master_schedule
        JOIN tbl_attendance a 
            ON s.id_schedule = a.id_schedule
        JOIN tbl_student st 
            ON a.id_student = st.id_student
        WHERE m.id_admin = %s
        ORDER BY m.id_master_schedule, s.date
    """, (session['id_admin'],))

    attendance_rows = cur.fetchall()

    attendance_tracker = {}

    for r in attendance_rows:

        master_id = r[0]
        year = r[1]
        term = r[2]
        student = r[3]
        class_date = r[4]
        status = r[5]

        key = f"{master_id}_{student}"

        if key not in attendance_tracker:
            attendance_tracker[key] = {
                "year": year,
                "term": term,
                "student": student,
                "meetings": []
            }

        attendance_tracker[key]["meetings"].append({
            "date": class_date.strftime("%d %b %Y"),
            "status": status
        })

    attendance_tracker = list(attendance_tracker.values())

    # ============================
    # 6️⃣ BUILD SCHEDULE MAP
    # ============================

    schedule_map = {}

    for teacher_id, teacher_name in teachers:

        schedule_map[teacher_id] = {
            "teacher_name": teacher_name,
            "slots": {
                f"{start}-{end}": [] for start, end in TIME_SLOTS
            }
        }

    # ============================
    # 7️⃣ FILL STUDENTS INTO SLOTS
    # ============================

    for r in schedule_rows:

        slot_key = f"{r[1]}-{r[2]}"
        teacher_id = r[3]

        if teacher_id in schedule_map and slot_key in schedule_map[teacher_id]["slots"]:

            age = calculate_age(r[8])

            # FIX: ensure trial student always has visible age
            if not age or age == "-":
                if r[13]:  # is_trial
                    age = "0.00"

            schedule_map[teacher_id]["slots"][slot_key].append({
                "id_schedule": r[0],
                "student_name": r[7],
                "age": age,
                "level": r[5],
                "status": r[9],
                "is_rescheduled": bool(r[10]),
                "rescheduled_from": (
                    r[11].strftime("%d %b %Y") if r[11] else None
                ),
                "is_trial": bool(r[13])
            })

    cur.close()

    # ============================
    # 8️⃣ RENDER PAGE
    # ============================

    return render_template(
        "admin/schedule/schedule.html",
        selected_date=selected_date,
        schedule_map=schedule_map,
        time_slots=TIME_SLOTS,
        data_master_schedule=data_master_schedule,
        attendance_tracker=attendance_tracker,
        levels=levels,
        teachers_filter=teachers_filter
    )

# ADD SCHEDULE
def model_add_schedule():
    cur = mysql.connection.cursor()

    # Load dropdown data
    cur.execute("SELECT * FROM tbl_teacher WHERE id_admin=%s", (session['id_admin'],))
    teachers = cur.fetchall()

    cur.execute("SELECT * FROM tbl_student WHERE id_admin=%s AND (is_trial IS NULL OR is_trial = 0)", (session['id_admin'],))
    students = cur.fetchall()

    updated_students = []
    for student in students:
        age = calculate_age(student[2])
        updated_students.append((student[0], student[1], age))

    cur.execute("SELECT * FROM tbl_level WHERE id_admin=%s", (session['id_admin'],))
    levels = cur.fetchall()

    if request.method == "POST":
        # ===== 1. GET FORM DATA =====
        term = request.form['form_term']
        start_date = datetime.strptime(
            request.form['form_start_date'], "%Y-%m-%d"
        ).date()

        class_day = request.form['form_class_day'].upper().strip()
        level = int(request.form['form_level'])
        start_time = request.form['form_start_time']
        end_time = request.form['form_end_time']
        teacher = int(request.form['form_teacher'])

        term = request.form['form_term']

        if term == "TRIAL":
            term = 0
            student_name = request.form['form_trial_student_name']
            dob = request.form['form_trial_dob']

            # ✅ DO NOT insert into tbl_student
            # Instead: store name directly in schedule

            cur.execute("""
                INSERT INTO tbl_student (name, dob, is_trial, id_admin)
                VALUES (%s, %s, %s, %s)
            """, (student_name, dob, 1, session['id_admin']))

            student = cur.lastrowid
            total_meetings = 1

        else:
            term = int(term)
            student = int(request.form['form_student'])
            total_meetings = int(request.form['form_total_meetings'])

        # ===== 2. INSERT MASTER SCHEDULE =====
        cur.execute("""
            INSERT INTO tbl_master_schedule
            (term, start_date, class_day, id_level, start_time, end_time,
             id_teacher, id_student, total_meetings, id_admin)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            term, start_date, class_day, level,
            start_time, end_time, teacher, student,
            total_meetings, session['id_admin']
        ))

        id_master_schedule = cur.lastrowid

        # ===== 3. MAP DAY STRING → PYTHON WEEKDAY =====
        day_map = {
            'MON': 0,
            'TUE': 1,
            'WED': 2,
            'THU': 3,
            'FRI': 4,
            'SAT': 5
        }

        target_weekday = day_map[class_day]

        # ===== 4. FIND FIRST VALID CLASS DATE =====
        current_date = start_date
        while current_date.weekday() != target_weekday:
            current_date += timedelta(days=1)

        # ===== 5. GENERATE WEEKLY SCHEDULES =====
        for _ in range(total_meetings):
            cur.execute("""
                INSERT INTO tbl_schedule
                (date, start_time, end_time, id_teacher,
                 id_level, id_master_schedule, id_admin)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                current_date,
                start_time,
                end_time,
                teacher,
                level,
                id_master_schedule,
                session['id_admin']
            ))

            id_schedule = cur.lastrowid

            # Link student attendance
            cur.execute("""
                INSERT INTO tbl_attendance
                (id_schedule, id_student, id_admin)
                VALUES (%s,%s,%s)
            """, (id_schedule, student, session['id_admin']))

            # Move to next week
            current_date += timedelta(days=7)

        mysql.connection.commit()
        cur.close()

        flash("Schedule successfully added", "success")
        return redirect(url_for('schedule'))

    return render_template(
        'admin/schedule/add_schedule.html',
        data_teacher=teachers,
        data_student=updated_students,
        data_level=levels
    )


# EDIT SCHEDULE
def model_edit_schedule(id):
  cur = mysql.connection.cursor()
  # Get Schedule Data
  cur.execute("SELECT * FROM tbl_schedule WHERE id_schedule = %s AND id_admin = %s", (id, session['id_admin'], ))
  schedule = cur.fetchone()

  # Get Teachers
  cur.execute("SELECT * FROM tbl_teacher WHERE id_admin=%s", (session['id_admin'], ))
  teachers = cur.fetchall()

  # Get Students
  cur.execute("SELECT * FROM tbl_student WHERE id_admin=%s", (session['id_admin'], ))
  students = cur.fetchall()
  updated_students = []
  for student in students:
    age = calculate_age(student[2])
    updated_students.append((student[0], student[1], age))

  cur.execute("SELECT * FROM tbl_level WHERE id_admin=%s", (session['id_admin'], ))
  levels = cur.fetchall()

  # Get Current Students for this schedule
  cur.execute("SELECT id_student FROM tbl_attendance WHERE id_schedule = %s AND id_admin=%s", (id, session['id_admin'], ))
  current_students_data = cur.fetchall()
  current_students = [row[0] for row in current_students_data]

  cur.close()
  return render_template('admin/schedule/edit_schedule.html', data_schedule=schedule, data_teacher=teachers, data_student=updated_students, data_current_student=current_students, data_level=levels)


# PROCESS EDIT SCHEDULE
def model_process_edit_schedule():
  id_schedule = request.form['form_id_schedule']
  date = request.form['form_date']
  level = request.form['form_level']
  start_time = request.form['form_start_time']
  end_time = request.form['form_end_time']
  teacher = request.form['form_teacher']
  students = request.form.getlist('form_students')

  cur = mysql.connection.cursor()
  cur.execute("UPDATE tbl_schedule SET date=%s, id_level=%s, start_time=%s, end_time=%s, id_teacher=%s WHERE id_schedule=%s AND id_admin=%s",
              (date, level, start_time, end_time, teacher, id_schedule, session['id_admin'], ))

  cur.execute("SELECT id_student FROM tbl_attendance WHERE id_schedule = %s AND id_admin=%s", (id_schedule, session['id_admin'], ))
  existing_rows = cur.fetchall()
  existing_ids = set(row[0] for row in existing_rows)
  new_ids = set(int(x) for x in students)

  to_delete = existing_ids - new_ids
  to_add = new_ids - existing_ids

  for sid in to_delete:
      cur.execute("DELETE FROM tbl_attendance WHERE id_schedule=%s AND id_student=%s AND id_admin=%s", (id_schedule, sid, session['id_admin'], ))

  for sid in to_add:
      cur.execute("INSERT INTO tbl_attendance (id_schedule, id_student, id_admin) VALUES (%s, %s, %s)", (id_schedule, sid, session['id_admin'], ))

  mysql.connection.commit()
  cur.close()

  flash("Schedule successfully updated", "success")
  return redirect(url_for("schedule"))


# EDIT MASTER SCHEDULE
def model_edit_master_schedule(id_master_schedule):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT *
        FROM tbl_master_schedule
        WHERE id_master_schedule=%s AND id_admin=%s
    """, (id_master_schedule, session['id_admin']))
    master = cur.fetchone()

    cur.execute("SELECT * FROM tbl_teacher WHERE id_admin=%s", (session['id_admin'],))
    teachers = cur.fetchall()

    cur.execute("SELECT * FROM tbl_student WHERE id_admin=%s", (session['id_admin'],))
    raw_students = cur.fetchall()

    students = []
    for s in raw_students:
        age = calculate_age(s[2])  # s[2] = DOB
        students.append({
            "id": s[0],
            "name": s[1],
            "age": age
        })

    cur.execute("SELECT * FROM tbl_level WHERE id_admin=%s", (session['id_admin'],))
    levels = cur.fetchall()

    cur.close()

    return render_template(
        'admin/schedule/edit_master_schedule.html',
        data_master_schedule=master,
        data_teacher=teachers,
        data_student=students,
        data_level=levels
    )

# PROCESS EDIT MASTER SCHEDULE
def model_process_edit_master_schedule():
    id_master = int(request.form['form_id_master_schedule'])
    term = request.form['form_term']
    start_date = datetime.strptime(
        request.form['form_start_date'], "%Y-%m-%d"
    ).date()
    class_day = request.form['form_class_day'].upper()[:3]
    level = int(request.form['form_level'])
    start_time = request.form['form_start_time']
    end_time = request.form['form_end_time']
    teacher = int(request.form['form_teacher'])
    student = int(request.form['form_student'])
    total_meetings = int(request.form['form_total_meetings'])

    if total_meetings < 1:
        flash("Total meetings must be at least 1", "danger")
        return redirect(url_for("schedule"))

    cur = mysql.connection.cursor()

    # =========================
    # 1️⃣ UPDATE MASTER SCHEDULE
    # =========================
    cur.execute("""
        UPDATE tbl_master_schedule
        SET term=%s,
            start_date=%s,
            class_day=%s,
            id_level=%s,
            start_time=%s,
            end_time=%s,
            id_teacher=%s,
            id_student=%s,
            total_meetings=%s
        WHERE id_master_schedule=%s AND id_admin=%s
    """, (
        term, start_date, class_day, level,
        start_time, end_time, teacher, student,
        total_meetings, id_master, session['id_admin']
    ))

    # =========================
    # 2️⃣ GET ALL SCHEDULES + STATUS
    # =========================
    cur.execute("""
        SELECT s.id_schedule, s.date, a.status
        FROM tbl_schedule s
        JOIN tbl_attendance a ON s.id_schedule = a.id_schedule
        WHERE s.id_master_schedule=%s AND s.id_admin=%s
        ORDER BY s.date ASC
    """, (id_master, session['id_admin']))

    schedules = cur.fetchall()

    # =========================
    # 3️⃣ SPLIT LOCKED / EDITABLE
    # =========================
    locked = []
    editable = []

    for s in schedules:
        if s[2]:  # has status (present/absent)
            locked.append(s)
        else:
            editable.append(s)

    # =========================
    # 4️⃣ LIMIT TOTAL MEETINGS
    # =========================
    final_schedules = locked + editable
    final_schedules = final_schedules[:total_meetings]

    locked_ids = {s[0] for s in locked}
    kept_ids = {s[0] for s in final_schedules}

    # =========================
    # 5️⃣ DELETE EXTRA (ONLY EDITABLE)
    # =========================
    for s in schedules:
        if s[0] not in kept_ids and s[0] not in locked_ids:
            cur.execute("DELETE FROM tbl_attendance WHERE id_schedule=%s AND id_admin=%s",
                        (s[0], session['id_admin']))
            cur.execute("DELETE FROM tbl_schedule WHERE id_schedule=%s AND id_admin=%s",
                        (s[0], session['id_admin']))

    # =========================
    # 6️⃣ RECALCULATE DATES FOR EDITABLE
    # =========================
    day_map = {'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3, 'FRI': 4, 'SAT': 5}
    target_day = day_map[class_day]

    # =========================
    # 🧠 NEW: FIND LAST ATTENDED DATE
    # =========================
    last_attended_date = None

    if locked:
        last_attended_date = max(s[1] for s in locked)

    # =========================
    # 🧠 NEW: DETERMINE START POINT
    # =========================
    if last_attended_date:
        # 👉 Move to NEXT WEEK (your rule)
        next_week_start = last_attended_date + timedelta(days=(7 - last_attended_date.weekday()))
    else:
        # No attendance yet → fallback to original start_date
        next_week_start = start_date

    # =========================
    # 🧠 NEW: ALIGN TO TARGET DAY (IN NEXT WEEK)
    # =========================
    current_date = next_week_start

    while current_date.weekday() != target_day:
        current_date += timedelta(days=1)

    # Collect locked dates so we don't overwrite them
    locked_dates = {s[1] for s in locked}

    updated_count = 0

    for s in final_schedules:
        sched_id = s[0]

        # SKIP LOCKED
        if sched_id in locked_ids:
            continue

        # Find next available date (skip locked dates)
        while current_date in locked_dates:
            current_date += timedelta(days=7)

        # UPDATE THIS SCHEDULE
        cur.execute("""
            UPDATE tbl_schedule
            SET date=%s,
                start_time=%s,
                end_time=%s,
                id_teacher=%s,
                id_level=%s
            WHERE id_schedule=%s AND id_admin=%s
        """, (
            current_date,
            start_time,
            end_time,
            teacher,
            level,
            sched_id,
            session['id_admin']
        ))

        current_date += timedelta(days=7)
        updated_count += 1

    # =========================
    # 7️⃣ ADD MISSING SCHEDULES
    # =========================
    existing_count = len(final_schedules)
    to_add = total_meetings - existing_count

    for _ in range(to_add):
        while current_date in locked_dates:
            current_date += timedelta(days=7)

        cur.execute("""
            INSERT INTO tbl_schedule
            (date, start_time, end_time, id_teacher,
             id_level, id_master_schedule, id_admin)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            current_date,
            start_time,
            end_time,
            teacher,
            level,
            id_master,
            session['id_admin']
        ))

        new_schedule_id = cur.lastrowid

        cur.execute("""
            INSERT INTO tbl_attendance
            (id_schedule, id_student, id_admin)
            VALUES (%s,%s,%s)
        """, (new_schedule_id, student, session['id_admin']))

        current_date += timedelta(days=7)

    mysql.connection.commit()
    cur.close()

    flash("Master schedule updated successfully", "success")
    return redirect(url_for("schedule"))

# DELETE SCHEDULE
# def model_delete_schedule(id):
#   cur = mysql.connection.cursor()
#   cur.execute("DELETE FROM tbl_schedule WHERE id_schedule = %s AND id_admin=%s", (id, session['id_admin'], ))
#   mysql.connection.commit()
#   cur.close()

#   flash("Schedule successfully deleted", "success")
#   return redirect(url_for("schedule"))

def model_delete_schedule(id):
    cur = mysql.connection.cursor()

    # =========================
    # 1️⃣ GET STUDENT LINKED TO THIS SCHEDULE
    # =========================
    cur.execute("""
        SELECT st.id_student, st.is_trial
        FROM tbl_attendance a
        JOIN tbl_student st ON a.id_student = st.id_student
        WHERE a.id_schedule = %s
        AND a.id_admin = %s
    """, (id, session['id_admin']))

    student_data = cur.fetchone()

    # =========================
    # 2️⃣ DELETE ATTENDANCE FIRST
    # =========================
    cur.execute("""
        DELETE FROM tbl_attendance 
        WHERE id_schedule = %s 
        AND id_admin = %s
    """, (id, session['id_admin']))

    # =========================
    # 3️⃣ DELETE SCHEDULE
    # =========================
    cur.execute("""
        DELETE FROM tbl_schedule 
        WHERE id_schedule = %s 
        AND id_admin=%s
    """, (id, session['id_admin']))

    # =========================
    # 4️⃣ DELETE TRIAL STUDENT (ONLY IF TRIAL)
    # =========================
    if student_data:
        student_id, is_trial = student_data

        if is_trial == 1:
            cur.execute("""
                DELETE FROM tbl_student
                WHERE id_student = %s
                AND id_admin = %s
            """, (student_id, session['id_admin']))

    mysql.connection.commit()
    cur.close()

    flash("Schedule successfully deleted", "success")
    return redirect(url_for("schedule"))

# DELETE MASTER SCHEDULE
def model_delete_master_schedule(id_master_schedule):
    cur = mysql.connection.cursor()

    # 1️⃣ GET ALL SCHEDULE IDS UNDER THIS MASTER
    cur.execute("""
        SELECT id_schedule
        FROM tbl_schedule
        WHERE id_master_schedule=%s AND id_admin=%s
    """, (id_master_schedule, session['id_admin']))

    schedule_ids = [row[0] for row in cur.fetchall()]

    # 2️⃣ DELETE ATTENDANCE FIRST (VERY IMPORTANT)
    if schedule_ids:
        cur.execute("""
            DELETE FROM tbl_attendance
            WHERE id_schedule IN %s AND id_admin=%s
        """, (tuple(schedule_ids), session['id_admin']))

    # 3️⃣ DELETE ALL SCHEDULES UNDER MASTER
    cur.execute("""
        DELETE FROM tbl_schedule
        WHERE id_master_schedule=%s AND id_admin=%s
    """, (id_master_schedule, session['id_admin']))

    # 4️⃣ DELETE MASTER SCHEDULE ITSELF
    cur.execute("""
        DELETE FROM tbl_master_schedule
        WHERE id_master_schedule=%s AND id_admin=%s
    """, (id_master_schedule, session['id_admin']))

    mysql.connection.commit()
    cur.close()

    flash("Student schedule and all related classes deleted successfully", "success")
    return redirect(url_for("schedule"))

# CALCULATE AGE BASED ON DOB
def calculate_age(dob):

    if not dob:
        return "-"

    if isinstance(dob, str):
        if dob.strip() == "":
            return "-"
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


# GET ATTENDANCE
def model_get_attendance(id):
  cur = mysql.connection.cursor()

  cur.execute("""SELECT tbl_attendance.id_attendance, tbl_student.name, tbl_attendance.status FROM tbl_attendance
JOIN tbl_student ON tbl_attendance.id_student = tbl_student.id_student WHERE tbl_attendance.id_schedule=%s AND tbl_attendance.id_admin=%s""", (id, session['id_admin'], ))
  data = cur.fetchall()
  cur.close()

  # convert to list of dicts for json
  students = []
  for row in data:
    students.append({
      'id_ss': row[0],
      'name': row[1],
      'status': row[2],
    })
  return jsonify(students)

# UPDATE ATTENDANCE
def model_update_attendance():
  if request.method == 'POST':
    data = request.get_json()
    attendance_list = data.get('attendance')

    cur = mysql.connection.cursor()
    for item in attendance_list:
      cur.execute("UPDATE tbl_attendance SET status=%s WHERE id_attendance=%s AND id_admin=%s", (item['status'], item['id_ss'], session['id_admin'], ))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Attendance successfully updated'})
  return jsonify({'error': 'invalid request'}), 400