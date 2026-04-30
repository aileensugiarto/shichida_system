from flask import Flask, render_template, redirect, url_for, request, flash, session
import os
from db import mysql

# BRANCH
def model_branch():
  cur = mysql.connection.cursor()
  cur.execute("""
        SELECT
            b.id_branch,
            b.branch_name,
            COUNT(DISTINCT s.id_student) AS total_students,
            COUNT(DISTINCT t.id_teacher) AS total_teachers
        FROM tbl_branch b
        LEFT JOIN tbl_admin a ON a.id_branch = b.id_branch
        LEFT JOIN tbl_student s ON s.id_admin = a.id_admin
        LEFT JOIN tbl_teacher t ON t.id_admin = a.id_admin
        WHERE b.id_director = %s
        GROUP BY b.id_branch, b.branch_name
        ORDER BY b.id_branch
      """, (session['id_director'], ))
  branches = cur.fetchall()
  cur.close()
  return render_template('director/branch/branch.html', data_branch=branches,)

# ADD BRANCH
def model_add_branch():
  if request.method == 'POST':
    branch_name = request.form['form_branch_name']

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO tbl_branch VALUES (%s, %s, %s)", ('', branch_name, session['id_director'], ))
    mysql.connection.commit()
    cur.close()

    flash("Branch successfully added", "success")
    return redirect(url_for("branch"))

  return render_template('director/branch/add_branch.html')

# EDIT BRANCH
def model_edit_branch(id):
  cur = mysql.connection.cursor()
  cur.execute("SELECT * FROM tbl_branch WHERE id_branch = %s AND id_director = %s", (id, session['id_director'], ))
  data = cur.fetchone()
  cur.close()
  return render_template('director/branch/edit_branch.html', data_branch=data)

# PROCESS EDIT BRANCH
def model_process_edit_branch():
  id_branch = request.form['form_id_branch']
  branch_name = request.form['form_branch_name']
  cur = mysql.connection.cursor()
  cur.execute("UPDATE tbl_branch SET branch_name=%s WHERE id_branch=%s AND id_director=%s", (branch_name, id_branch, session['id_director'], ))
  mysql.connection.commit()
  cur.close()

  flash("Branch successfully updated", "success")
  return redirect(url_for("branch"))

# DELETE BRANCH
def model_delete_branch(id):
  cur = mysql.connection.cursor()
  cur.execute("DELETE FROM tbl_branch WHERE id_branch = %s AND id_director = %s", (id, session['id_director'], ))
  mysql.connection.commit()
  cur.close()
  flash("Branch successfully deleted", "success")
  return redirect(url_for("branch"))