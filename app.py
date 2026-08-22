from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'ASH FILE STORE & CLONE MANAGER BOT'


if __name__ == "__main__":
    app.run()
