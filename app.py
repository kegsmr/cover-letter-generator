import tempfile
import os
import json
from datetime import timedelta
import time 
import random
import re
import shutil
import hashlib
from functools import lru_cache
import zipfile

from flask import Flask, render_template as flask_render_template, redirect, request, session, url_for, send_from_directory, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from generator import *


app = Flask(__name__)

limiter_options = {"enabled": True, "default_limits": ["60 per minute"]}
limiter_options_path = "limiter.json"
if not os.path.exists(limiter_options_path):
	with open(limiter_options_path, "w", encoding="utf-8") as limiter_options_file:
		json.dump(limiter_options, limiter_options_file, indent=4)
else:
	with open(limiter_options_path, "r", encoding="utf-8") as limiter_options_file:
		for key, value in json.load(limiter_options_file).items():
			limiter_options[key] = value
limiter_enabled = limiter_options.pop("enabled")
limiter = Limiter(app=app, key_func=get_remote_address, **limiter_options)

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

ads_options = {"client": "", "publisher": ""}
ads_options_path = "ads.json"
if not os.path.exists(ads_options_path):
	with open(ads_options_path, "w", encoding="utf-8") as ads_options_file:
		json.dump(ads_options, ads_options_file, indent=4)
else:
	with open(ads_options_path, "r", encoding="utf-8") as ads_options_file:
		for key, value in json.load(ads_options_file).items():
			ads_options[key] = value
google_ads_client = ads_options["client"]
google_ads_publisher = ads_options["publisher"]

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

LOCAL_USER_ID = "local"
local_user_enabled = False

database_path = "database"
os.makedirs(database_path, exist_ok=True)
for directory in os.scandir(database_path):
	if directory.is_dir():
		if directory.name == LOCAL_USER_ID:
			continue
		last_modification = 0 #os.path.getmtime(directory.path)
		for root, _, files in os.walk(directory.path):
			for file in files:
				file_path = os.path.join(root, file)
				last_modification = max(last_modification, os.path.getmtime(file_path))
		if not last_modification or (time.time() - last_modification) > (session_options["lifetime"] * 86400):
			print(f"Deleting `{directory.path}`...")
			shutil.rmtree(directory.path, ignore_errors=True)

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
	if local_user_enabled and request.remote_addr == "127.0.0.1":
		return LOCAL_USER_ID
	if "user_id" in s:
		user_id = sanitize_directory_name(s["user_id"])
		if user_id != LOCAL_USER_ID:
			return user_id
	new_user_id = f"{int(time.time() * 1000)}-{random.randint(1000, 9999)}"
	s["user_id"] = new_user_id
	return new_user_id


def get_user_path(user_id, path="", missing_ok=False) -> str:
	user_path = os.path.join(database_path, user_id)
	os.makedirs(user_path, exist_ok=True)
	if path:
		user_path = os.path.join(user_path, path)
		if missing_ok or os.path.exists(user_path):
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
	

def get_user_file_mtime(user_id, path=""):
	user_path = get_user_path(user_id, path)
	if user_path:
		return os.path.getmtime(get_user_path(user_id, path))
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


def set_user_status(user_id, status=None):
	if status:
		user_status[user_id] = status
	elif user_id in user_status:
		user_status.pop(user_id)


def get_user_status(user_id, default=None):
	return user_status.get(user_id, default)


def render_template(template, **context):

	if google_ads_client:
		context.setdefault("google_ads_client", google_ads_client)

	# etag = get_etag({"template": template, "context": context})
	# client_etag = request.headers.get('If-None-Match')
	
	# if etag and client_etag:
	# 	client_etag = client_etag.strip("\"")
	# 	if etag == client_etag:
	# 		return Response(status=304)

	# print(f"{etag} != {client_etag}")

	response = Response(flask_render_template(template, **context))

	# if etag:
	# 	response.set_etag(etag)

	return response


def get_etag(data):
	try:
		serialized_data = json.dumps(data, sort_keys=True, default=str)  # Ensure consistent order
		return hashlib.md5(serialized_data.encode()).hexdigest()  # Generate hash
	except Exception:
		return None


def get_loaded_id(user_id, job) -> str:
	if "loaded" in session:
		if job == read_user_file(user_id, os.path.join("saved", session["loaded"], "job.md")):
			return session["loaded"]
	return ""


def log_error(request, e):
	user_id = session.get("user_id", "")
	error = e.code if hasattr(e, 'code') else f"\"{e}\""
	with open("error.log", "a") as file:
		file.write(f"{datetime.now().strftime('[%Y/%m/%d %H:%M:%S]')} - {user_id if user_id else request.remote_addr} - \"{request.method} {request.path}\" - {error}\n")


def log_access(request):
	address = request.remote_addr
	user_id = session.get("user_id", "")
	name = session.get("name", "")
	if user_id:
		if name:
			identifier = f"{address} - {user_id} - {name}"
		else:
			identifier = f"{address} - {user_id}"
	else:
		identifier = address
	with open("access.log", "a") as file:
		file.write(f"{datetime.now().strftime('[%Y/%m/%d %H:%M:%S]')} - {identifier} - \"{request.method} {request.path}\"\n")


