from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
import os
from db import mysql
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

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

def indo_time_today():
    return datetime.now(
        ZoneInfo("Asia/Jakarta")
    ).date()

# BUILD SCHEDULE MAP
def build_schedule_map(selected_date):
    cur = mysql.connection.cursor()

    # GET TEACHERS
    cur.execute("SELECT id_teacher, name FROM tbl_teacher WHERE id_admin=%s ORDER BY name", (session['id_admin'], ))
    teachers = cur.fetchall()

    # GET SCHEDULES
    cur.execute("""
        SELECT
        s.id_schedule,
        s.start_time,
        s.end_time,
        s.id_teacher,
        t.name AS teacher_name,
        l.level_name

        st.name AS student_name,
        st.dob AS student_dob,
        st.is_trial AS old_trial,

        ts.name AS trial_name,
        ts.dob AS trial_dob,

        s.id_trial_student
        FROM tbl_schedule s
        JOIN tbl_teacher t ON s.id_teacher = t.id_teacher
        LEFT JOIN tbl_level l ON s.id_level = l.id_level
        LEFT JOIN tbl_attendance a ON s.id_schedule = a.id_schedule
        LEFT JOIN tbl_student st ON a.id_student = st.id_student
        LEFT JOIN tbl_trial_student ts ON s.id_trial_student = ts.id_trial_student
        WHERE DATE(s.date)=%s AND s.id_admin=%s
        ORDER BY s.id_teacher, s.start_time
    """, (selected_date, session['id_admin']))

    schedule_rows = cur.fetchall()
    schedule_map = {}
    for id_teacher, teacher_name in teachers:
        schedule_map[id_teacher] = {
            "teacher_name":teacher_name,
            "slots": {
                f"{start}-{end}": [] for start, end in TIME_SLOTS
            }
        }

    for r in schedule_rows:
        slot_key = f"{r[1]}-{r[2]}"
        id_teacher = r[3]

        if id_teacher not in schedule_map:
            continue
        
        is_new_trial = bool(r[15])
        is_old_trial = bool(r[8])

        if is_new_trial:
            student_name = r[9]
            dob = r[10]
        else:
            student_name = r[6]
            dob = r[7]

        age = calculate_age(dob)

        schedule_map[id_teacher]["slots"][slot_key].append({
            "id_schedule": r[0],
            "student_name": student_name,
            "age": age,
            "level": r[5],
            "status": r[11],
            "is_trial": is_new_trial or is_old_trial
        })
    
    cur.close()

    return schedule_map, teachers

