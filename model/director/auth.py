from flask import Flask, render_template, redirect, url_for, request, flash, session
from db import mysql

# SIGNUP
def model_director_signup():
  cur = mysql.connection.cursor()

  if request.method == "POST":
    name = request.form['form_name']
    username = request.form['form_username']
    password = request.form['form_password']
    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM tbl_director WHERE username = %s", (username, ))
    account = cur.fetchone()

    if account is None:
      cur.execute("INSERT INTO tbl_director VALUES (%s, %s, %s, %s)", ('', username, password, name))
      mysql.connection.commit()
      flash("Sign Up Successful", "success")
      return redirect(url_for('director_login'))
    else:
      flash("Username already exists", "danger")
      return redirect(url_for("director_signup"))

  return render_template('director/signup.html')


# LOGIN
def model_director_login():
  if request.method == "POST":
    username = request.form['form_username']
    password = request.form['form_password']

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM tbl_director WHERE username = %s", (username, ))

    account = cur.fetchone()

    if account is None:
      flash("Please check your username", "danger")
    elif password != account[2]:
      flash("Please check your password", "danger")
    else:
      session['director_loggedin'] = True
      session['director_name'] = account[3]
      session['id_director'] = account[0]
      return redirect(url_for("director_dashboard"))

  return render_template("director/login.html")


# LOGOUT
def model_director_logout():
  session.pop('director_loggedin', None)
  session.pop('director_name', None)
  return redirect(url_for('director_login'))