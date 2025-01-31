import tempfile
import os
import json
from datetime import timedelta
import time 
import random

from flask import Flask, render_template, redirect, request, session, url_for
from authlib.integrations.flask_client import OAuth

from generator import *


app = Flask(__name__)

session_options = {"secret_key": os.urandom(24).hex(), "lifetime": 30}
session_options_path = "session.json"
if not os.path.exists(session_options_path):
	with open(session_options_path, "w", encoding="utf-8") as session_options_file:
		json.dump(session_options, session_options_file, indent=4)
else:
	with open(session_options_path, "r", encoding="utf-8") as session_options_file:
		for key, value in json.load(session_options_file).items():
			session_options[key] = value
app.secret_key = bytes.fromhex(session_options["secret_key"])
app.permanent_session_lifetime = timedelta(days=session_options["lifetime"])

database_path = "database"

# oauth_path = "oauth.json"
# oauth_default_client_id = "YOUR_CLIENT_ID"
# oauth_default_client_secret = "YOUR_CLIENT_SECRET"
# if not os.path.exists(oauth_path):
# 	json.dump({
# 		"provider": "google",
# 		"client_id": oauth_default_client_id,
# 		"client_secret": "YOUR_CLIENT_SECRET",
# 		"server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
# 		"client_kwargs": {"scope": "openid email profile"}
# 	}, open(oauth_path, "w", encoding="utf-8"), indent=4)
# oauth = OAuth(app)
# oauth_options = json.load(open(oauth_path, encoding="utf-8"))
# if oauth_options["client_id"] == oauth_default_client_id or oauth_options["client_secret"] == oauth_default_client_secret:
# 	print(f"Enter your OAuth `client_id` and `client_secret` in `{oauth_path}`.")
# 	sys.exit()
# oauth_provider = oauth_options.pop("provider")
# oauth.register(oauth_provider, **oauth_options)


def get_user_id(s) -> str:
	LOCAL_USER_ID = "local"
	if request.remote_addr == "127.0.0.1":
		return LOCAL_USER_ID
	if "user_id" in s:
		user_id = s["user_id"]
		if user_id == LOCAL_USER_ID:
			raise Exception("Attempted login to local user from external address.")
		return s["user_id"]
	else:
		user_id = f"{int(time.time() * 1000)}-{random.randint(1000, 9999)}"
		s["user_id"] = user_id
		return user_id


def get_user_path(user_id, path="") -> str:
	user_path = os.path.join(database_path, user_id)
	os.makedirs(user_path, exist_ok=True)
	if path:
		user_path = os.path.join(user_path, path)
		if os.path.exists(user_path):
			return user_path
		else:
			return None
	else:
		return user_path


def get_user_file(user_id, path="", mode="r", encoding="utf-8"):
	user_path = get_user_path(user_id, path)
	if user_path:
		return open(user_path, mode, encoding=encoding)
	else:
		return None
	

def get_user_jobs(user_id):
	saved_path = get_user_path(user_id, "saved")
	if saved_path:
		jobs = []
		for directory in os.listdir(saved_path):
			title_path = os.path.join(saved_path, directory, "title.md")
			if os.path.exists(title_path):
				jobs.insert(0, open(title_path, encoding="utf-8").read())
		return jobs
	else:
		return None


@app.before_request
def make_session_permanent():
	session.permanent = True


@app.after_request
def add_cors_headers(response):
	response.headers['Access-Control-Allow-Origin'] = '*'
	return response


@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error_message="Page not found"), 404


@app.errorhandler(500)
def internal_server_error(error):
    return render_template('error.html', error_message="Internal server error, please try again later."), 500


@app.route("/")
def index():
	user_id = get_user_id(session)
	if not get_user_path(user_id, "resume.md"):
		return redirect("/welcome")
	if not get_user_jobs(user_id):
		return redirect("/job")
	else:
		return redirect("/dashboard")


@app.route("/welcome")
def welcome():
	return render_template("welcome.html")


@app.route("/dashboard")
def dashboard():
	jobs = get_user_jobs(get_user_id(session))
	if jobs:
		return render_template("dashboard.html", jobs=jobs)
	else:
		return redirect("/")

# @app.route("/login")
# def login():
# 	return render_template("login.html")


@app.route("/resume")
def resume():
	resume_file = get_user_file(get_user_id(session), "resume.md")
	if resume_file:
		resume = resume_file.read()
	else:
		resume = ""
	return render_template("resume.html", resume=resume)


@app.route("/sample")
def sample():
	return render_template("sample.html")


@app.route("/job")
def job():
	return render_template("job.html")


@app.route("/letter")
def letter():
	job = open("job.md", "r", encoding="utf-8").read().replace("\n", "\\n")
	resume = open("resume.md", "r", encoding="utf-8").read().replace("\n", "\\n")
	letter = open("letter.md", "r", encoding="utf-8").read()
	return render_template("letter.html", job=job, resume=resume, letter=letter)


@app.route("/api/resume/upload", methods=["POST"])
def api_resume_upload():

	# Error if no file uploaded
	if "resume" not in request.files:
		return {"error": "No file uploaded"}, 400

	# Get the uploaded file
	upload = request.files["resume"]

	# Error if no file selected
	if upload.filename == "":
		return {"error": "No selected file"}, 400

	# Error if file extension is not supported
	if not upload.filename.endswith(".pdf"):
		return {"error": "Only PDF files are supported"}, 400

	with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as file:

		# Write the uploaded file to a temporary file
		file.write(upload.read())
		file.flush()

		# Get the filename of the temporary file
		filename = file.name

	# Extract the text from the temporary file
	text = parse_pdf(filename)
	# print(text)

	# Save extracted text in session cookie
	session["resume"] = text

	# Delete the temporary file
	os.remove(filename)

	# Success
	return {"message": "Resume uploaded successfully", "text": text}, 200


@app.route("/api/resume/edit", methods=["POST"])
def api_resume_edit():

	# Error if no string is provided
	if not request.json or "resume" not in request.json:
		return {"error": "No resume text provided"}, 400

	# Get the resume text from the request
	text = request.json["resume"]
	# print(text)

	# Save the resume text in session cookie
	session["resume"] = text

	# Success
	return {"message": "Resume updated successfully", "text": text}, 200


@app.route("/api/generate", methods=["POST"])
def api_generate():
	return


if __name__ == "__main__":
	app.run(debug=True)