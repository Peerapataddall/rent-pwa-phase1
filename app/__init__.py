from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    # ✅ ensure Flask finds app/templates and app/static
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object("app.config.Config")

    db.init_app(app)
    migrate.init_app(app, db)

    from app.blueprints.pages import bp as pages_bp
    from app.blueprints.api import bp as api_bp
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
