from flask import Flask, render_template, redirect, url_for, request, flash, session
from db import mysql

# SIGNUP
def model_signup():
    cur = mysql.connection.cursor()

    # Always load branches for dropdown
    cur.execute("SELECT id_branch, branch_name FROM tbl_branch")
    branches = cur.fetchall()

    if request.method == 'POST':
        name = request.form['form_name']
        username = request.form['form_username']
        password = request.form['form_password']
        id_branch = request.form['form_id_branch']

        cur = mysql.connection.cursor()

        # 1. Check if username already exists
        cur.execute("SELECT 1 FROM tbl_admin WHERE username = %s", (username,))
        if cur.fetchone():
            flash("Username already exists", "danger")
            return redirect(url_for("signup"))

        # 2. ✅ Check if branch already has an admin
        cur.execute("SELECT 1 FROM tbl_admin WHERE id_branch = %s", (id_branch,))
        if cur.fetchone():
            flash("This branch already has an admin account", "danger")
            return redirect(url_for("signup"))

        # 3. Get id_director from selected branch
        cur.execute("SELECT id_director FROM tbl_branch WHERE id_branch = %s", (id_branch,))
        result = cur.fetchone()

        if result is None:
            flash("Selected branch does not exist", "danger")
            return redirect(url_for("signup"))

        id_director = result[0]

        # 4. Insert new admin
        try:
            cur.execute(
                "INSERT INTO tbl_admin (username, password, name, id_branch, id_director) VALUES (%s, %s, %s, %s, %s)",
                (username, password, name, id_branch, id_director)
            )
            mysql.connection.commit()

            flash("Sign Up Successful", "success")
            return redirect(url_for("login"))

        except Exception as e:
            mysql.connection.rollback()
            flash("Something went wrong during signup", "danger")
            print(e)
            return redirect(url_for("signup"))

    return render_template('admin/signup.html', data_branch=branches)


# LOGIN
def model_login():
    if request.method == 'POST':
        username = request.form['form_username']
        password = request.form['form_password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM tbl_admin WHERE username = %s", (username,))
        account = cur.fetchone()

        if account is None:
            flash("Please check your username", 'danger')
        elif password != account[2]:
            flash("Please check your password", 'danger')
        else:
            # get branch name
            cur.execute("SELECT branch_name FROM tbl_branch WHERE id_branch=%s", (account[4], ))
            branch = cur.fetchone()

            session['loggedin'] = True
            session['name'] = account[3]
            session['id_admin'] = account[0]
            session['id_branch'] = account[4]
            session['id_director'] = account[5]
            session['branch_name'] = branch[0] if branch else ""
            return redirect(url_for("dashboard"))

    return render_template('admin/login.html')


# LOGOUT
def model_logout():
    session.pop('loggedin', None)
    session.pop('name', None)
    session.pop('id_admin', None)
    session.pop('id_branch', None)
    session.pop('id_director', None)
    return redirect(url_for('login'))