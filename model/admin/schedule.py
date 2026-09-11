from flask import render_template, redirect, url_for, request, flash, jsonify, session
from db import mysql
from datetime import date, datetime, timedelta
import calendar


# =========================================================
# CONSTANTS
# =========================================================

DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]

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

TERM_MONTHS = {
    1: [1, 2, 3],
    2: [4, 5, 6],
    3: [7, 8, 9],
    4: [10, 11, 12]
}


# =========================================================
# DATE / TERM HELPERS
# =========================================================

def get_term_from_month(month):
    if 1 <= month <= 3:
        return 1
    elif 4 <= month <= 6:
        return 2
    elif 7 <= month <= 9:
        return 3
    else:
        return 4


def get_current_year():
    return date.today().year


def get_current_month():
    return date.today().month


def get_current_term():
    return get_term_from_month(get_current_month())


def month_to_word(month_number):
    return calendar.month_name[int(month_number)]


def calculate_age(dob):
    if not dob:
        return ""

    if isinstance(dob, datetime):
        dob = dob.date()
    elif isinstance(dob, str):
        parsed = None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(dob.strip(), fmt).date()
                break
            except ValueError:
                pass
        dob = parsed

    if not dob:
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
# =========================================================
# STUDENT STATUS
# =========================================================

def get_effective_student_period(cur, id_student, year, month):
    """
    Get the latest student period that is effective
    for the selected year + month.
    """

    cur.execute("""
        SELECT
            sp.id_teacher,
            sp.status,
            sp.id_level,
            sp.class_type,
            sp.year,
            sp.month,
            t.name
        FROM tbl_student_period sp
        LEFT JOIN tbl_teacher t
            ON sp.id_teacher = t.id_teacher
        WHERE sp.id_student = %s
          AND (
                sp.year < %s
                OR (sp.year = %s AND sp.month <= %s)
              )
        ORDER BY sp.year DESC, sp.month DESC
        LIMIT 1
    """, (
        id_student,
        year,
        year,
        month
    ))

    return cur.fetchone()


def is_current_student(cur, id_student, year, month):
    """
    Returns True only when the student's effective status
    for the selected year/month is 'Current Student'.
    """

    period = get_effective_student_period(
        cur,
        id_student,
        year,
        month
    )

    if not period:
        return False

    status = period[1]

    return str(status).strip().lower() == "current student"


# =========================================================
# BUILD TEACHER SCHEDULE MAP
# =========================================================

