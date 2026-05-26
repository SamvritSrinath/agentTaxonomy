```python app.py
import os
import logging
from flask import Flask, request, jsonify, session, g
from config import Config
from models import db, User
from services import UserService, AuthService

# Configure logging to ensure no sensitive identifiers are logged
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
