"""Sample Python app for parser testing."""

import os
from pathlib import Path

from flask import Flask, jsonify

from .models import User
from .utils import validate_input

app = Flask(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
DEBUG = os.getenv("DEBUG")


@app.route("/api/users", methods=["GET"])
def get_users():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])


@app.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id: int):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())


async def process_data(data: dict) -> list[str]:
    """Process incoming data asynchronously."""
    validated = validate_input(data)
    return [str(item) for item in validated]


if __name__ == "__main__":
    app.run(debug=True)