def build_teacher_schedule_map(selected_day):
    """
    Build the recurring teacher schedule for one day.

    Structure:

    {
        teacher_id: {
            "id_teacher": ...,
            "name": ...,
            "slots": {
                ("09:00", "10:00"): [
                    student rows...
                ]
            }
        }
    }
    """

    cur = mysql.connection.cursor()

    admin_id = session["id_admin"]

    # -----------------------------------------------------
    # GET ALL TEACHERS
    # -----------------------------------------------------

    cur.execute("""
        SELECT
            id_teacher,
            name
        FROM tbl_teacher
        WHERE id_admin = %s
        ORDER BY name
    """, (admin_id,))

    teacher_rows = cur.fetchall()

    teacher_map = {}

    for teacher_id, teacher_name in teacher_rows:

        teacher_map[teacher_id] = {
            "id_teacher": teacher_id,
            "name": teacher_name,
            "slots": {}
        }

        for start_time, end_time in TIME_SLOTS:
            teacher_map[teacher_id]["slots"][
                (start_time, end_time)
            ] = []

    # -----------------------------------------------------
    # GET RECURRING SCHEDULE
    # -----------------------------------------------------

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

        LEFT JOIN tbl_student st
            ON ts.id_student = st.id_student

        LEFT JOIN tbl_trial_student tr
            ON ts.id_trial_student = tr.id_trial_student

        LEFT JOIN tbl_level l
            ON ts.id_level = l.id_level

        WHERE ts.id_admin = %s
          AND ts.class_day = %s

        ORDER BY
            ts.id_teacher,
            ts.start_time,
            COALESCE(st.name, tr.name)
    """, (
        admin_id,
        selected_day
    ))

    schedule_rows = cur.fetchall()

    for row in schedule_rows:

        (
            id_teacher_schedule,
            id_teacher,
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

        if id_teacher not in teacher_map:
            continue

        slot_key = (
            str(start_time)[:5],
            str(end_time)[:5]
        )

        if slot_key not in teacher_map[id_teacher]["slots"]:
            teacher_map[id_teacher]["slots"][slot_key] = []

        # -------------------------------------------------
        # STUDENT TYPE
        # -------------------------------------------------

        if id_student:
            student_type = "current"
            display_name = student_name
        else:
            student_type = "trial"
            display_name = trial_name

        teacher_map[id_teacher]["slots"][slot_key].append({
            "id_teacher_schedule": id_teacher_schedule,
            "id_student": id_student,
            "id_trial_student": id_trial_student,
            "student_type": student_type,
            "name": display_name or "",
            "age": calculate_age(student_dob if id_student else trial_dob),
            "id_level": id_level,
            "level_name": level_name or "",
            "notes": notes or ""
        })

    cur.close()

    return teacher_map


# =========================================================
# MAIN SCHEDULE PAGE
# =========================================================

def model_schedule():
    today = date.today()
    selected_day = request.args.get("day", "").upper()

    if selected_day not in DAYS:
        selected_day = today.strftime("%a").upper()
        if selected_day not in DAYS:
            selected_day = "MON"

    # -----------------------------------------------------
    # ATTENDANCE FILTER
    # -----------------------------------------------------

    today = date.today()

    try:
        attendance_year = int(
            request.args.get("attendance_year", today.year)
        )
    except (TypeError, ValueError):
        attendance_year = today.year

    try:
        attendance_term = int(
            request.args.get(
                "attendance_term",
                get_term_from_month(today.month)
            )
        )
    except (TypeError, ValueError):
        attendance_term = get_term_from_month(today.month)

    if attendance_term not in (1, 2, 3, 4):
        attendance_term = get_term_from_month(today.month)

    # -----------------------------------------------------
    # LOAD SCHEDULE
    # -----------------------------------------------------

    schedule_map = build_teacher_schedule_map(selected_day)

    # -----------------------------------------------------
    # LOAD LEVELS
    # -----------------------------------------------------

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            id_level,
            level_name,
            age_range
        FROM tbl_level
        WHERE id_admin = %s
        ORDER BY
            CAST(
                SUBSTRING_INDEX(age_range, '-', 1)
                AS DECIMAL(4,2)
            )
    """, (session["id_admin"],))

    levels = cur.fetchall()

    cur.close()

    # -----------------------------------------------------
    # LOAD ATTENDANCE STUDENTS
    # -----------------------------------------------------

    attendance_students = get_attendance_students(
        attendance_year,
        attendance_term
    )

    # -----------------------------------------------------
    # LOAD ATTENDANCE RECORDS
    # -----------------------------------------------------

    attendance_records = get_attendance_records(
        attendance_year,
        attendance_term
    )

    return render_template(
        "admin/schedule/schedule.html",

        # Teacher schedule
        selected_day=selected_day,
        days=DAYS,
        time_slots=TIME_SLOTS,
        schedule_map=schedule_map,

        # Dropdowns
        levels=levels,

        # Attendance
        attendance_year=attendance_year,
        attendance_term=attendance_term,
        attendance_students=attendance_students,
        attendance_records=attendance_records
    )


# =========================================================
# GET CURRENT STUDENTS FOR ADD STUDENT MODAL
# =========================================================

def get_current_students():

    cur = mysql.connection.cursor()

    admin_id = session["id_admin"]

    today = date.today()

    cur.execute("""
        SELECT
            id_student,
            name,
            dob
        FROM tbl_student
        WHERE id_admin = %s
          AND (is_trial = 0 OR is_trial IS NULL)
        ORDER BY name
    """, (admin_id,))

    rows = cur.fetchall()

    students = []

    for student_id, name, dob in rows:

        if is_current_student(
            cur,
            student_id,
            today.year,
            today.month
        ):
            students.append({
                "id_student": student_id,
                "name": name,
                "age": calculate_age(dob)
            })

    cur.close()

    return students


# =========================================================
# GET TRIAL STUDENTS
# =========================================================

