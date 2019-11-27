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

# Get current followers and pending followers data, send it to home.html
@app.route("/home")
@login_required
def home(followMsg=False, errorMsg=False):
    with connection.cursor() as cursor:
        # get pending followers
        query = "SELECT * FROM follow WHERE username_followed = %s AND followStatus = 0"
        cursor.execute(query, (session["username"]))
        pendingFollowRequests = cursor.fetchall()
        # get current followers
        query = "SELECT * FROM follow WHERE (username_follower = %s OR username_followed = %s) AND followStatus = 1"
        cursor.execute(query, (session["username"], session["username"]))
        currentFollowers = cursor.fetchall()
    return render_template("home.html", username=session["username"], currentFollowers=currentFollowers, pendingFollowRequests=pendingFollowRequests, followMsg=followMsg, errorMsg=errorMsg)

# this route is invoked when the request follow form is filled out and sent
# We must check if the username exists first
# Then we check if a request has already been sent, if a request exists, let the user know
# if no request has been sent to this user yet, then send it 
@app.route("/requestFollow", methods=["POST"])
@login_required
def requestFollow():
    if request.form:
        username = request.form.get("username")
        with connection.cursor() as cursor:
            # check if user exists
            query = "SELECT * FROM person WHERE username = %s"
            cursor.execute(query, (username))
        data = cursor.fetchone()
        if data:
            with connection.cursor() as cursor:
                # check if request has been sent before
                query = "SELECT * FROM follow WHERE (username_follower = %s AND username_followed = %s) OR (username_followed = %s AND username_follower = %s)"
                cursor.execute(query, (username, session["username"], username, session["username"]))
            data = cursor.fetchone()
            if not data:
                with connection.cursor() as cursor:
                    # send request
                    query = "INSERT INTO follow (username_followed, username_follower, followstatus) VALUES (%s, %s, %s)"
                    cursor.execute(query, (username, session["username"], 0))
                followMsg = "Follow request sent"
                return home(followMsg=followMsg)
            else:
                # let the user know he/she has already sent a request
                error = "Request to %s already sent" % (username)
                return home(followMsg=error)
        else:
            # let the user know the user does not exists
            followMsg = "Username does not exist"
            return home(followMsg=followMsg)

    error = "An unknown error has occurred. Please try again."
    return home(errorMsg=error)

# update the follow table with the follow status 1
# this route is invoked when a user clicks the accept button on the pending follow
@app.route("/acceptFollow/<usernameFollower>", methods=["POST"])
@login_required
def acceptFollow(usernameFollower):
    with connection.cursor() as cursor:
        query = "UPDATE follow SET followstatus = 1 WHERE username_follower = %s AND username_followed = %s"
        cursor.execute(query, (usernameFollower, session["username"]))
    return redirect(url_for("home"))

# this route is invoked when a user clicks the decline button on the pending follow
# serves as a decline follow but also as an unfollow, as it deletes the table entry in its entirety
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

# gets images visible to the user.
@app.route("/images", methods=["GET"])
@login_required
def images():
    query = ("SELECT * "
            "FROM photo AS p1 "
            "WHERE photoPoster = %s "
            "OR ( "
                "p1.allFollowers = 1 "
                "AND EXISTS ( "
                            "SELECT * "
                            "FROM follow "
                            "WHERE follow.username_followed = p1.photoPoster "
                            "AND follow.username_follower = %s "
                            "AND followstatus = 1) "
                "OR EXISTS ( "
                            "SELECT * "
                            "FROM follow "
                            "WHERE follow.username_follower = p1.photoPoster "
                            "AND follow.username_followed = %s "
                            "AND followstatus = 1) "
                ") "
            "OR EXISTS ( "
                        "SELECT * "
                        "FROM sharedWith as s1 "
                        "WHERE photoID = p1.photoID "
                        "AND (groupOwner, groupName) IN ( "
                                                        "SELECT groupOwner, groupName "
                                                        "FROM belongTo "
                                                        "WHERE member_username = %s "
                                                        ") "
                        ") "
            )
    with connection.cursor() as cursor:
        cursor.execute(query, (session["username"], session["username"], session["username"], session["username"]))
        images = cursor.fetchall()
        query = "SELECT * FROM tagged WHERE username = %s AND tagstatus = 0"
        cursor.execute(query, (session["username"]))
        pendingTags = cursor.fetchall()
    return render_template("images.html", images=images, pendingTags=pendingTags)

