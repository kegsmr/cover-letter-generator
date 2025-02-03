import tempfile
import os
import json
from datetime import timedelta
import time 
import random
import re

from flask import Flask, render_template, redirect, request, session, url_for, send_from_directory

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

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

database_path = "database"

user_status = {}

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
		user_id = sanitize_directory_name(s["user_id"])
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
	

def read_user_file(user_id, path="", fix_spacing=True, **kwargs):
	file = get_user_file(user_id, path, **kwargs)
	if file:
		data = file.read()
		if fix_spacing:
			data = re.sub(r'\n{3,}', '\n\n', data).strip()
		return data
	else:
		return ""


def write_user_file(data, user_id, path="", mode="w", encoding="utf-8", fix_spacing=True):
	user_path = os.path.join(database_path, user_id)
	if path:
		user_path = os.path.join(user_path, path)
	if fix_spacing:
			data = re.sub(r'\n{3,}', '\n\n', data).strip()
	with open(user_path, mode, encoding=encoding) as user_file:
		user_file.write(data)


def get_user_jobs(user_id):
	saved_path = get_user_path(user_id, "saved")
	if saved_path:
		jobs = []
		for directory in os.listdir(saved_path):
			title_path = os.path.join(saved_path, directory, "title.md")
			if os.path.exists(title_path):
				jobs.insert(0, (directory, open(title_path, encoding="utf-8").read()))
		if len(jobs) > 0:
			return jobs
		else:
			return None
	else:
		return None


def set_user_status(user_id, status="Loading..."):
	user_status[user_id] = status


def get_user_status(user_id):
	return user_status.get(user_id, "Loading...")


@app.before_request
def make_session_permanent():
	session.permanent = True


# @app.after_request
# def add_cors_headers(response):
# 	response.headers['Access-Control-Allow-Origin'] = '*'
# 	return response


@app.errorhandler(404)
def not_found_error(error):
	return render_template('error.html', error_message="Page not found"), 404


@app.errorhandler(500)
def internal_server_error(error):
	return render_template('error.html', error_message="Internal server error, please try again later."), 500


@app.route('/.well-known/acme-challenge/<filename>')
def serve_challenge(filename):
	challenge_directory = os.path.join(os.getcwd(), '.well-known', 'acme-challenge')
	return send_from_directory(challenge_directory, filename)


@app.route("/")
def index():
	user_id = get_user_id(session)
	if not get_user_path(user_id, "resume.md"):
		return redirect("/welcome")
	if not get_user_jobs(user_id):
		return redirect("/job")
	else:
		return redirect("/home")


@app.route("/home")
def home():
	jobs = get_user_jobs(get_user_id(session))
	if jobs:
		return render_template("dashboard.html", jobs=jobs)
	else:
		return render_template("welcome.html")


# @app.route("/welcome")
# def welcome():
# 	return render_template("welcome.html")


# @app.route("/dashboard")
# def dashboard():
# 	jobs = get_user_jobs(get_user_id(session))
# 	if jobs:
# 		return render_template("dashboard.html", jobs=jobs)
# 	else:
# 		return redirect("welcome")

# @app.route("/login")
# def login():
# 	return render_template("login.html")


@app.route("/resume", methods=["GET", "POST"])
def resume():

	user_id = get_user_id(session)
	
	if request.method == "GET":

		set_user_status(user_id)

		# Get the user's resume text (if it exists)
		r = read_user_file(user_id, "resume.md")
		return render_template("resume.html", resume=r)
	
	else:

		# Handling the file upload
		if "resume" in request.files and request.files["resume"].filename != "":

			set_user_status(user_id, "Reading your resume...")

			upload = request.files["resume"]

			# Error if no file selected
			if upload.filename == "":
				return {"error": "No selected file"}, 400

			# Error if file extension is not supported
			if upload.mimetype != "application/pdf":
				return {"error": "Only PDF files are supported"}, 400

			with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as file:
				# Write the uploaded file to a temporary file
				file.write(upload.read())
				file.flush()

				# Get the filename of the temporary file
				filename = file.name

			# Extract the text from the temporary file
			resume = parse_pdf(filename)

			# Save extracted text
			write_user_file(resume, user_id, path="resume.md")

			# Delete the temporary file
			os.remove(filename)

			# After processing the file, render with the resume text
			return render_template("resume.html", resume=resume)
		
		# Handling the textarea content submission
		if "resume_content" in request.form:

			url = request.args.get('redirect')

			resume_content = request.form["resume_content"]

			# Save the resume content (textarea data)
			write_user_file(resume_content, user_id, path="resume.md")

			# Render with the new resume content
			return redirect(url)

		# If neither file nor text content is provided, return an error
		return {"error": "No resume file or content provided"}, 400


