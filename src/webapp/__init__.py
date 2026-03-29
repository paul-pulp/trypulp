"""
PulpIQ Web App
Self-serve cafe analytics — upload CSV, see instant results.
"""

import os
from flask import Flask, session
from .models import init_db, get_user_by_id


def create_app():
    app = Flask(__name__)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-in-production"),
        DATABASE=os.environ.get("DATABASE_PATH",
                                os.path.join(app.instance_path, "pulpiq.db")),
        SMTP_HOST=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        SMTP_PORT=int(os.environ.get("SMTP_PORT", "587")),
        SMTP_USER=os.environ.get("SMTP_USER", ""),
        SMTP_PASS=os.environ.get("SMTP_PASS", ""),
        APP_URL=os.environ.get("APP_URL", "http://localhost:5000"),
    )

    os.makedirs(app.instance_path, exist_ok=True)

    # Ensure database directory exists (for Render persistent disk)
    db_dir = os.path.dirname(app.config["DATABASE"])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # Initialize database
    with app.app_context():
        init_db(app)

    # Register blueprints
    from .views.auth_views import auth_bp
    from .views.upload_views import upload_bp
    from .views.dashboard_views import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(dashboard_bp)

    # Inject current_user into all templates
    @app.context_processor
    def inject_user():
        user = None
        if "user_id" in session:
            try:
                user = get_user_by_id(session["user_id"])
            except Exception:
                pass
        return {"current_user": user}

    # Root redirect
    @app.route("/")
    def index():
        from flask import session, redirect, url_for
        if "user_id" in session:
            return redirect(url_for("dashboard.dashboard"))
        return redirect(url_for("auth.login"))

    return app