def get_trial_students():

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            id_trial_student,
            name,
            dob,
            trial_date
        FROM tbl_trial_student
        WHERE id_admin = %s
        ORDER BY
            trial_date DESC,
            name
    """, (session["id_admin"],))

    rows = cur.fetchall()

    cur.close()

    return [
        {
            "id_trial_student": row[0],
            "name": row[1],
            "age": calculate_age(row[2]),
            "trial_date": row[3].strftime("%Y-%m-%d")
                if row[3] else ""
        }
        for row in rows
    ]


# =========================================================
# API: GET STUDENTS FOR ADD MODAL
# =========================================================

def model_get_schedule_students():

    try:

        current_students = get_current_students()
        trial_students = get_trial_students()

        return jsonify({
            "success": True,
            "current_students": current_students,
            "trial_students": trial_students
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# ADD STUDENT TO RECURRING TEACHER SCHEDULE
# =========================================================

def model_add_teacher_schedule():

    cur = mysql.connection.cursor()

    try:

        admin_id = session["id_admin"]

        # -------------------------------------------------
        # FORM DATA
        # -------------------------------------------------

        id_teacher = request.form.get("id_teacher")
        class_day = request.form.get("class_day", "").upper()
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        student_type = request.form.get("student_type")

        id_student = request.form.get("id_student")
        id_trial_student = request.form.get("id_trial_student")

        id_level = request.form.get("id_level")
        notes = request.form.get("notes", "").strip()

        # -------------------------------------------------
        # BASIC VALIDATION
        # -------------------------------------------------

        if not id_teacher:
            raise Exception("Teacher is required.")

        if class_day not in DAYS:
            raise Exception("Invalid class day.")

        if not start_time or not end_time:
            raise Exception("Start time and end time are required.")

        if student_type not in ("current", "trial"):
            raise Exception("Invalid student type.")

        if not id_level:
            raise Exception("Level is required.")

        # -------------------------------------------------
        # VERIFY TEACHER
        # -------------------------------------------------

        cur.execute("""
            SELECT id_teacher
            FROM tbl_teacher
            WHERE id_teacher = %s
              AND id_admin = %s
            LIMIT 1
        """, (
            id_teacher,
            admin_id
        ))

        if not cur.fetchone():
            raise Exception("Teacher not found.")

        # -------------------------------------------------
        # DETERMINE STUDENT
        # -------------------------------------------------

        if student_type == "current":

            if not id_student:
                raise Exception("Please select a student.")

            id_student = int(id_student)

            # Make sure student belongs to this admin
            cur.execute("""
                SELECT id_student
                FROM tbl_student
                WHERE id_student = %s
                  AND id_admin = %s
                  AND (is_trial = 0 OR is_trial IS NULL)
                LIMIT 1
            """, (
                id_student,
                admin_id
            ))

            if not cur.fetchone():
                raise Exception("Student not found.")

            # Check CURRENT status
            today = date.today()

            if not is_current_student(
                cur,
                id_student,
                today.year,
                today.month
            ):
                raise Exception(
                    "Only Current Students can be added "
                    "to the teacher schedule."
                )

            id_trial_student = None

        else:

            if not id_trial_student:
                raise Exception("Please select a trial student.")

            id_trial_student = int(id_trial_student)

            # Make sure trial belongs to this admin
            cur.execute("""
                SELECT id_trial_student
                FROM tbl_trial_student
                WHERE id_trial_student = %s
                  AND id_admin = %s
                LIMIT 1
            """, (
                id_trial_student,
                admin_id
            ))

            if not cur.fetchone():
                raise Exception("Trial student not found.")

            id_student = None

        # -------------------------------------------------
        # CHECK SLOT LIMIT
        # -------------------------------------------------

        cur.execute("""
            SELECT COUNT(*)
            FROM tbl_teacher_schedule
            WHERE id_teacher = %s
              AND class_day = %s
              AND start_time = %s
              AND end_time = %s
              AND id_admin = %s
        """, (
            id_teacher,
            class_day,
            start_time,
            end_time,
            admin_id
        ))

        slot_count = cur.fetchone()[0]

        if slot_count >= 6:
            raise Exception(
                "This time slot already has 6 students."
            )

        # -------------------------------------------------
        # CHECK DUPLICATE CURRENT STUDENT
        # -------------------------------------------------

        if id_student:

            cur.execute("""
                SELECT id_teacher_schedule
                FROM tbl_teacher_schedule
                WHERE id_teacher = %s
                  AND class_day = %s
                  AND start_time = %s
                  AND end_time = %s
                  AND id_student = %s
                  AND id_admin = %s
                LIMIT 1
            """, (
                id_teacher,
                class_day,
                start_time,
                end_time,
                id_student,
                admin_id
            ))

            if cur.fetchone():
                raise Exception(
                    "This student is already assigned "
                    "to this time slot."
                )

        # -------------------------------------------------
        # CHECK DUPLICATE TRIAL STUDENT
        # -------------------------------------------------

        if id_trial_student:

            cur.execute("""
                SELECT id_teacher_schedule
                FROM tbl_teacher_schedule
                WHERE id_teacher = %s
                  AND class_day = %s
                  AND start_time = %s
                  AND end_time = %s
                  AND id_trial_student = %s
                  AND id_admin = %s
                LIMIT 1
            """, (
                id_teacher,
                class_day,
                start_time,
                end_time,
                id_trial_student,
                admin_id
            ))

            if cur.fetchone():
                raise Exception(
                    "This trial student is already assigned "
                    "to this time slot."
                )

        # -------------------------------------------------
        # VERIFY LEVEL
        # -------------------------------------------------

        cur.execute("""
            SELECT id_level
            FROM tbl_level
            WHERE id_level = %s
              AND id_admin = %s
            LIMIT 1
        """, (
            id_level,
            admin_id
        ))

        if not cur.fetchone():
            raise Exception("Invalid level.")

        # -------------------------------------------------
        # INSERT RECURRING SCHEDULE
        # -------------------------------------------------

        cur.execute("""
            INSERT INTO tbl_teacher_schedule
            (
                id_teacher,
                class_day,
                start_time,
                end_time,
                id_student,
                id_trial_student,
                id_level,
                notes,
                id_admin
            )
            VALUES
            (
                %s,%s,%s,%s,%s,%s,%s,%s,%s
            )
        """, (
            id_teacher,
            class_day,
            start_time,
            end_time,
            id_student,
            id_trial_student,
            id_level,
            notes,
            admin_id
        ))

        mysql.connection.commit()

        flash(
            "Student successfully added to the schedule.",
            "success"
        )

    except Exception as e:

        mysql.connection.rollback()

        flash(
            f"Error adding student: {str(e)}",
            "danger"
        )

    finally:

        cur.close()

    return redirect(url_for("schedule",day=class_day))


# =========================================================
# EDIT STUDENT FROM RECURRING TEACHER SCHEDULE
# =========================================================

def model_edit_teacher_schedule(schedule_id):
    if request.method != "POST":
        return redirect(url_for("schedule"))

    id_teacher = request.form.get("id_teacher")
    class_day = request.form.get("class_day")
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")

    student_type = request.form.get("student_type")

    id_student = request.form.get("id_student") if student_type == "current" else None
    id_trial_student = request.form.get("id_trial_student") if student_type == "trial" else None

    id_level = request.form.get("id_level")
    notes = request.form.get("notes", "").strip()

    if not id_level:
        flash("Please select a level.", "danger")
        return redirect(url_for("schedule", day=class_day))

    cursor = mysql.connection.cursor()

    cursor.execute("""
        UPDATE tbl_teacher_schedule
        SET
            id_student = %s,
            id_trial_student = %s,
            id_level = %s,
            notes = %s
        WHERE id_teacher_schedule = %s
    """, (
        id_student or None,
        id_trial_student or None,
        id_level,
        notes or None,
        schedule_id
    ))

    mysql.connection.commit()
    cursor.close()

    flash("Student schedule updated successfully.", "success")

    return redirect(
        url_for(
            "schedule",
            day=class_day
        )
    )

# =========================================================
# DELETE STUDENT FROM RECURRING SCHEDULE
# =========================================================

def model_delete_teacher_schedule(id):

    cur = mysql.connection.cursor()

    try:

        # -------------------------------------------------
        # VERIFY OWNERSHIP
        # -------------------------------------------------

        cur.execute("""
            SELECT
                class_day
            FROM tbl_teacher_schedule
            WHERE id_teacher_schedule = %s
              AND id_admin = %s
            LIMIT 1
        """, (
            id,
            session["id_admin"]
        ))

        row = cur.fetchone()

        if not row:
            raise Exception("Schedule entry not found.")

        class_day = row[0]

        # -------------------------------------------------
        # DELETE
        # -------------------------------------------------

        cur.execute("""
            DELETE FROM tbl_teacher_schedule
            WHERE id_teacher_schedule = %s
              AND id_admin = %s
        """, (
            id,
            session["id_admin"]
        ))

        mysql.connection.commit()

        flash(
            "Student removed from the schedule.",
            "success"
        )

    except Exception as e:

        mysql.connection.rollback()

        flash(
            f"Error deleting schedule: {str(e)}",
            "danger"
        )

        class_day = request.args.get("day", "MON")

    finally:

        cur.close()

    return redirect(
        url_for(
            "schedule",
            day=class_day
        )
    )





# =========================================================
# ATTENDANCE — GET CURRENT STUDENTS
# =========================================================

def get_attendance_students(year, term):

    cur = mysql.connection.cursor()

    admin_id = session["id_admin"]

    # -----------------------------------------------------
    # TERM → USE THE LAST MONTH OF THE TERM
    # -----------------------------------------------------

    months = TERM_MONTHS[term]
    reference_month = months[-1]

    # -----------------------------------------------------
    # GET STUDENTS
    # -----------------------------------------------------

    cur.execute("""
        SELECT
            id_student,
            name,
            dob
        FROM tbl_student
        WHERE id_admin = %s
          AND (is_trial = 0 OR is_trial IS NULL)
        ORDER BY name
    """, (admin_id,))

    rows = cur.fetchall()

    students = []

    for student_id, name, dob in rows:

        period = get_effective_student_period(
            cur,
            student_id,
            year,
            reference_month
        )

        if not period:
            continue

        status = period[1]

        if (
            status
            and str(status).strip().lower()
            == "current student"
        ):
            students.append({
                "id_student": student_id,
                "name": name,
                "age": calculate_age(dob)
            })

    cur.close()

    return students


# =========================================================
# ATTENDANCE — GET RECORDS
# =========================================================

def get_attendance_records(year, term):

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            id_student_attendance,
            id_student,
            meeting_number,
            class_date,
            status
        FROM tbl_student_attendance
        WHERE year = %s
          AND term = %s
          AND id_admin = %s
        ORDER BY
            id_student,
            meeting_number
    """, (
        year,
        term,
        session["id_admin"]
    ))

    rows = cur.fetchall()

    cur.close()

    records = {}

    for row in rows:

        (
            attendance_id,
            student_id,
            meeting_number,
            class_date,
            status
        ) = row

        student_key = str(student_id)
        meeting_key = str(meeting_number)

        if student_key not in records:
            records[student_key] = {}

        records[student_key][meeting_key] = {
            "id_student_attendance": attendance_id,
            "class_date": (
                class_date.strftime("%Y-%m-%d")
                if class_date
                else None
            ),
            "status": status
        }

    return records