@app.route("/sample", methods=["GET", "POST"])
def sample():

	if request.method == "GET":

		s = read_user_file(get_user_id(session), "sample.md")
		return render_template("sample.html", sample=s)

	else:

		if "sample" in request.form:

			url = request.args.get('redirect')

			write_user_file(request.form["sample"], get_user_id(session), "sample.md")

			return redirect(url)
		
		else:

			return {"error": "No sample letter provided."}, 400


@app.route("/job", methods=["GET", "POST"])
def job():

	user_id = get_user_id(session)

	if request.method == "GET":

		set_user_status(user_id)

		job_posting = read_user_file(user_id, "job.md")

		return render_template("job.html", job=job_posting)

	else:

		if "url" in request.form and request.form["url"]:

			url = request.form["url"]

			if not (url.startswith("http://") or url.startswith("https://")):
				url = f"http://{url}"

			try:
				job_posting = get_job_posting(url, callback=lambda message: set_user_status(user_id, message))
			except Exception as e:
				job_posting = f"Unable to fetch job description.\n\nYou can still copy and paste it manually." + f"\n\nERROR:\n{e}" if request.remote_addr == "127.0.0.1" else ""

			write_user_file(job_posting, user_id, "job.md")

			return render_template("job.html", job=job_posting)

		elif "job_content" in request.form:

			url = request.args.get('redirect')

			session["feedback"] = []

			job_posting = request.form["job_content"]

			write_user_file(job_posting, user_id, "job.md")

			return redirect(url)

		else:

			return redirect("/job")


@app.route("/job/new")
def job_new():

	user_id = get_user_id(session)

	write_user_file("", user_id, "title.md")
	write_user_file("", user_id, "job.md")
	write_user_file("", user_id, "letter.md")

	return redirect("/job")


@app.route("/letter", methods=["GET", "POST"])
def letter():

	user_id = get_user_id(session)

	if request.method == "GET":

		title = read_user_file(user_id, "title.md")

		if not title:
			title = "(Job Title)"

		options = {
			"job": read_user_file(user_id, "job.md").replace("\n", "\\n"),
			"resume": read_user_file(user_id, "resume.md").replace("\n", "\\n"),
			"title": title,
			"letter": read_user_file(user_id, "letter.md")
		}
		
		return render_template("letter.html", **options)
	
	else:

		if "letter" in request.form:

			url = request.args.get('redirect')

			letter = request.form["letter"]

			write_user_file(letter, user_id, "letter.md")

			return redirect(url)
		
		else:

			return {"error": "No cover letter provided."}, 400


@app.route("/letter/generate", methods=["GET", "POST"])
def letter_generate():

	user_id = get_user_id(session)
	set_user_status(user_id)

	if request.method == "POST":
		if "feedback" in request.form:
			feedback = request.form["feedback"]
			if feedback:
				session["feedback"].append(feedback)

	resume = read_user_file(user_id, "resume.md")
	job = read_user_file(user_id, "job.md")
	sample = read_user_file(user_id, "sample.md")

	examples = []
	if sample:
		examples += [(resume, "No job description provided.", sample)]
	save_path = os.path.join(database_path, user_id, "saved")
	if os.path.exists(save_path):
		for directory in os.listdir(save_path):
			examples += [load(os.path.join(save_path, directory))]

	# print(examples)
	
	write_user_file(pick_job_title(job), user_id, "title.md")
	write_user_file(generate(examples, resume, job, comments=session["feedback"], callback=lambda message: set_user_status(user_id, message)), user_id, "letter.md")

	return redirect("/letter") #{"success": ""} 


@app.route("/letter/save", methods=["POST"])
def letter_save():

	user_id = get_user_id(session)

	save_path = os.path.join(database_path, user_id, "saved")

	title = read_user_file(user_id, "title.md")
	resume = read_user_file(user_id, "resume.md")
	job = read_user_file(user_id, "job.md")
	letter = request.form["letter"]
	
	save_id = ""
	if "loaded" in session:
		if job == read_user_file(user_id, os.path.join("saved", session["loaded"], "job.md")):
			save_id = session["loaded"]

	write_user_file(letter, user_id, "letter.md")
	save(save_path, resume, job, letter, title=title, save_id=save_id)

	return redirect("/home")


@app.route("/letter/load/<save_id>")
def letter_load(save_id):

	session["loaded"] = save_id

	user_id = get_user_id(session)

	title = read_user_file(user_id, os.path.join("saved", save_id, "title.md"))
	job = read_user_file(user_id, os.path.join("saved", save_id, "job.md"))
	resume = read_user_file(user_id, os.path.join("saved", save_id, "resume.md"))
	letter = read_user_file(user_id, os.path.join("saved", save_id, "letter.md"))
	
	write_user_file(title, user_id, "title.md")
	write_user_file(job, user_id, "job.md")
	write_user_file(resume, user_id, "resume.md")
	write_user_file(letter, user_id, "letter.md")

	return redirect("/letter")


@app.route("/status")
def status():

	return {"status": get_user_status(get_user_id(session))}


if __name__ == "__main__":
	app.run(debug=True)