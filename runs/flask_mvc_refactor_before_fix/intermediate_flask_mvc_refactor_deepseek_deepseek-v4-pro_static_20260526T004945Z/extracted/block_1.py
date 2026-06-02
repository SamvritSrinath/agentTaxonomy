from flask import Flask
from database import close_db, init_db
from routes.user_routes import user_bp
from routes.admin_routes import admin_bp

def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE='db.sqlite3',
        # A default admin token for demonstration – tests can override
        ADMIN_TOKEN='admin-secret',
        TOKENS={
            'admin-secret': 'admin_user'
        }
    )
    app.teardown_appcontext(close_db)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)

    # CLI command to initialise the database (keeps tests happy if they call init_db)
    @app.cli.command('init-db')
    def init_db_command():
        """Clear the existing data and create new tables."""
        init_db()
        click.echo('Initialized the database.')

    return app

app = create_app()

# Make init_db importable at package level for test fixtures
# (some test suites rely on `from app import init_db`)
from database import init_db as _init_db
init_db = _init_db

# also expose the Flask app factory for advanced usage
__all__ = ['app', 'init_db', 'create_app']
