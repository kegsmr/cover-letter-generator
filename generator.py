import os
import re
from datetime import datetime

import ollama as o
import pdfplumber
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


BASE_MODEL = 'llama3.1'

model = 'cover-letter-generator'
prompt = open("prompt.md", encoding="utf-8").read()

o.create(model=model, from_=BASE_MODEL, system=prompt)
ollama = o.Client()


def main():

	DATA_PATH = os.path.join("database", "local")
	RESUME_PATH = os.path.join(DATA_PATH, "resume.md")
	JOB_PATH = os.path.join(DATA_PATH, "job.md")
	LETTER_PATH = os.path.join(DATA_PATH, "letter.md")
	SAVE_PATH = os.path.join(DATA_PATH, "saved")
	os.makedirs(SAVE_PATH, exist_ok=True)

	try:
		if not os.path.exists(RESUME_PATH):
			print("\033[90mStatus: Reading your resume...\033[90m")
			resume = parse_pdf("resume.pdf")
			open(RESUME_PATH, "w", encoding="utf-8").write(resume)
		else:
			resume = open(RESUME_PATH, encoding="utf-8").read()
	except Exception as e:
		raise Exception("Please save your resume with the filename `resume.pdf`.") from e

	job_posting = input("Job URL/description: ")
	if job_posting.startswith("http://") or job_posting.startswith("https://"):
		job_posting = get_job_posting(job_posting)
	else:
		i = True
		while True:
			try:
				if i:
					i = input("...")
				else:
					i = input("... (Press <CTRL+C>) ")
			except KeyboardInterrupt:
				print()
				break
			job_posting += f"\n{i}"
		print(f"\033[90mStatus: Formatting job posting...\033[90m")
		job_posting = text_to_markdown(job_posting)

	print("\033[34m")
	[print(line) for line in job_posting.splitlines()]
	print("\033[0m")

	open(JOB_PATH, "w", encoding="utf-8").write(job_posting)

	examples = []
	for directory in os.listdir(SAVE_PATH):
		path = os.path.join(SAVE_PATH, directory)
		if os.path.isdir(path):
			# print(f"Loading `{path}`...")
			examples += [load(path)]
	# print(examples)

	feedback = []
	while True:
		cover_letter = generate(examples=examples, resume=resume, job_posting=job_posting, comments=feedback)
		open(LETTER_PATH, "w", encoding="utf-8") \
			.write(cover_letter)
		print("\033[32m")
		[print(line) for line in cover_letter.splitlines()]
		print("\033[0m")
		try:
			f = input("Feedback: ")
		except KeyboardInterrupt:
			break
		if f:
			feedback += [f]

	if input("\nSave? (y/n): ").lower() == "y":
		path = save(SAVE_PATH, resume, job_posting, cover_letter)
		print(f"Saved to `{path}`.")


def generate(examples=[], resume="", job_posting="", comments=[], sample="", callback=lambda message: print(f"\033[90mStatus: {message}\033[90m"), debug=False):
	
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
				# "```"
			]

			lines += [f"*   {comment.strip()}" for comment in comments]
			
			# lines += ["```"]

		if not sample:
			lines += [
				"",
				"Now write the candidate's cover letter based on their resume and the job posting.",
			]
		else:
			lines += [
				"",
				"Now modify the candidate's last cover letter to fit the new job posting. Here is the cover letter to modify:",
				"```",
				sample,
				"```"
			]
		
		lines += [
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

	# if len(comments) < 1:
	callback("Writing draft 1...")
	# else:
		# callback("Reviewing your feedback...")

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

	if debug:
		log_messages(messages)


	DONE_MESSAGE = "All Done!"
	for n in range(2):
		callback(f"Reviewing draft {n + 1}...")
		v = verify(resume, cover_letter, debug=debug)
		if v is True:
			callback(DONE_MESSAGE)
			return cover_letter
		else:
			callback(f"Writing draft {n + 2}...")
			cover_letter = revise(messages, justification=v, resume=resume, debug=debug)
	callback(DONE_MESSAGE)
	return cover_letter


def verify(resume, cover_letter, debug=False): #TODO compare job description to cover letter

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
		"What qualifications did the candidate mention in the cover letter, but not their resume (if any)?",
		"",
		"I want to ensure that the candidate is not exaggerating their skills and/or experience." #"I suspect the candidate may be exaggerating their skills and experience."
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
			"content": "So, did the candidate mention any qualifications in the cover letter, but not the resume?\n\nCould they be exaggerating their skills and/or experience?\n\nReply in one word: \"Yes\" or \"No\"."
		}
	]

	choice = ollama.chat(model, messages=messages).message.content

	messages += [
		{
			"role": "assistant",
			"content": choice
		}
	]

	if debug:
		log_messages(messages)

	if choice.lower().startswith("no"):
		return True
	else:
		return differences
	