@app.before_request
def before_request():
	log_access(request)
	session.permanent = True


@app.after_request
def after_request(response):
	response.cache_control.private = True
	response.cache_control.max_age = 5
	response.cache_control.must_revalidate = True
	return response


@app.errorhandler(404)
def error_404(e):
	log_error(request, e)
	return render_template('error.html', error_message="Page not found"), 404


@app.errorhandler(500)
def error_500(e):
	log_error(request, e)
	return render_template('error.html', error_message="Internal server error, please try again later."), 500


@app.errorhandler(Exception)
def error_generic(e):
	if app.debug:
		raise e
	else:
		log_error(request, e)
		return render_template('error.html', error_message="An unexpected error occurred, please try again later."), 500


@app.route('/.well-known/acme-challenge/<filename>')
def serve_challenge(filename):
	certbot_redirect = os.getenv("CERTBOT_REDIRECT")
	if certbot_redirect:
		return redirect(f"http://{certbot_redirect}/.well-known/acme-challenge/{filename}", code=301)
	else:
		challenge_directory = os.path.join(os.getcwd(), '.well-known', 'acme-challenge')
		return send_from_directory(challenge_directory, filename)


@app.route("/ads.txt")
def serve_ads_txt():
	if google_ads_publisher:
		ads_content = f"google.com, {google_ads_publisher}, DIRECT, f08c47fec0942fa0"
		return ads_content, 200, {"Content-Type": "text/plain"}
	else:
		return {"error", "Page not found."}, 404


@app.route("/")
def index():

	return redirect("/home")


@app.route("/home")
def home():

	user_id = get_user_id(session)
	jobs = get_user_jobs(user_id)
	name = session.get("name", "")

	if name:
		message = f"Welcome back, {name}!"
	else:
		message = "Welcome to the AI Cover Letter Generator"


	if jobs:
		return render_template("dashboard.html", jobs=jobs, message=message)
	else:
		if not get_user_path(user_id, "resume.md") or not read_user_file(user_id, "resume.md"):
			url = "/resume"
		elif not get_user_path(user_id, "sample.md") or not read_user_file(user_id, "sample.md"):
			url = "/sample"
		else:
			url = "/job"
		return render_template("welcome.html", url=url)


@app.route("/resume", methods=["GET", "POST"])
@limiter.limit(lambda: "6 per minute" if request.method == "POST" and "resume" in request.files and request.files["resume"].filename else None)
def resume():

	user_id = get_user_id(session)
	
	if request.method == "GET":

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
			session["name"] = name_from_resume(resume)

			# Delete the temporary file
			os.remove(filename)

			set_user_status(user_id)

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

	user_id = get_user_id(session)

	if request.method == "GET":

		s = read_user_file(user_id, "sample.md")
		return render_template("sample.html", sample=s, back=("/home" if get_user_jobs(user_id) else "/resume"))

	else:

		if "sample" in request.form:

			url = request.args.get('redirect')

			write_user_file(request.form["sample"], user_id, "sample.md")

			return redirect(url)
		
		else:

			return {"error": "No sample letter provided."}, 400


