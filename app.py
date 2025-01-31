import tempfile
import os

from flask import Flask, render_template, redirect, request, session, url_for

from generator import *


app = Flask(__name__)

app.secret_key = os.urandom(24)	


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
	return redirect("/home")


@app.route("/home")
def home():
	return render_template("home.html")


@app.route("/login")
def login():
	return render_template("login.html")


@app.route("/resume")
def resume():
	return render_template("resume.html")


@app.route("/sample")
def sample():
	return render_template("sample.html")


@app.route("/job")
def job():
	return render_template("job.html")


@app.route("/letter")
def letter():
	job = open("input.md", "r", encoding="utf-8").read().replace("\n", "\\n")
	resume = open("resume.md", "r", encoding="utf-8").read().replace("\n", "\\n")
	letter = open("output.md", "r", encoding="utf-8").read()
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