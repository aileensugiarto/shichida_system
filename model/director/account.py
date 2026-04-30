from flask import render_template, redirect, url_for, request, flash, session
from db import mysql

# EDIT ACCOUNT
def model_edit_director_account():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM tbl_director WHERE id_director=%s", (session['id_director'], ))
    data = cur.fetchone()
    cur.close()
    return render_template('director/account/edit_account.html', data_director=data)

# PROCESS EDIT ACCOUNT
def model_process_edit_director_account():
    name = request.form['form_name']
    username = request.form['form_username']
    password = request.form['form_password']

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE tbl_director SET username=%s, password=%s, name=%s WHERE id_director=%s",
        (username, password, name, session['id_director'])
    )
    mysql.connection.commit()
    cur.close()

    # ✅ UPDATE SESSION HERE
    session['director_name'] = name
    session['username'] = username
    session['password'] = password

    # flash("Account successfully updated", "success")
    return redirect(url_for("director_dashboard"))