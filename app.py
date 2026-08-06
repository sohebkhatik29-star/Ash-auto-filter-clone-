from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "VJ File Store Bot"
