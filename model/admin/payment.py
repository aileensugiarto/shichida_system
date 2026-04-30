from flask import render_template, request, redirect, url_for, flash, session
from db import mysql
from datetime import datetime

# =========================
# HELPER FUNCTION
# =========================
def clean_rupiah(value):
    if not value:
        return 0
    return int(''.join(filter(str.isdigit, value)))


# =========================
# PAYMENT
# =========================
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
            p.discount_type,
            p.discount_fee,
            p.payment_method,
            p.payment_date,
            p.tuition_fee,
            p.total_payment,
            p.registration_amount
        FROM tbl_payment p
        LEFT JOIN tbl_student s ON p.id_student = s.id_student
        WHERE p.id_admin=%s
        ORDER BY p.year DESC, p.term ASC, s.name ASC
    """, (session['id_admin'],))

    data = cur.fetchall()
    cur.close()

    return render_template(
        'admin/payment/payment.html',
        data_payment=data,
        current_year=current_year
    )


# =========================
# ADD PAYMENT
# =========================
def model_add_payment():
    cur = mysql.connection.cursor()

    if request.method == "POST":
        id_student = request.form['form_id_student']
        year = request.form['form_year']
        terms = request.form.getlist('form_term')

        if not terms:
            flash("Please select at least one term", "danger")
            return redirect(url_for("add_payment"))

        term_str = ",".join(terms)

        tuition_fee = clean_rupiah(request.form['form_tuition_fee'])
        registration_fee = request.form.get('form_registration_fee', 'no')
        registration_amount = clean_rupiah(request.form.get('form_registration_amount'))

        discount_type = request.form['form_discount_type']
        discount_fee = clean_rupiah(request.form.get('form_discount_fee'))

        payment_method = request.form['form_payment_method']
        payment_date = request.form['form_payment_date']

        # CHECK REGISTRATION ALREADY PAID BEFORE
        cur.execute("""
            SELECT COUNT(*)
            FROM tbl_payment
            WHERE id_student=%s
            AND registration_fee IN ('yes','free')
        """, (id_student,))
        already_paid = cur.fetchone()[0] > 0

        # FINAL VALUE
        if already_paid:
            reg_fee_value = "already_paid"
        else:
            reg_fee_value = registration_fee

        total_payment = tuition_fee

        if reg_fee_value == "yes":
            total_payment += registration_amount
        else:
            registration_amount = 0

        total_payment -= discount_fee

        if total_payment < 0:
            total_payment = 0

        cur.execute("""
            INSERT INTO tbl_payment (
                id_student,
                id_admin,
                term,
                year,
                registration_fee,
                registration_amount,
                discount_type,
                discount_fee,
                payment_method,
                payment_date,
                tuition_fee,
                total_payment
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            id_student,
            session['id_admin'],
            term_str,
            year,
            reg_fee_value,
            registration_amount,
            discount_type,
            discount_fee,
            payment_method,
            payment_date,
            tuition_fee,
            total_payment
        ))

        mysql.connection.commit()
        cur.close()

        flash("Payment successfully added", "success")
        return redirect(url_for("payment"))

    # GET
    cur.execute("""
        SELECT id_student, name
        FROM tbl_student
        WHERE id_admin=%s
        AND (is_trial IS NULL OR is_trial = 0)
        ORDER BY name ASC
    """, (session['id_admin'],))

    students = cur.fetchall()
    cur.close()

    return render_template(
        'admin/payment/add_payment.html',
        data_student=students
    )


# =========================
# EDIT PAYMENT PAGE
# =========================
def model_edit_payment(id):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            p.id_payment,
            p.id_student,
            s.name,
            p.term,
            p.year,
            p.registration_fee,
            p.discount_type,
            p.discount_fee,
            p.payment_method,
            p.payment_date,
            p.tuition_fee,
            p.registration_amount
        FROM tbl_payment p
        JOIN tbl_student s ON p.id_student = s.id_student
        WHERE p.id_payment=%s AND p.id_admin=%s
    """, (id, session['id_admin']))

    data = cur.fetchone()

    cur.execute("""
        SELECT id_student, name
        FROM tbl_student
        WHERE id_admin=%s
        ORDER BY name ASC
    """, (session['id_admin'],))

    students = cur.fetchall()
    cur.close()

    registration_paid = check_registration_paid(data[1], data[0])

    return render_template(
        'admin/payment/edit_payment.html',
        data_payment=data,
        data_student=students,
        registration_paid=registration_paid
    )

# =========================
# PROCESS EDIT PAYMENT
# =========================
def model_process_edit_payment():
    id_payment = request.form['form_id_payment']
    id_student = request.form['form_id_student']

    terms = request.form.getlist('form_term')
    term = ",".join(terms)
    year = request.form['form_year']

    registration_fee = request.form['form_registration_fee']
    discount_type = request.form['form_discount_type']

    tuition_fee = clean_rupiah(request.form['form_tuition_fee'])
    discount_fee = clean_rupiah(request.form['form_discount_fee'])
    registration_amount = clean_rupiah(request.form.get('form_registration_amount'))

    payment_method = request.form['form_payment_method']
    payment_date = request.form['form_payment_date']

    total_payment = tuition_fee

    if registration_fee == "yes":
        total_payment += registration_amount
    else:
        registration_amount = 0

    total_payment -= discount_fee

    if total_payment < 0:
        total_payment = 0

    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE tbl_payment
        SET
            id_student=%s,
            term=%s,
            year=%s,
            registration_fee=%s,
            discount_type=%s,
            discount_fee=%s,
            payment_method=%s,
            payment_date=%s,
            tuition_fee=%s,
            total_payment=%s,
            registration_amount=%s
        WHERE id_payment=%s AND id_admin=%s
    """, (
        id_student,
        term,
        year,
        registration_fee,
        discount_type,
        discount_fee,
        payment_method,
        payment_date,
        tuition_fee,
        total_payment,
        registration_amount,
        id_payment,
        session['id_admin']
    ))

    mysql.connection.commit()
    cur.close()

    flash("Payment successfully updated", "success")
    return redirect(url_for("payment"))


# =========================
# DELETE PAYMENT
# =========================
def model_delete_payment(id):
    cur = mysql.connection.cursor()

    cur.execute("""
        DELETE FROM tbl_payment
        WHERE id_payment=%s AND id_admin=%s
    """, (id, session.get('id_admin')))

    mysql.connection.commit()
    cur.close()

    flash("Payment successfully deleted", "success")
    return redirect(url_for("payment"))


# =========================
# HELPER FUNCTION
# =========================
def check_registration_paid(id_student, exclude_id=None):
    cur = mysql.connection.cursor()

    if exclude_id:
        cur.execute("""
            SELECT COUNT(*)
            FROM tbl_payment
            WHERE id_student=%s
            AND id_payment!=%s
            AND registration_fee IN ('yes','free')
        """, (id_student, exclude_id))
    else:
        cur.execute("""
            SELECT COUNT(*)
            FROM tbl_payment
            WHERE id_student=%s
            AND registration_fee IN ('yes','free')
        """, (id_student,))

    result = cur.fetchone()
    cur.close()

    return result[0] > 0


from flask import jsonify

def check_registration_status():
    id_student = request.args.get("id_student")

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM tbl_payment
        WHERE id_student=%s
        AND registration_fee IN ('yes','free')
    """, (id_student,))

    result = cur.fetchone()[0] > 0
    cur.close()

    return jsonify({"already_paid": result})