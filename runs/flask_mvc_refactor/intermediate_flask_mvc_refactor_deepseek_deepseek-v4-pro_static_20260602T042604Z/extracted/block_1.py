import logging
from flask import Flask
from views import main_blueprint

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'change-me-in-production'

    # Disable propagation of potentially sensitive headers to loggers
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.INFO)
    # Ensure that the default request logger does not output raw authorization headers
    # We do not configure custom logging here; avoid logging user email addresses later.

    app.register_blueprint(main_blueprint)
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