# =========================================================
# API — GET ATTENDANCE
# =========================================================

def model_get_student_attendance():

    try:

        year = int(request.args.get("year"))
        term = int(request.args.get("term"))

        if term not in (1, 2, 3, 4):
            raise Exception("Invalid term.")

        students = get_attendance_students(
            year,
            term
        )

        records = get_attendance_records(
            year,
            term
        )

        return jsonify({
            "success": True,
            "students": students,
            "records": records
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# API — GET ONE ATTENDANCE RECORD
# =========================================================

def model_get_student_attendance_record():

    try:

        attendance_id = request.args.get(
            "id_student_attendance"
        )

        if not attendance_id:
            raise Exception(
                "Attendance ID is required."
            )

        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT
                id_student_attendance,
                id_student,
                year,
                term,
                meeting_number,
                class_date,
                status
            FROM tbl_student_attendance
            WHERE id_student_attendance = %s
              AND id_admin = %s
            LIMIT 1
        """, (
            attendance_id,
            session["id_admin"]
        ))

        row = cur.fetchone()

        cur.close()

        if not row:
            raise Exception(
                "Attendance record not found."
            )

        return jsonify({
            "success": True,
            "attendance": {
                "id_student_attendance": row[0],
                "id_student": row[1],
                "year": row[2],
                "term": row[3],
                "meeting_number": row[4],
                "class_date": (
                    row[5].strftime("%Y-%m-%d")
                    if row[5]
                    else ""
                ),
                "status": row[6]
            }
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# SAVE ATTENDANCE
# =========================================================

def model_save_student_attendance():

    cur = mysql.connection.cursor()

    try:

        admin_id = session["id_admin"]

        data = request.get_json()

        if not data:
            raise Exception("No data received.")

        id_student = data.get("id_student")
        year = data.get("year")
        term = data.get("term")
        meeting_number = data.get("meeting_number")
        class_date = data.get("class_date")
        status = data.get("status", "None")

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if not id_student:
            raise Exception("Student is required.")

        if not year:
            raise Exception("Year is required.")

        if term not in (1, 2, 3, 4):
            term = int(term)

        if term not in (1, 2, 3, 4):
            raise Exception("Invalid term.")

        meeting_number = int(meeting_number)

        if meeting_number < 1 or meeting_number > 10:
            raise Exception(
                "Meeting number must be between 1 and 10."
            )

        if status not in (
            "None",
            "Absent",
            "Present"
        ):
            raise Exception("Invalid attendance status.")

        # -------------------------------------------------
        # VERIFY STUDENT
        # -------------------------------------------------

        cur.execute("""
            SELECT id_student
            FROM tbl_student
            WHERE id_student = %s
              AND id_admin = %s
            LIMIT 1
        """, (
            id_student,
            admin_id
        ))

        if not cur.fetchone():
            raise Exception("Student not found.")

        # -------------------------------------------------
        # NORMALIZE DATE
        # -------------------------------------------------

        if class_date:

            try:
                parsed_date = datetime.strptime(
                    class_date,
                    "%Y-%m-%d"
                ).date()

            except ValueError:
                raise Exception(
                    "Invalid class date."
                )

        else:
            parsed_date = None

        # -------------------------------------------------
        # UPSERT ATTENDANCE
        # -------------------------------------------------

        cur.execute("""
            SELECT id_student_attendance
            FROM tbl_student_attendance
            WHERE id_student = %s
              AND year = %s
              AND term = %s
              AND meeting_number = %s
              AND id_admin = %s
            LIMIT 1
        """, (
            id_student,
            year,
            term,
            meeting_number,
            admin_id
        ))

        existing = cur.fetchone()

        if existing:

            cur.execute("""
                UPDATE tbl_student_attendance
                SET
                    class_date = %s,
                    status = %s
                WHERE id_student_attendance = %s
                  AND id_admin = %s
            """, (
                parsed_date,
                status,
                existing[0],
                admin_id
            ))

        else:

            cur.execute("""
                INSERT INTO tbl_student_attendance
                (
                    id_student,
                    year,
                    term,
                    meeting_number,
                    class_date,
                    status,
                    id_admin
                )
                VALUES
                (
                    %s,%s,%s,%s,%s,%s,%s
                )
            """, (
                id_student,
                year,
                term,
                meeting_number,
                parsed_date,
                status,
                admin_id
            ))

        mysql.connection.commit()

        return jsonify({
            "success": True,
            "message": "Attendance saved successfully."
        })

    except Exception as e:

        mysql.connection.rollback()

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:

        cur.close()


# =========================================================
# DELETE / CLEAR ATTENDANCE
# =========================================================

def model_delete_student_attendance():

    cur = mysql.connection.cursor()

    try:

        data = request.get_json()

        if not data:
            raise Exception("No data received.")

        id_student = data.get("id_student")
        year = int(data.get("year"))
        term = int(data.get("term"))
        meeting_number = int(
            data.get("meeting_number")
        )

        cur.execute("""
            DELETE FROM tbl_student_attendance
            WHERE id_student = %s
              AND year = %s
              AND term = %s
              AND meeting_number = %s
              AND id_admin = %s
        """, (
            id_student,
            year,
            term,
            meeting_number,
            session["id_admin"]
        ))

        mysql.connection.commit()

        return jsonify({
            "success": True,
            "message": "Attendance cleared."
        })

    except Exception as e:

        mysql.connection.rollback()

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:

        cur.close()


# =========================================================
# PRINT SCHEDULE
# =========================================================

def model_print_schedule():

    selected_day = request.args.get(
        "day",
        "MON"
    ).upper()

    if selected_day not in DAYS:
        selected_day = "MON"

    schedule_map = build_teacher_schedule_map(
        selected_day
    )

    return render_template(
        "admin/schedule/print_schedule.html",
        selected_day=selected_day,
        days=DAYS,
        time_slots=TIME_SLOTS,
        schedule_map=schedule_map
    )