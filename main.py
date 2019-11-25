from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
from os import path, walk
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")
SALT = "cs3083"

connection = pymysql.connect(host="127.0.0.1",
                             user="root",
                             password="Mach-3F-35C",
                             db="finstagram",
                             charset="utf8mb4",
                             port=3306,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home(followMsg=False, errorMsg=False):
    with connection.cursor() as cursor:
        query = "SELECT * FROM follow WHERE username_followed = %s AND followStatus = 0"
        cursor.execute(query, (session["username"]))
        pendingFollowRequests = cursor.fetchall()
        query = "SELECT * FROM follow WHERE (username_follower = %s OR username_followed = %s) AND followStatus = 1"
        cursor.execute(query, (session["username"], session["username"]))
        currentFollowers = cursor.fetchall()
    return render_template("home.html", username=session["username"], currentFollowers=currentFollowers, pendingFollowRequests=pendingFollowRequests, followMsg=followMsg, errorMsg=errorMsg)

@app.route("/requestFollow", methods=["POST"])
@login_required
def requestFollow():
    if request.form:
        username = request.form.get("username")
        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s"
            cursor.execute(query, (username))
        data = cursor.fetchone()
        if data:
            with connection.cursor() as cursor:
                query = "SELECT * FROM follow WHERE (username_follower = %s AND username_followed = %s) OR (username_followed = %s AND username_follower = %s)"
                cursor.execute(query, (username, session["username"], username, session["username"]))
            data = cursor.fetchone()
            if not data:
                with connection.cursor() as cursor:
                    query = "INSERT INTO follow (username_followed, username_follower, followstatus) VALUES (%s, %s, %s)"
                    cursor.execute(query, (username, session["username"], 0))
                followMsg = "Follow request sent"
                return home(followMsg=followMsg)
            else:
                error = "Request to %s already sent" % (username)
                return home(followMsg=error)
        else:
            followMsg = "Username does not exist"
            return home(followMsg=followMsg)

    error = "An unknown error has occurred. Please try again."
    return home(errorMsg=error)

@app.route("/acceptFollow/<usernameFollower>", methods=["POST"])
@login_required
def acceptFollow(usernameFollower):
    with connection.cursor() as cursor:
        query = "UPDATE follow SET followstatus = 1 WHERE username_follower = %s AND username_followed = %s"
        cursor.execute(query, (usernameFollower, session["username"]))
    return redirect(url_for("home"))

@app.route("/declineFollow/<usernameFollower>", methods=["POST"])
@login_required
def declineFollow(usernameFollower):
    with connection.cursor() as cursor:
        query = "DELETE FROM follow WHERE (username_follower = %s AND username_followed = %s) OR (username_followed = %s AND username_follower = %s)"
        cursor.execute(query, (usernameFollower, session["username"], usernameFollower, session["username"]))
    return redirect(url_for("home"))

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")

@app.route("/images", methods=["GET"])
@login_required
def images():
    query = "SELECT * FROM photo"
    with connection.cursor() as cursor:
        cursor.execute(query)
    data = cursor.fetchall()
    return render_template("images.html", images=data)

@app.route("/image/<image_name>", methods=["GET"])
@login_required
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/more-info/<username>/<photoID>", methods=["GET"])
@login_required
def moreInfo(username, photoID):
    moreInfoData = {
        "firstName": "",
        "lastName": "",
        "timeStamp": "",
        "tagged": [],
        "likes": []
    }
    photoID = int(photoID)
    with connection.cursor() as cursor:
        query = "SELECT * FROM person WHERE username = %s"
        cursor.execute(query, (username))
        data = cursor.fetchone()
        moreInfoData["firstName"] = data["firstName"]
        moreInfoData["lastName"] = data["lastName"]

        query = "SELECT username, firstName, LastName FROM tagged NATURAL JOIN person WHERE photoID = %s AND tagstatus = 1"
        cursor.execute(query, (photoID))
        data = cursor.fetchall()
        moreInfoData["tagged"] = data

        query = "SELECT username, rating FROM likes WHERE photoID = %s"
        cursor.execute(query, (photoID))
        data = cursor.fetchall()
        moreInfoData["liked"] = data

        query = "SELECT * FROM photo WHERE photoID = %s"
        cursor.execute(query, (photoID))
    imageInQuestion = cursor.fetchone()
    return render_template("more-info.html", moreInfoData=moreInfoData, image=imageInQuestion)
        

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"] + SALT
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"] + SALT
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, firstName, lastName) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)    

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    if request.files:
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        allFollowers = 0
        if request.form.get("allFollowers"):
            allFollowers = 1
        caption = request.form.get("caption")
        query = "INSERT INTO photo (photoID, postingdate, filepath, allFollowers, caption, photoPoster) VALUES (%s, %s, %s, %s, %s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (0, time.strftime('%Y-%m-%d %H:%M:%S'), image_name, allFollowers, caption, session["username"]))
        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message)
    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run(debug=True)