@app.route("/job", methods=["GET", "POST"])
@limiter.limit(lambda: "6 per minute" if request.method == "POST" and "url" in request.form and request.form["url"] else None)
def job():

	user_id = get_user_id(session)

	if request.method == "GET":

		job_posting = read_user_file(user_id, "job.md")

		return render_template("job.html", job=job_posting, back=("/home" if get_user_jobs(user_id) else "/sample"))

	else:

		if "url" in request.form and request.form["url"]:

			url = request.form["url"]

			if not (url.startswith("http://") or url.startswith("https://")):
				url = f"http://{url}"

			try:
				job_posting = f"Fetched from: {url}\n\n\n{get_job_posting(url, callback=lambda message: set_user_status(user_id, message))}"
			except Exception as e:
				job_posting = f"Unable to fetch job description.\n\nYou can still copy and paste it manually." + f"\n\nERROR:\n{e}" if app.debug else ""

			write_user_file(job_posting, user_id, "job.md")

			set_user_status(user_id)

			return render_template("job.html", job=job_posting, back=("/home" if get_user_jobs(user_id) else "/sample"))

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
@limiter.limit("6 per minute")
def letter_generate():

	user_id = get_user_id(session)
	save_path = os.path.join(database_path, user_id, "saved")

	# POST method used for regenerating cover letter with feedback
	feedback = ""
	if request.method == "POST":
		if "feedback" in request.form:
			feedback = request.form["feedback"]
			if feedback:
				session["feedback"].append(feedback)

	# Read files from user directory
	resume = read_user_file(user_id, "resume.md")
	job = read_user_file(user_id, "job.md")
	sample = read_user_file(user_id, "sample.md")# if len(session["feedback"]) < 1 else ""

	# Save old cover letter if regenerating (so that the modified cover letter can be an example for Ollama)
	if request.method == "POST":
		if "letter" in request.form:
			# print("Using modified letter as sample...")
			letter = request.form["letter"]
			sample = letter
			# letter = request.form["letter"]
			# title = read_user_file(user_id, "title.md")
			# if letter and title:
			# 	save_id = get_loaded_id(user_id, job)
			# 	path = save(save_path, resume, job, letter, title=title, save_id=save_id)
			# 	# write_user_file(letter, user_id, "letter.md")
			# 	session["loaded"] = os.path.split(path)[1]

	# Use saved cover letters as examples for Ollama
	examples = []
	# if sample:
	# 	examples += [(resume, "No job description provided.", sample)]
	if os.path.exists(save_path):
		for directory in os.listdir(save_path):
			# if read_user_file(user_id, "letter.md") != read_user_file(user_id, os.path.join(save_path, directory, "letter.md")):
			# # if feedback or read_user_file(user_id, "letter.md") != read_user_file(user_id, os.path.join(save_path, directory, "letter.md")):
			examples += [load(os.path.join(save_path, directory))]
	if len(examples) > 10:
		examples = examples[len(examples) - 10:]
	
	# Clear logs
	write_user_file("# Nothing here yet...", user_id, "messages.md")

	# Use Ollama to generate the job title and cover letter
	title = pick_job_title(job)
	letter = generate(examples, 
				   resume, 
				   job, 
				   comments=session["feedback"], 
				   sample=sample, 
				   callback=lambda message: set_user_status(user_id, message), 
				   debug=app.debug, 
				   log_path=get_user_path(user_id, "messages.md", missing_ok=True)
				)
	
	write_user_file("# Done", user_id, "messages.md", mode="a")

	# Write files in user directory
	write_user_file(title, user_id, "title.md")
	write_user_file(letter, user_id, "letter.md")

	# Save new cover letter in `saved` directory (use loaded save ID if job description is the same)
	save_id = get_loaded_id(user_id, job)
	path = save(save_path, resume, job, letter, title=title, save_id=save_id)
	session["loaded"] = os.path.split(path)[1]

	# Reset user status so it doesn't leak into future loading screens
	set_user_status(user_id)

	return redirect("/letter")


@app.route("/letter/save", methods=["POST"])
def letter_save():

	user_id = get_user_id(session)

	save_path = os.path.join(database_path, user_id, "saved")

	title = read_user_file(user_id, "title.md")
	resume = read_user_file(user_id, "resume.md")
	job = read_user_file(user_id, "job.md")
	letter = request.form["letter"]
	
	save_id = get_loaded_id(user_id, job)

	write_user_file(letter, user_id, "letter.md")
	save_path = save(save_path, resume, job, letter, title=title, save_id=save_id)

	session["loaded"] = os.path.split(save_path)[1]

	return redirect("/home")


@app.route("/letter/load/<save_id>")
def letter_load(save_id):

	session["loaded"] = save_id

	save_id = sanitize_directory_name(save_id)
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


@app.route("/letter/delete/<save_id>")
def letter_delete(save_id):

	save_id = sanitize_directory_name(save_id)
	user_id = get_user_id(session)

	directory = get_user_path(user_id, os.path.join("saved", save_id))

	shutil.rmtree(directory)

	if session["loaded"] == save_id:
		session.pop("loaded")

	return redirect(f"/home#letters")


@app.route("/letter/messages")
def letter_messages():

	return render_template("messages.html", messages=read_user_file(get_user_id(session), "messages.md"))


@app.route("/status")
def status():

	return {"status": get_user_status(get_user_id(session), "Hang tight...")}


@app.route("/export")
@limiter.limit("6 per minute")
def export():

    user_id = get_user_id(session)
    user_path = get_user_path(user_id)
    
    if not user_path or not os.path.exists(user_path):
        return {"error": "User data not found."}, 404
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_zip:
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(user_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, user_path)
                    zipf.write(file_path, arcname)
    
        temp_zip_path = temp_zip.name
    
    return send_from_directory(os.path.dirname(temp_zip_path), os.path.basename(temp_zip_path), as_attachment=True, download_name=f"cover-letter-generator-{datetime.now().strftime('%Y%m%d%H%M%S')}.zip")


@app.route("/delete")
def delete():

    user_id = get_user_id(session)
    user_path = get_user_path(user_id)
    
    if not user_path or not os.path.exists(user_path):
        return {"error": "User data not found."}, 404
	
    try:

        shutil.rmtree(user_path)
        session.clear()

        return redirect("/home") #{"message": "User data deleted successfully."}, 200
	
    except Exception as e:

        return {"error": f"Failed to delete user data: {str(e)}"}, 500


@limiter.request_filter
def limiter_request_filter():

    return app.debug or not limiter_enabled


if __name__ == "__main__":

	local_user_enabled = True

	app.run(debug=True)