@app.route("/image/<image_name>", methods=["GET"])
@login_required
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/more-info/<username>/<photoID>", methods=["GET"])
@login_required
def moreInfo(username, photoID, tagMsg=False):
    moreInfoData = {
        "firstName": "",
        "lastName": "",
        "tagged": [],
        "likes": []
    }
    print(photoID)
    with connection.cursor() as cursor:
        query = "SELECT * FROM person WHERE username = %s"
        cursor.execute(query, (username))
        data = cursor.fetchone()
        moreInfoData["firstName"] = data["firstName"]
        moreInfoData["lastName"] = data["lastName"]

        query = "SELECT username, firstName, lastName FROM tagged NATURAL JOIN person WHERE photoID = %s AND tagstatus = 1"
        cursor.execute(query, (photoID))
        moreInfoData["tagged"] = cursor.fetchall()

        query = "SELECT username, rating FROM likes WHERE photoID = %s"
        cursor.execute(query, (photoID))
        moreInfoData["likes"] = cursor.fetchall()

        query = "SELECT * FROM photo WHERE photoID = %s"
        cursor.execute(query, (photoID))
        imageInQuestion = cursor.fetchone()
    print(moreInfoData)
    return render_template("more-info.html", moreInfoData=moreInfoData, image=imageInQuestion, tagMsg=tagMsg)
        
@app.route("/tag", methods=["POST"])
def tag():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        photoID = requestData["photoID"]
        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s"
            cursor.execute(query, (username))
            data = cursor.fetchone()
            if not data:
                tagMsg = "User does not exist"
                return moreInfo(username, photoID, tagMsg=tagMsg)
            if username == session["username"]:
                try:
                    query = "INSERT INTO tagged (username, photoID, tagstatus) VALUES (%s, %s, %s)"
                    cursor.execute(query, (username, photoID, 1))
                    tagMsg = "Tag set"
                    return moreInfo(username, photoID, tagMsg=tagMsg)
                except pymysql.err.IntegrityError:
                    error = "%s is already tagged." % (username)
                    return moreInfo(username, photoID, tagMsg=error)
            else:
                query = ("SELECT * "
                        "FROM photo AS p1 "
                        "WHERE photoID = %s "
                        "AND ( EXISTS ( "
                                        "SELECT * "
                                        "FROM follow "
                                        "WHERE follow.username_followed = p1.photoPoster "
                                        "AND follow.username_follower = %s "
                                        "AND followstatus = 1) "
                                "OR EXISTS ( "
                                            "SELECT * "
                                            "FROM follow "
                                            "WHERE follow.username_follower = p1.photoPoster "
                                            "AND follow.username_followed = %s "
                                            "AND followstatus = 1) "
                            ")"
                        "OR EXISTS ( "
                                    "SELECT * "
                                    "FROM sharedWith as s1 "
                                    "WHERE photoID = p1.photoID "
                                    "AND (groupOwner, groupName) IN ( "
                                                                    "SELECT groupOwner, groupName "
                                                                    "FROM belongTo "
                                                                    "WHERE member_username = %s "
                                                                    ") "
                                    ") "
                        )
                cursor.execute(query, (photoID, username, username, username))
                data = cursor.fetchone()
                if data:
                    query = "INSERT INTO tagged (username, photoID, tagstatus) VALUES (%s, %s, %s)"
                    cursor.execute(query, (username, photoID, 0))
                    tagMsg = "Tag pending approval"
                    return moreInfo(username, photoID, tagMsg=tagMsg)
                else:
                    tagMsg = "Photo not visible to Taggee"
                    return moreInfo(username, photoID, tagMsg=tagMsg)

@app.route("/acceptTag/<photoID>", methods=["POST"])
def acceptTag(photoID):
    with connection.cursor() as cursor:
        query = "UPDATE tagged SET tagstatus = 1 WHERE username = %s AND photoID = %s"
        cursor.execute(query, (session["username"], photoID))
    return images()

# serves as a decline follow but also as an unfollow, as it deletes the table entry in its entirety
@app.route("/declineTag/<photoID>", methods=["POST"])
@login_required
def declineTag(photoID):
    with connection.cursor() as cursor:
        query = "DELETE FROM tagged WHERE (username = %s AND photoID = %s)"
        cursor.execute(query, (session["username"], photoID))
    return images()

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