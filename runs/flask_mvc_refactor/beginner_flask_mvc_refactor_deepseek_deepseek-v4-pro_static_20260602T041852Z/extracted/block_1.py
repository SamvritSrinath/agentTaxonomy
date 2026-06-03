from flask import Flask
from views import register_routes

app = Flask(__name__)

register_routes(app)
