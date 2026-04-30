from flask import Flask, render_template, redirect, url_for, request, flash, session
import os
from db import mysql

# ADMINS
def model_admin():
  cur = mysql.connection.cursor()
  cur.execute("""
            SELECT
              a.id_admin,
              a.username,
              a.password,
              a.name,
              b.branch_name
            FROM tbl_admin a JOIN tbl_branch b
            ON a.id_branch = b.id_branch
            WHERE a.id_director = %s
          """, (session['id_director'], ))
  admins = cur.fetchall()
  cur.close()
  return render_template('director/admin/admin.html', data_admin=admins)


# ADD ADMIN
def model_add_admin():
  cur = mysql.connection.cursor()
  cur.execute("SELECT id_branch, branch_name FROM tbl_branch WHERE id_director=%s", (session['id_director'], ))
  branches = cur.fetchall()

  if request.method == 'POST':
    name = request.form['form_name']
    username = request.form['form_username']
    password = request.form['form_password']
    id_branch = request.form['form_id_branch']

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO tbl_admin (username, password, name, id_branch, id_director) VALUES (%s, %s, %s, %s, %s)",
                (username, password, name, id_branch, session['id_director'], ))
    mysql.connection.commit()
    cur.close()

    flash("Admin successfully added", "success")
    return redirect(url_for('admin'))

  return render_template('director/admin/add_admin.html', data_branch=branches)


# EDIT ADMIN
def model_edit_admin(id):
  cur = mysql.connection.cursor()
  cur.execute("SELECT id_admin, username, password, name, id_branch FROM tbl_admin WHERE id_admin=%s AND id_director=%s", (id, session['id_director'], ))
  data = cur.fetchone()

  cur.execute("SELECT id_branch, branch_name FROM tbl_branch WHERE id_director=%s", (session['id_director'], ))
  branches = cur.fetchall()

  cur.close()

  return render_template('director/admin/edit_admin.html', data_admin=data, data_branch=branches)

# PROCESS EDIT ADMIN
def model_process_edit_admin():
  id_admin = request.form['form_id_admin']
  name = request.form['form_name']
  username = request.form['form_username']
  password = request.form['form_password']
  id_branch = request.form['form_id_branch']

  cur = mysql.connection.cursor()
  cur.execute("UPDATE tbl_admin SET username=%s, password=%s, name=%s, id_branch=%s WHERE id_admin=%s AND id_director=%s",
              (username, password, name, id_branch, id_admin, session['id_director'], ))
  mysql.connection.commit()
  cur.close()

  flash("Admin successfully updated", "success")
  return redirect(url_for("admin"))


# DELETE ADMIN
def model_delete_admin(id):
  cur = mysql.connection.cursor()
  cur.execute("DELETE FROM tbl_admin WHERE id_admin=%s AND id_director=%s", (id, session['id_director'], ))
  mysql.connection.commit()
  cur.close()

  flash("Admin successfully deleted", "success")
  return redirect(url_for("admin"))

