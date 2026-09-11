from flask import render_template, request
from db import mysql
from datetime import date, datetime
from zoneinfo import ZoneInfo


DAYS = [
    "MON",
    "TUE",
    "WED",
    "THU",
    "FRI",
    "SAT"
]


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


# =========================================================
# INDONESIA TODAY
# =========================================================

def indo_time_today():
    return datetime.now(
        ZoneInfo("Asia/Jakarta")
    ).date()


# =========================================================
# CALCULATE AGE
# =========================================================

def calculate_age(dob):

    if not dob:
        return ""

    if isinstance(dob, str):

        dob = dob.strip()

        if not dob:
            return ""

        parsed = None

        for fmt in (
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d"
        ):
            try:
                parsed = datetime.strptime(
                    dob,
                    fmt
                ).date()
                break
            except ValueError:
                pass

        dob = parsed

    elif isinstance(dob, datetime):
        dob = dob.date()

    if not dob:
        return ""

    today = indo_time_today()

    years = today.year - dob.year
    months = today.month - dob.month

    if today.day < dob.day:
        months -= 1

    if months < 0:
        years -= 1
        months += 12

    return f"{years}.{months:02d}"


# =========================================================
# TEACHER SCHEDULE PAGE
# =========================================================

def model_teacher_schedule(branch_name):

    cur = mysql.connection.cursor()

    # =====================================================
    # SELECTED DAY
    # Automatically use today's day
    # =====================================================

    selected_day = request.args.get(
        "day",
        ""
    ).upper()

    if selected_day not in DAYS:

        selected_day = indo_time_today().strftime(
            "%a"
        ).upper()

        if selected_day not in DAYS:
            selected_day = "MON"

    # =====================================================
    # GET TEACHERS FOR THIS BRANCH
    # =====================================================

    cur.execute("""
        SELECT
            t.id_teacher,
            t.name

        FROM tbl_teacher t

        JOIN tbl_admin a
            ON t.id_admin = a.id_admin

        JOIN tbl_branch b
            ON a.id_branch = b.id_branch

        WHERE LOWER(b.branch_name) = LOWER(%s)

        ORDER BY
            t.name ASC
    """, (
        branch_name,
    ))

    teacher_rows = cur.fetchall()

    # =====================================================
    # BUILD EMPTY TEACHER MAP
    # =====================================================

    schedule_map = {}

    for teacher_id, teacher_name in teacher_rows:

        schedule_map[teacher_id] = {
            "id_teacher": teacher_id,
            "name": teacher_name,
            "slots": {}
        }

        for start_time, end_time in TIME_SLOTS:

            schedule_map[teacher_id]["slots"][
                (start_time, end_time)
            ] = []

    # =====================================================
    # GET RECURRING TEACHER SCHEDULE
    # =====================================================

    cur.execute("""
        SELECT

            ts.id_teacher_schedule,
            ts.id_teacher,
            ts.class_day,
            ts.start_time,
            ts.end_time,

            ts.id_student,
            ts.id_trial_student,

            ts.id_level,
            ts.notes,

            st.name AS student_name,
            st.dob AS student_dob,

            tr.name AS trial_name,
            tr.dob AS trial_dob,

            l.level_name

        FROM tbl_teacher_schedule ts

        JOIN tbl_teacher t
            ON ts.id_teacher = t.id_teacher

        JOIN tbl_admin a
            ON ts.id_admin = a.id_admin

        JOIN tbl_branch b
            ON a.id_branch = b.id_branch

        LEFT JOIN tbl_student st
            ON ts.id_student = st.id_student

        LEFT JOIN tbl_trial_student tr
            ON ts.id_trial_student = tr.id_trial_student

        LEFT JOIN tbl_level l
            ON ts.id_level = l.id_level

        WHERE LOWER(b.branch_name) = LOWER(%s)

          AND ts.class_day = %s

        ORDER BY

            ts.id_teacher,
            ts.start_time,
            COALESCE(
                st.name,
                tr.name
            ) ASC
    """, (
        branch_name,
        selected_day
    ))

    schedule_rows = cur.fetchall()

    # =====================================================
    # FILL TEACHER SCHEDULE
    # =====================================================

    for row in schedule_rows:

        (
            id_teacher_schedule,
            teacher_id,
            class_day,
            start_time,
            end_time,

            id_student,
            id_trial_student,

            id_level,
            notes,

            student_name,
            student_dob,

            trial_name,
            trial_dob,

            level_name

        ) = row

        # -------------------------------------------------
        # Ignore teachers outside the branch
        # -------------------------------------------------

        if teacher_id not in schedule_map:
            continue

        slot_key = (
            str(start_time)[:5],
            str(end_time)[:5]
        )

        # -------------------------------------------------
        # CURRENT / TRIAL
        # -------------------------------------------------

        if id_student:

            student_type = "current"
            display_name = student_name
            dob = student_dob

        else:

            student_type = "trial"
            display_name = trial_name
            dob = trial_dob

        # -------------------------------------------------
        # ADD STUDENT
        # -------------------------------------------------

        schedule_map[teacher_id]["slots"][
            slot_key
        ].append({

            "id_teacher_schedule":
                id_teacher_schedule,

            "id_student":
                id_student,

            "id_trial_student":
                id_trial_student,

            "student_type":
                student_type,

            "name":
                display_name or "",

            "age":
                calculate_age(dob),

            "id_level":
                id_level,

            "level_name":
                level_name or "",

            "notes":
                notes or ""

        })

    cur.close()

    # =====================================================
    # RENDER
    # =====================================================

    return render_template(

        "admin/teacher/teacher_schedule.html",

        selected_day=selected_day,

        days=DAYS,

        time_slots=TIME_SLOTS,

        schedule_map=schedule_map,

        branch_name=branch_name
    )