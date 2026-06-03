import logging
import re
from flask import Flask
from views import admin_bp

class SensitiveDataFilter(logging.Filter):
    """Redact sensitive data from log records."""
    def filter(self, record):
        if hasattr(record, 'msg'):
            # Redact Authorization header values
            record.msg = re.sub(r'Authorization: Bearer \S+', 'Authorization: [REDACTED]', str(record.msg))
            # Redact email addresses
            record.msg = re.sub(r'[\w\.-]+@[\w\.-]+', '[EMAIL_REDACTED]', str(record.msg))
        return True

def create_app():
    app = Flask(__name__)
    app.config['LOCAL_ADMIN_TOKEN'] = 'secret-admin-token'  # In production, load from environment

    # Configure logging with sensitive data filter
    handler = logging.StreamHandler()
    handler.addFilter(SensitiveDataFilter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])

    # Register blueprints
    app.register_blueprint(admin_bp, url_prefix='/admin')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run()
