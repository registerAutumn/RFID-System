#!/usr/bin/env python
#-*- encoding: utf-8

from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
from flask.ext.basicauth import BasicAuth
import sqlite3
import time
import json
import os
import re

host = Flask(__name__)
host.config["SECRET_KEY"] = os.urandom(10)
host.config["BASIC_AUTH_USERNAME"] = "admin"
host.config["BASIC_AUTH_PASSWORD"] = "password"
sock = SocketIO(host)
auth = BasicAuth(host)
os.environ["tz"] = "Asia/Taipei"

@host.route("/")
@host.route("/<int:serial_code>")
def main(serial_code=None):
    if serial_code == None:
        data = do_sql("select serial_id, title, unit, descript from Activity", ())
        ret = []
        for d in data:
            (serial_id, title, unit, descript) = d
            ret.append({"id": serial_id, "title": title, "unit": unit, "descript": descript})
        return render_template("show.html", act=ret)
    else:
        (title, unit, descript) = do_sql("select title, unit, descript from Activity where serial_id=?", (serial_code,))[0]
        ret = {
            "title": title,
            "unit": unit,
            "descript": descript,
            "attend_list": []
        }
        attend_list = do_sql("select student_id, is_check, check_time from Attend_List where serial_id=? order by student_id", (serial_code,))
        for student in attend_list:
            (student_id, is_check, check_time) = student
            (name, unit) = do_sql("select name, unit from Member where student_id=? limit 1", (student_id,))[0]
            ret["attend_list"].append({"student_id": student_id, "name": name, "unit": unit, "status": is_check, "time": check_time})
        return render_template("activity.html", details=ret)

@host.route("/admin")
@host.route("/admin/<option>")
@auth.required
def admin(option=None):
    page = option + ".html" if option != None else "home.html"
    ret = []
    print option
    if option == "users":
        result = do_sql("select student_id, name, unit from Member order by student_id", ())
        for data in result:
            (student_id, name, unit) = data
            ret.append({"student_id": student_id, "name": name, "unit": unit})
        print "users"
    elif option == "event":
        events = do_sql("select serial_id, title, unit from Activity", ())
        for event in events:
            (serial_id, title, unit) = event
            temp = {
                "serial_id": serial_id,
                "title": title,
                "unit": unit,
                "attend_list": []
            }
            attend_list = do_sql("select student_id, is_check from Attend_List where serial_id=?", (serial_id, ))
            for member in attend_list:
                (student_id, is_check) = member
                (name, unit) = do_sql("select name, unit from Member where student_id=? limit 1", (student_id, ))[0]
                temp["attend_list"].append({"student_id": student_id, "name": name, "unit": unit, "is_check": is_check})
            ret.append(temp)
    else:
        pass
    return render_template("admin/" + page, details=ret)

@host.route("/admin/event/new", methods=["POST", "GET"])
@auth.required
def new_event():
    if request.method == "POST":
        print request.form
        print request.form.getlist("member")
    ret = []
    result = do_sql("select student_id, name, unit from Member order by student_id", ())
    for data in result:
        (student_id, name, unit) = data
        ret.append({"student_id": student_id, "name": name, "unit": unit})
    return render_template("admin/event_new.html", member=ret)

@host.route("/api/get_list", methods=["GET"])
def get_list():
    if request.method == "GET":
        result = do_sql("select serial_id, title from Activity order by serial_id", ())
        ret = []
        for data in result:
            (sid, title) = data
            ret.append({"id": sid, "name": title})
        return json.dumps(ret)
    else:
        "", 500

@host.route("/api/check_in", methods=["POST"])
def check_in():
    if not ("timeout" in session and session["timeout"] >= time.time()):
        print "Error"
        return "", 500
    if request.method == "POST":
        card_id = request.form["card_id"]
        serial_id = request.form["serial_id"]
        print card_id, serial_id
        try:
            (student_id, ) = do_sql("select student_id from Member where card_id=? limit 1", (card_id, ))[0]
            print student_id
            (is_check, ) = do_sql("select is_check from Attend_List where student_id=? and serial_id=?", (student_id, serial_id, ))[0]
            if is_check == 1:
                sock.emit("check_in", {"success": "true",  "id": student_id, "msg": "已經簽到了"}, boradcast=True)
            else:
                do_sql("update Attend_List set is_check=1, check_time=? where student_id=?", (time.strftime("%Y-%m-%d %H:%M:%S"), student_id, ))
                sock.emit("check_in", {"success": "true",  "id": student_id, "msg": "簽到完成", "time": time.strftime("%Y-%m-%d %H:%M:%S")}, boradcast=True)
            session["timeout"] = time.time() + 3600
            return "True"
        except Exception, e:
            sock.emit("check_in", {"success": "false",  "id": "", "msg": "Error"}, boradcast=True)
            return "False"
    else:
        return "", 500

@host.route("/api/token", methods=["POST"])
def get_token():
    if request.method == "POST":
        try:
            username = request.form["username"]
            password = request.form["password"]
            if username == "admin" and password == "KUASITC":
                session["timeout"] = time.time() + 3600
                return "OK"
            else:
                return ""
        except Exception, e:
            raise e
            return "", 500
    else:
        return "", 500

def do_sql(sql_content, args):
    database = sqlite3.connect("activity")
    cursor = database.cursor()
    cursor.execute(sql_content, args)
    result = cursor.fetchall()
    if re.match(r"^select.+", sql_content.lower()) == None:
        database.commit()
    return result

if __name__ == '__main__':
    sock.run(host, host="0.0.0.0", port=8080, debug=True)