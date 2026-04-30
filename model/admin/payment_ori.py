from flask import render_template, request, redirect, url_for, flash, session
from db import mysql
from datetime import datetime

# PAYMENT
def model_payment():
    cur = mysql.connection.cursor()
    current_year = datetime.now().year

    cur.execute("""
        SELECT
            p.id_payment,
            s.name,
            p.term,
            p.year,
            p.registration_fee,
            p.late_fee,
            p.discount_type,
            p.discount_fee,
            p.payment_method,
            p.payment_date,
            p.status,
            p.tuition_fee
        FROM tbl_payment p
        JOIN tbl_student s ON p.id_student = s.id_student
        WHERE p.id_admin=%s
        ORDER BY
            CASE WHEN p.registration_fee IN ('yes','free') THEN 0 ELSE 1 END,  -- registration first
            p.year DESC,
            p.term,
            s.name
        """, (session['id_admin'],))

    rows = cur.fetchall()
    cur.close()

    data = []

    for r in rows:
        tuition = r[11] or 0
        reg_fee = str(r[4]).lower()
        late_fee = str(r[5]).lower()
        discount_fee = r[7] or 0

        total = tuition

        if reg_fee == "yes":
            total += 1000000
        elif reg_fee == "free":
            total += 0

        if late_fee == "yes":
            total += 250000

        total -= discount_fee
        if total < 0:
            total = 0

        data.append(r + (total,))

    return render_template(
        'admin/payment/payment.html',
        data_payment=data,
        current_year=current_year
    )
# EDIT PAYMENT
def model_edit_payment(id):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            p.id_payment,
            p.id_student,
            s.name,
            s.parent_name,
            s.parent_telp,
            p.term,
            p.registration_fee,
            p.late_fee,
            p.discount_type,
            p.discount_fee,
            p.payment_method,
            p.total_payment,
            p.payment_date,
            p.status,
            p.year,
            p.tuition_fee
        FROM tbl_payment p
        JOIN tbl_student s
        ON p.id_student = s.id_student
        WHERE p.id_payment=%s AND p.id_admin=%s
    """, (id, session['id_admin']))

    data = cur.fetchone()

    cur.execute("""
        SELECT id_student, name
        FROM tbl_student
        WHERE id_admin=%s
    """, (session['id_admin'],))

    students = cur.fetchall()
    cur.close()

    registration_paid = check_registration_paid(id_student=data[1])

    return render_template(
        'admin/payment/edit_payment.html',
        data_payment=data,
        data_student=students,
        registration_paid=registration_paid
    )

# PROCESS EDIT PAYMENT
def model_process_edit_payment():
    id_payment = request.form['form_id_payment']
    id_student = request.form['form_id_student']

    term = request.form['form_term']
    registration_fee = request.form['form_registration_fee']
    late_fee = request.form['form_late_fee']
    discount_type = request.form['form_discount_type']
    discount_fee = int(request.form['form_discount_fee'] or 0)
    payment_method = request.form['form_payment_method']
    payment_date = request.form['form_payment_date']
    status = request.form['form_status']
    tuition_fee = int(request.form['form_tuition_fee'])

    total_payment = tuition_fee
    if registration_fee == "yes":
        total_payment += 1000000
    elif registration_fee == "free":
        total_payment += 0

    if late_fee == "yes":
        total_payment += 250000

    total_payment -= discount_fee

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE tbl_payment
        SET
            id_student=%s,
            term=%s,
            registration_fee=%s,
            late_fee=%s,
            discount_type=%s,
            discount_fee=%s,
            payment_method=%s,
            total_payment=%s,
            payment_date=%s,
            status=%s,
            tuition_fee=%s
        WHERE id_payment=%s AND id_admin=%s
    """, (
        id_student,
        term,
        registration_fee,
        late_fee,
        discount_type,
        discount_fee,
        payment_method,
        total_payment,
        payment_date,
        status,
        tuition_fee,
        id_payment,
        session['id_admin']
    ))
    mysql.connection.commit()
    cur.close()

    flash("Payment successfully updated", "success")
    return redirect(url_for("payment"))

# DELETE PAYMENT
def model_delete_payment(id):
    cur = mysql.connection.cursor()
    cur.execute("""
        DELETE FROM tbl_payment
        WHERE id_payment=%s AND id_admin=%s
    """, (id, session['id_admin']))
    mysql.connection.commit()
    cur.close()
    flash("Payment successfully deleted", "success")
    return redirect(url_for("payment"))

def check_registration_paid(id_student):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM tbl_payment
        WHERE id_student=%s
        AND registration_fee IN ('yes','free')
    """, (id_student,))
    result = cur.fetchone()
    cur.close()
    return result[0] > 0