from flask import Flask
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)


@app.route("/")
def index():
    return "indexing 123"



if __name__ in "__main__":
    app.run(debug=True)