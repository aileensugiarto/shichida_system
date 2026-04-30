from flask import render_template, redirect, url_for, request, flash, session
from db import mysql

# EDIT ACCOUNT
def model_edit_account():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM tbl_admin WHERE id_admin=%s", (session['id_admin'], ))
    data = cur.fetchone()
    cur.close()
    return render_template('admin/account/edit_account.html', data_admin=data)

# PROCESS EDIT ACCOUNT
def model_process_edit_account():
    name = request.form['form_name']
    username = request.form['form_username']
    password = request.form['form_password']

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE tbl_admin SET username=%s, password=%s, name=%s WHERE id_admin=%s",
        (username, password, name, session['id_admin'])
    )
    mysql.connection.commit()
    cur.close()

    # ✅ UPDATE SESSION HERE
    session['name'] = name
    session['username'] = username
    session['password'] = password

    # flash("Account successfully updated", "success")
    return redirect(url_for("dashboard"))