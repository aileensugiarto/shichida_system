from flask import render_template, request, redirect, url_for, flash, session
from db import mysql
from datetime import datetime

# PAYMENT
def model_director_payment():
    cur = mysql.connection.cursor()

    # 1️⃣ Get payment data (current year only)
    cur.execute("""
        SELECT
            s.name AS student_name,
            p.term,
            p.year,
            p.registration_fee,
            p.discount_type,
            p.discount_fee,
            p.payment_method,
            p.payment_date,
            p.tuition_fee,
            p.total_payment,
            p.registration_amount,
            b.branch_name
        FROM tbl_payment p
        JOIN tbl_student s ON p.id_student = s.id_student
        JOIN tbl_admin a ON p.id_admin = a.id_admin
        JOIN tbl_branch b ON a.id_branch = b.id_branch
        WHERE 
            a.id_director = %s
            AND p.year = YEAR(CURDATE())
        ORDER BY 
            b.branch_name ASC,
            p.term ASC
    """, (session['id_director'],))

    data_payment = cur.fetchall()

    # 2️⃣ Get branches ONLY from tbl_branch
    cur.execute("""
        SELECT branch_name 
        FROM tbl_branch
        WHERE id_director = %s
    """, (session['id_director'],))

    branches = cur.fetchall()

    cur.close()

    return render_template(
        'director/payment/payment.html',
        data_payment=data_payment,
        branches=branches
    )
