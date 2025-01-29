from flask import Flask, render_template, redirect


app = Flask(__name__)


@app.route("/")
def index():
	if False:
		return redirect("/login")
	else:
		return render_template("app.html")


@app.route("/login")
def login():
	return render_template("login.html")


@app.route("/api/login", methods=["POST"])
def api_login():
	return


if __name__ == "__main__":
	app.run(debug=True)