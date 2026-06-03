import os
import sqlite3
from flask import g

# Support both database.db and app.db, defaulting to app.db
DATABASE = "app.db"
if os.path.exists("database.db") and not os.path.exists("app.db"):
    DATABASE = "database.db"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def close_db(exception=None):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()
