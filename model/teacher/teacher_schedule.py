from flask import render_template, request
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

# =========================================
# TEACHER SCHEDULE PAGE
# =========================================
def model_teacher_schedule(branch_name):

    cur = mysql.connection.cursor()

    # =========================================
    # SELECTED DATE
    # =========================================
    selected_date = request.args.get("date")

    if not selected_date:
        selected_date = indo_time_today().strftime("%Y-%m-%d")

    # =========================================
    # GET TEACHERS BY BRANCH
    # =========================================
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

        ORDER BY t.name ASC
    """, (branch_name,))

    teachers = cur.fetchall()

    # =========================================
    # GET SCHEDULES
    # =========================================
    cur.execute("""
        SELECT
            s.id_schedule,
            s.start_time,
            s.end_time,
            s.id_teacher,

            COALESCE(ts.name, st.name) AS student_name,
            COALESCE(ts.dob, st.dob) AS dob,

            CASE
                WHEN ts.id_trial_student IS NOT NULL THEN 1
                WHEN st.is_trial = 1 THEN 1
                ELSE 0
            END AS is_trial,

            l.level_name,

            att.status,

            s.is_rescheduled,
            s.reschedule_date

        FROM tbl_schedule s

        JOIN tbl_admin a
            ON s.id_admin = a.id_admin

        JOIN tbl_branch b
            ON a.id_branch = b.id_branch

        LEFT JOIN tbl_attendance att
            ON s.id_schedule = att.id_schedule

        LEFT JOIN tbl_student st
            ON att.id_student = st.id_student

        LEFT JOIN tbl_trial_student ts
            ON s.id_trial_student = ts.id_trial_student

        LEFT JOIN tbl_level l
            ON s.id_level = l.id_level

        WHERE DATE(s.date) = %s
        AND LOWER(b.branch_name) = LOWER(%s)

        ORDER BY s.id_teacher, s.start_time
    """, (
        selected_date,
        branch_name
    ))

    schedule_rows = cur.fetchall()

    # =========================================
    # BUILD EMPTY SCHEDULE MAP
    # =========================================
    schedule_map = {}

    for teacher_id, teacher_name in teachers:

        schedule_map[teacher_id] = {
            "teacher_name": teacher_name,
            "slots": {
                f"{start}-{end}": []
                for start, end in TIME_SLOTS
            }
        }

    # =========================================
    # FILL SLOTS
    # =========================================
    for r in schedule_rows:

        slot_key = f"{r[1]}-{r[2]}"
        teacher_id = r[3]

        if (
            teacher_id in schedule_map
            and slot_key in schedule_map[teacher_id]["slots"]
        ):

            age = calculate_age(r[5])

            # old trial data sometimes has empty DOB
            if r[6] and (not age or age == "-"):
                age = "0.00"

            schedule_map[teacher_id]["slots"][slot_key].append({
                "id_schedule": r[0],
                "student_name": r[4] if r[4] else "-",
                "age": age,
                "level": r[7],
                "status": r[8],
                "is_rescheduled": bool(r[9]),
                "reschedule_date": (
                    r[10].strftime("%d %b %Y")
                    if r[10] else None
                ),
                "is_trial": bool(r[6])
            })

    cur.close()

    # =========================================
    # RENDER PAGE
    # =========================================
    return render_template(
        "admin/teacher/teacher_schedule.html",
        selected_date=selected_date,
        schedule_map=schedule_map,
        time_slots=TIME_SLOTS,
        branch_name=branch_name
    )


# =========================================
# CALCULATE AGE
# =========================================
def calculate_age(dob):

    if not dob:
        return "-"

    if isinstance(dob, str):

        if dob.strip() == "":
            return "-"

        from datetime import datetime

        dob = datetime.strptime(
            dob,
            "%Y-%m-%d"
        ).date()

    today = indo_time_today()

    years = today.year - dob.year
    months = today.month - dob.month

    if today.day < dob.day:
        months -= 1

    if months < 0:
        years -= 1
        months += 12

    return f"{years}.{months:02d}"



# CALCULATE AGE
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