# SCHEDULE
def model_schedule():

    cur = mysql.connection.cursor()

    # ============================
    # 1️⃣ SELECTED DATE
    # ============================

    selected_date = request.args.get("date")

    if not selected_date:
        selected_date = indo_time_today().strftime("%Y-%m-%d")

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
            t.name AS teacher_name,
            l.level_name,

            st.name AS student_name,
            st.dob AS student_dob,
            st.is_trial AS old_trial,

            ts.name AS trial_name,
            ts.dob AS trial_dob,

            a.status,

            s.id_trial_student

        FROM tbl_schedule s

        JOIN tbl_teacher t
            ON s.id_teacher = t.id_teacher

        LEFT JOIN tbl_level l
            ON s.id_level = l.id_level

        LEFT JOIN tbl_attendance a
            ON s.id_schedule = a.id_schedule

        LEFT JOIN tbl_student st
            ON a.id_student = st.id_student

        LEFT JOIN tbl_trial_student ts
            ON s.id_trial_student = ts.id_trial_student

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
            a.status,
            a.id_attendance
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
        id_attendnace = r[6]

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
            "status": status,
            "id_attendance": id_attendnace
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

        if teacher_id not in schedule_map:
            continue

        if slot_key not in schedule_map[teacher_id]["slots"]:
            continue

        # New trial student table
        is_new_trial = bool(r[12])

        # Old tbl_student.is_trial
        is_old_trial = bool(r[8])

        # Any trial
        is_trial = is_new_trial or is_old_trial

        if is_new_trial:

            student_name = r[9]      # ts.name
            dob = r[10]              # ts.dob

        else:

            student_name = r[6]      # st.name
            dob = r[7]               # st.dob

        age = calculate_age(dob)

        schedule_map[teacher_id]["slots"][slot_key].append({

            "id_schedule": r[0],

            "student_name": student_name,

            "age": age,

            "level": r[5],

            "status": r[11],

            "is_trial": is_trial
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

        term = request.form['form_term']

        start_date = datetime.strptime(
            request.form['form_start_date'],
            "%Y-%m-%d"
        ).date()

        class_day = request.form['form_class_day'].upper().strip()

        level = int(request.form['form_level'])

        time_slot = request.form['form_time_slot']
        start_time, end_time = time_slot.split("|")

        teacher = int(request.form['form_teacher'])

        student = None
        id_trial_student = None

        if term == "TRIAL":

            term = 0
            total_meetings = 1

            student_name = request.form['form_trial_student_name']
            dob = request.form['form_trial_dob']
            parent_name = request.form['form_trial_parent_name']
            parent_telp = request.form['form_trial_parent_telp']

        else:

            term = int(term)

            student = int(
                request.form['form_student']
            )

            total_meetings = int(
                request.form['form_total_meetings']
            )

        day_map = {
            'MON': 0,
            'TUE': 1,
            'WED': 2,
            'THU': 3,
            'FRI': 4,
            'SAT': 5
        }

        target_weekday = day_map[class_day]

        current_date = start_date

        while current_date.weekday() != target_weekday:
            current_date += timedelta(days=1)

        first_class_date = current_date

        # ==================================
        # INSERT TRIAL STUDENT
        # ==================================

        if term == 0:

            cur.execute("""
                INSERT INTO tbl_trial_student
                (
                    name,
                    dob,
                    parent_name,
                    parent_telp,
                    trial_date,
                    id_admin
                )
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                student_name,
                dob,
                parent_name,
                parent_telp,
                first_class_date,
                session['id_admin']
            ))

            id_trial_student = cur.lastrowid

        # ==================================
        # MASTER SCHEDULE
        # ==================================

        cur.execute("""
            INSERT INTO tbl_master_schedule
            (
                term,
                start_date,
                class_day,
                id_level,
                start_time,
                end_time,
                id_teacher,
                id_student,
                id_trial_student,
                total_meetings,
                id_admin
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            term,
            start_date,
            class_day,
            level,
            start_time,
            end_time,
            teacher,
            student,
            id_trial_student,
            total_meetings,
            session['id_admin']
        ))

        id_master_schedule = cur.lastrowid

        # ==================================
        # CREATE SCHEDULES
        # ==================================

        for _ in range(total_meetings):

            cur.execute("""
                INSERT INTO tbl_schedule
                (
                    date,
                    start_time,
                    end_time,
                    id_teacher,
                    id_level,
                    id_master_schedule,
                    id_trial_student,
                    id_admin
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                current_date,
                start_time,
                end_time,
                teacher,
                level,
                id_master_schedule,
                id_trial_student,
                session['id_admin']
            ))

            id_schedule = cur.lastrowid

            # regular students only
            if student is not None:

                cur.execute("""
                    INSERT INTO tbl_attendance
                    (
                        id_schedule,
                        id_student,
                        id_admin
                    )
                    VALUES (%s,%s,%s)
                """, (
                    id_schedule,
                    student,
                    session['id_admin']
                ))

            current_date += timedelta(days=7)

        mysql.connection.commit()

        cur.close()

        flash(
            "Schedule successfully added",
            "success"
        )

        return redirect(
            url_for(
                'schedule',
                date=first_class_date.strftime("%Y-%m-%d")
            )
        )

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
  return render_template('admin/schedule/edit_schedule.html', data_schedule=schedule, data_teacher=teachers, data_student=updated_students, data_current_student=current_students, data_level=levels, time_slots=TIME_SLOTS)

# PROCESS EDIT SCHEDULE
def model_process_edit_schedule():
  id_schedule = request.form['form_id_schedule']
  date = request.form['form_date']
  level = request.form['form_level']
  time_slot = request.form['form_time_slot']
  start_time, end_time = time_slot.split('|')
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
  return redirect(url_for("schedule", date=date))

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
    time_slot = request.form['form_time_slot']
    start_time, end_time = time_slot.split("|")
    teacher = int(request.form['form_teacher'])
    student = int(request.form['form_student'])
    total_meetings = int(request.form['form_total_meetings'])

    cur = mysql.connection.cursor()

    # =========================
    # 1️⃣ UPDATE MASTER
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
        start_time, end_time, teacher,
        student, total_meetings,
        id_master, session['id_admin']
    ))

    # =========================
    # 2️⃣ GET EXISTING SCHEDULES
    # =========================
    cur.execute("""
        SELECT id_schedule, date
        FROM tbl_schedule
        WHERE id_master_schedule=%s AND id_admin=%s
        ORDER BY date ASC, id_schedule ASC
    """, (id_master, session['id_admin']))

    schedules = cur.fetchall()

    enriched = []
    for s in schedules:
        enriched.append({
            "id": s[0],
            "date": s[1]
        })

    current_count = len(enriched)

    # =========================
    # 3️⃣ HANDLE REDUCE
    # =========================
    if total_meetings < current_count:

        to_delete = enriched[total_meetings:]

        for s in to_delete:
            sched_id = s["id"]

            cur.execute("""
                DELETE FROM tbl_attendance
                WHERE id_schedule=%s AND id_admin=%s
            """, (sched_id, session['id_admin']))

            cur.execute("""
                DELETE FROM tbl_schedule
                WHERE id_schedule=%s AND id_admin=%s
            """, (sched_id, session['id_admin']))

    # =========================
    # 4️⃣ HANDLE ADD
    # =========================
    elif total_meetings > current_count:

        # map day
        day_map = {
            'MON': 0,
            'TUE': 1,
            'WED': 2,
            'THU': 3,
            'FRI': 4,
            'SAT': 5
        }

        target_weekday = day_map[class_day]

        # determine last date
        if enriched:
            last_date = enriched[-1]["date"]
        else:
            last_date = start_date
            while last_date.weekday() != target_weekday:
                last_date += timedelta(days=1)

        new_needed = total_meetings - current_count

        for _ in range(new_needed):

            last_date += timedelta(days=7)

            cur.execute("""
                INSERT INTO tbl_schedule
                (date, start_time, end_time, id_teacher,
                 id_level, id_master_schedule, id_admin)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                last_date,
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

    # =========================
    # 5️⃣ REGENERATE DATES
    # =========================

    # map day
    day_map = {
        'MON': 0,
        'TUE': 1,
        'WED': 2,
        'THU': 3,
        'FRI': 4,
        'SAT': 5
    }

    target_weekday = day_map[class_day]

    # find first valid class date
    current_date = start_date

    while current_date.weekday() != target_weekday:
        current_date += timedelta(days=1)

    # get all schedules again
    cur.execute("""
        SELECT id_schedule
        FROM tbl_schedule
        WHERE id_master_schedule=%s
        AND id_admin=%s
        ORDER BY date ASC, id_schedule ASC
    """, (id_master, session['id_admin']))

    schedule_ids = cur.fetchall()

    # update every schedule sequentially
    for row in schedule_ids:

        sched_id = row[0]

        cur.execute("""
            UPDATE tbl_schedule
            SET
                date=%s,
                start_time=%s,
                end_time=%s,
                id_teacher=%s,
                id_level=%s
            WHERE id_schedule=%s
            AND id_admin=%s
        """, (
            current_date,
            start_time,
            end_time,
            teacher,
            level,
            sched_id,
            session['id_admin']
        ))

        # ✅ RESET ATTENDANCE STATUS
        # cur.execute("""
        #     UPDATE tbl_attendance
        #     SET status = NULL
        #     WHERE id_schedule=%s
        #     AND id_admin=%s
        # """, (
        #     sched_id,
        #     session['id_admin']
        # ))

        current_date += timedelta(days=7)

    mysql.connection.commit()
    cur.close()

    flash("Master schedule updated successfully", "success")
    return redirect(url_for("schedule"))

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

    today = indo_time_today()
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

  cur.execute("""
    SELECT
        tbl_attendance.id_attendance,
        tbl_student.name,
        tbl_attendance.status,
        tbl_schedule.date
    FROM tbl_attendance
    JOIN tbl_student
        ON tbl_attendance.id_student = tbl_student.id_student
    JOIN tbl_schedule
        ON tbl_attendance.id_schedule = tbl_schedule.id_schedule
    WHERE tbl_attendance.id_schedule=%s
    AND tbl_attendance.id_admin=%s
    """, (id, session['id_admin']))

  data = cur.fetchall()
  cur.close()

  # convert to list of dicts for json
  students = []
  for row in data:
    students.append({
      'id_ss': row[0],
      'name': row[1],
      'status': row[2],
      'date': row[3].strftime("%A, %d %B %Y")
    })
  return jsonify(students)

# GET ATTENDANCE BY ATTENDANCE ID
def model_get_attendance_by_attendance(id_attendance):

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            tbl_attendance.id_attendance,
            tbl_student.name,
            tbl_attendance.status,
            tbl_schedule.date
        FROM tbl_attendance
        JOIN tbl_student
            ON tbl_attendance.id_student = tbl_student.id_student
        JOIN tbl_schedule
            ON tbl_attendance.id_schedule = tbl_schedule.id_schedule
        WHERE tbl_attendance.id_attendance=%s
        AND tbl_attendance.id_admin=%s
    """, (id_attendance, session['id_admin']))

    data = cur.fetchall()

    cur.close()

    students = []

    for row in data:
        students.append({
            'id_ss': row[0],
            'name': row[1],
            'status': row[2],
            'date': row[3].strftime("%A, %d %B %Y")
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
