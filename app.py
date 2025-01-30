import tempfile
import os

from flask import Flask, render_template, redirect, request, session
import ollama as o
import pdfplumber


BASE_MODEL = 'llama3.1'

model = 'cover-letter-generator'
system = open("prompt.md", encoding="utf-8").read()

o.create(model=model, from_=BASE_MODEL, system=system)
ollama = o.Client()

app = Flask(__name__)
app.secret_key = os.urandom(24)	


def test():

	test_resume = parse_pdf("test_resume.pdf")
	test_input = open("test_input_1.txt", encoding="utf-8").read()
	
	examples = []
	n = 1
	while os.path.exists(f"test_example_input_{n}") \
		and os.path.exists(f"test_example_output_{n}"):
		examples += [(
			test_resume,
			open(f"test_example_input_{n}.txt", encoding="utf-8").read(),
			open(f"test_example_output_{n}.txt", encoding="utf-8").read()
		)]
		n += 1

	open("test_output.txt", "w", encoding="utf-8") \
		.write(generate(examples=examples, resume=test_resume, job_posting=test_input))


def parse_pdf(filename: str) -> str:
	text = ""
	with pdfplumber.open(filename) as pdf:
		for page in pdf.pages:
			text += page.extract_text() + "\n"
	return text


def generate(examples=[], resume="", job_posting=""):
	
	messages = []

	def format_user_message(resume, job_posting):
		return "\n".join([
			"Read this candidate's resume:",
			"```",
			resume,
			"```",
			"",
			"And read this job posting:"
			"```",
			job_posting,
			"```",
			"",
			"Now write the candidate's cover letter based on their resume and the job posting.",
			"",
			"Reply ONLY with the cover letter, no commentary!"
		])

	for r, j, c in examples:
		messages += [
			{
				"role": "user",
				"content": format_user_message(r, j)
			},
			{
				"role": "assistant",
				"content": c
			}
		]

	messages += [
		{
			"role": "user",
			"content": format_user_message(resume, job_posting)
		}
	]

	cover_letter = ollama \
		.chat(model, messages=messages) \
		.message \
		.content \
		.strip() \
		.replace("\n\n", "\n") \
		.replace("\n", "\n\n")

	messages += [
		{
			"role": "assistant",
			"content": cover_letter
		}
	]

	for _ in range(5):
		v = verify(resume, cover_letter)
		if v is True:
			return cover_letter
		else:
			cover_letter = revise(messages, justification=v, resume=resume)

	return cover_letter


def verify(resume, cover_letter):

	content = "\n".join([
		"Read this candidate's resume:",
		"```",
		resume,
		"```",
		"",
		"Now read the candidate's cover letter:",
		"```",
		cover_letter,
		"```",
		"",
		"What qualifications did the candidate mention in the cover letter, but not their resume (if any)?"
	])

	messages = [
		{
			"role": "user",
			"content": content
		}
	]

	differences = ollama.chat(model, messages=messages).message.content

	print(f"Differences: {differences}")

	messages += [
		{
			"role": "assistant",
			"content": differences
		},
		{
			"role": "user",
			"content": "Are there any qualifications mentioned in the cover letter that aren't from the resume?\n\nReply in one word: \"Yes\" or \"No\"."
		}
	]

	choice = ollama.chat(model, messages=messages).message.content

	# print(f"Choice: {choice}")

	if choice.lower().startswith("no"):
		return True
	else:
		return differences
	

def revise(messages, justification, resume):

	messages += [{
		"role": "user",
		"content": f"Write a revised version of the cover letter.\n\nRemove qualifications not mentioned in the resume:\n```\n{resume}\n```\n\nReply ONLY with the cover letter, no commentary!"
	}]

	cover_letter = ollama.chat(model, messages=messages).message.content

	messages += [{
		"role": "assistant",
		"content": cover_letter
	}]

	return cover_letter \
		.strip() \
		.replace("\n\n", "\n") \
		.replace("\n", "\n\n")


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


# @app.route("/login")
# def login():
# 	return render_template("login.html")


# @app.route("/api/login", methods=["POST"])
# def api_login():
# 	return


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
	print(text)

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
	print(text)

	# Save the resume text in session cookie
	session["resume"] = text

	# Success
	return {"message": "Resume updated successfully", "text": text}, 200


@app.route("/api/generate", methods=["POST"])
def api_generate():
	return


if __name__ == "__main__":
	test()
	# app.run(debug=True)