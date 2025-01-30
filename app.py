import subprocess
import tempfile
import os
import shutil
from argparse import ArgumentParser

from flask import Flask, render_template, redirect, request, session
import ollama as o
import pdfplumber
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


subprocess.run(["python", "-m", "playwright", "install"], check=True)

BASE_MODEL = 'llama3.1'

model = 'cover-letter-generator'
system = open("prompt.md", encoding="utf-8").read()

o.create(model=model, from_=BASE_MODEL, system=system)
ollama = o.Client()

app = Flask(__name__)
app.secret_key = os.urandom(24)	


def main():

	parser = ArgumentParser()
	parser.add_argument("-s", "--serve", action="store_true")

	args = parser.parse_args()

	if args.serve:
		app.run(debug=True)
	else:
		cmd()


def cmd():

	try:
		if not os.path.exists("resume.md"):
			_resume = parse_pdf("resume.pdf")
			open("resume.md", "w", encoding="utf-8").write(_resume)
		else:
			_resume = open("resume.md", encoding="utf-8").read()
	except Exception as e:
		raise Exception("Please save your resume with the filename `resume.pdf`.") from e

	_input = input("Job URL/description: ")
	if _input.startswith("http://") or _input.startswith("https://"):
		_input = get_job_posting(_input)
	else:
		i = True
		while True:
			try:
				if i:
					i = input()
				else:
					i = input("(Press <CTRL+C> to end) ")
			except KeyboardInterrupt:
				print()
				break
			_input += f"\n{i}"
		_input = text_to_markdown(_input)

	print("\033[34m")
	[print(line) for line in _input.splitlines()]
	print("\033[0m")

	open("input.md", "w", encoding="utf-8").write(_input)

	examples = []
	n = 1
	while os.path.exists(f"input_{n}.md") \
		and os.path.exists(f"output_{n}.md"):
		examples += [(
			_resume,
			open(f"input_{n}.md", encoding="utf-8").read(),
			open(f"output_{n}.md", encoding="utf-8").read()
		)]
		n += 1

	feedback = []
	while True:
		_output = generate(examples=examples, resume=_resume, job_posting=_input, comments=feedback)
		open("output.md", "w", encoding="utf-8") \
			.write(_output)
		print("\033[32m")
		[print(line) for line in _output.splitlines()]
		print("\033[0m")
		try:
			f = input("Feedback: ")
		except KeyboardInterrupt:
			break
		if f:
			feedback += [f]

	if input("\nSave? (y/n): ").lower() == "y":

		n = 1
		while os.path.exists(f"input_{n}.md") \
			and os.path.exists(f"output_{n}.md"):
			n += 1

		shutil.copy("input.md", f"input_{n}.md")
		shutil.copy("output.md", f"output_{n}.md")


def generate(examples=[], resume="", job_posting="", comments=[]):
	
	messages = []

	def format_user_message(resume, job_posting, comments=[]):
		
		lines = [
			"Read this candidate's resume:",
			"```",
			resume,
			"```",
			"",
			"And read this job posting:",
			"```",
			job_posting,
			"```"
		]

		if len(comments) > 0:

			lines += [
				"", 
				"The candidate also stated the following:",
				"```"
			]

			lines += [f"- {comment}" for comment in comments]
			
			lines += ["```"]

		lines += [
			"",
			"Now write the candidate's cover letter based on their resume and the job posting.",
			"",
			"Reply ONLY with the cover letter, no commentary!"
		]

		# print(*lines)

		return "\n".join(lines)

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
			"content": format_user_message(resume, job_posting, comments)
		}
	]

	# print([message["content"] for message in messages])

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

	# print(f"Differences: {differences}")

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


def parse_pdf(filename: str) -> str:
	text = ""
	with pdfplumber.open(filename) as pdf:
		for page in pdf.pages:
			text += page.extract_text() + "\n"
	return text_to_markdown(text)


def get_html(url: str) -> str:
	with sync_playwright() as p:
		browser = p.chromium.launch(headless=True)
		page = browser.new_page()
		page.goto(url)
		content = page.content()
		browser.close()
		return content


def get_job_posting(url: str):

	html = get_html(url)
	text = parse_html(html)


	messages = [
		{
			"role": "user",
			"content": "The following text was extracted from a job posting website.\n\n" \
				"```\n" \
				f"{text}\n" \
				"```\n\n" \
				"Please format all text relevant to the job posting into markdown, include all relevant information.\n\n"
				"Reply ONLY with the markdown, no commentary!"
		}
	]

	reply = ollama.chat(model=BASE_MODEL, messages=messages) \
		.message \
		.content \
		.replace("\n", "\n\n")

	if "```" in reply:
		try:
			reply = reply.split("```")[1]
		except Exception as e:
			print(f"Error: {e}")

	return reply



def parse_html(html: str):

	# Parse the HTML with BeautifulSoup
	soup = BeautifulSoup(html, 'html.parser')
	
	# Remove unwanted elements (e.g., script, style, etc.)
	for unwanted in soup(['script', 'style', 'head', 'meta', 'noscript']):
		unwanted.decompose()
	
	# Extract the visible text
	visible_text = soup.get_text(separator='\n').strip()
	
	t = []
	for line in visible_text.splitlines():
		if line:
			t.append(line.strip())

	return "\n".join(t)


def text_to_markdown(text: str) -> str:

	messages = [
		{
			"role": "user",
			"content": "Please format the following text in markdown.\n\n" \
				"```\n" \
				f"{text}\n" \
				"```\n\n" \
				"Reply ONLY with the markdown, no commentary!"
		}
	]

	reply = ollama.chat(model=BASE_MODEL, messages=messages) \
		.message \
		.content \
		.replace("\n", "\n\n")

	if "```" in reply:
		try:
			reply = reply.split("```")[1]
		except Exception as e:
			print(f"Error: {e}")

	return reply
	

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
	main()