def revise(messages, justification, resume, debug=False):

	messages += [{
		"role": "user",
		"content": f"Write a revised version of the cover letter.\n\nRemove qualifications not mentioned in the resume:\n```\n{resume}\n```\n\nReply ONLY with the cover letter, no commentary!"
	}]

	cover_letter = ollama.chat(model, messages=messages).message.content

	messages += [{
		"role": "assistant",
		"content": cover_letter
	}]

	if debug:
		log_messages(messages)

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


def get_job_posting(url: str, callback=lambda message: print(f"\033[90mStatus: {message}\033[90m")):

	callback("Fetching job description...")

	html = get_html(url)
	text = parse_html(html)

	callback("Formatting job description...")

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
	
	if reply.startswith("markdown"):
		reply = reply.replace("markdown", "", 1)

	return reply.strip()


def pick_job_title(job_posting: str) -> str:

	messages = [
		{
			"role": "user",
			"content": "Please choose a title for this job posting.\n\n" \
				"```\n" \
				f"{job_posting}\n" \
				"```\n\n" \
				"Format the title as `<job title> at <company name>`.\n\n" \
				"Reply ONLY with the job title, no commentary!"
		}
	]

	reply = ollama.chat(model=BASE_MODEL, messages=messages) \
		.message \
		.content \

	reply = reply.split("\n")[0]

	return reply.strip()


def filter_non_alpha_numeric(text: str) -> str:

	import re

	return " ".join(re.sub('[^0-9a-zA-Z ]+', " ", text).split())


def sanitize_directory_name(text: str) -> str:

	text = text.replace("..", "")
	
	for character in ["/", "\\"]:
		text = text.replace(character, "")

	text = text.replace("..", "")

	text = text.strip()

	return text


def save(path, resume, job_posting, cover_letter, title="", save_id="") -> str:

	if not save_id:
		save_id = datetime.now().strftime("%Y%m%d%H%M%S")

	path = os.path.join(path, save_id)
	
	os.makedirs(path, exist_ok=True)

	resume_path = os.path.join(path, "resume.md")
	job_path = os.path.join(path, "job.md")
	letter_path = os.path.join(path, "letter.md")
	title_path = os.path.join(path, "title.md")

	for filename, data in [(resume_path, resume), (job_path, job_posting), (letter_path, cover_letter), (title_path, title if title else pick_job_title(job_posting))]:
		with open(filename, "w", encoding="utf-8") as file:
			file.write(data)

	return path


def load(path) -> tuple:

	paths = [
		os.path.join(path, "resume.md"),
		os.path.join(path, "job.md"),
		os.path.join(path, "letter.md")
	]

	data = []

	for path in paths:
		data.append(open(path, encoding="utf-8").read())

	return tuple(data)


def log_messages(messages: list):

	global message_log_cleared

	if "message_log_cleared" not in globals().keys():
		with open("messages.log", "w") as file:
			file.write("")
		message_log_cleared = True

	with open("messages.log", "a", encoding="utf-8") as file:
		newlines = 3 * "\n"
		file.write(f"\033[1mCOVERSATION AT {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\033[0m{newlines}")
		for message in messages:
			role = message["role"]
			content = re.sub(r'\n{3,}', '\n\n', message["content"]).strip() #.replace("\n", "\n\t")
			color = "\033[34m" if role == "user" else "\033[32m"
			file.write(f"{color}{role.upper()}:\033[0m {content}{newlines}")
		file.write(100 * "-" + newlines)


if __name__ == "__main__":
	main()