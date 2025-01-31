import tempfile
import os

from flask import Flask, render_template, redirect, request, session

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
def error_404(e):
	return render_template('error_404.html', description=e.description), 404


@app.route("/")
def index():
	return redirect("/resume")


@app.route("/resume")
def resume_redirect():
	if "resume" not in session.keys():
		return redirect("/resume/upload")
	else:
		return redirect("/resume/edit")


@app.route("/resume/upload")
def resume_upload():
	return render_template("resume_upload.html")


@app.route("/resume/edit")
def resume_edit():
	text = session.get("resume", "No resume text extracted.").replace("\n", "\\n")
	return render_template("resume_edit.html", text=text)


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