"""
PulpIQ Web App
Self-serve cafe analytics — upload CSV, see instant results.
"""

import os
import threading
import time
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

    # Health check (public — confirms deploy is working)
    @app.route("/health")
    def health():
        from flask import jsonify
        routes = [rule.rule for rule in app.url_map.iter_rules() if "static" not in rule.rule]
        return jsonify({"status": "ok", "routes": sorted(routes)})

    # Admin routes (protected by username/password)
    def _check_admin_auth():
        from flask import request, Response
        auth = request.authorization
        admin_user = os.environ.get("ADMIN_USER", "admin")
        admin_pass = os.environ.get("ADMIN_PASS", "pulpiq")
        if not auth or auth.username != admin_user or auth.password != admin_pass:
            return Response(
                "Admin login required.",
                401,
                {"WWW-Authenticate": 'Basic realm="PulpIQ Admin"'},
            )
        return None

    @app.route("/admin/backup")
    def admin_backup():
        denied = _check_admin_auth()
        if denied:
            return denied
        from flask import jsonify
        from .backup import run_backup
        path = run_backup(app)
        if path:
            return jsonify({"status": "ok", "file": os.path.basename(path)})
        return jsonify({"status": "error", "message": "backup failed"}), 500

    @app.route("/admin/users")
    def admin_users():
        denied = _check_admin_auth()
        if denied:
            return denied
        from flask import render_template, jsonify
        from .models import get_all_users_with_stats
        try:
            users = get_all_users_with_stats()
            return render_template("admin_users.html", users=users)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/admin/cafe/<int:user_id>")
    def admin_cafe_detail(user_id):
        denied = _check_admin_auth()
        if denied:
            return denied
        from flask import render_template, abort, jsonify
        from .models import get_user_by_id, get_snapshots_for_user
        try:
            user = get_user_by_id(user_id)
            if user is None:
                abort(404)
            snapshots = get_snapshots_for_user(user_id)
            return render_template("admin_cafe.html", user=user, snapshots=snapshots)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/admin/feedback")
    def admin_feedback():
        denied = _check_admin_auth()
        if denied:
            return denied
        from flask import render_template, jsonify
        from .models import get_all_feedback
        try:
            feedback = get_all_feedback()
            return render_template("admin_feedback.html", feedback=feedback)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    # Public pages (methodology, terms)
    @app.route("/methodology")
    def methodology():
        from flask import render_template
        return render_template("methodology.html")

    @app.route("/terms")
    def terms():
        from flask import render_template
        return render_template("terms.html")

    # Daily automatic backup (background thread)
    def _daily_backup_loop():
        time.sleep(60)  # wait for app to fully start
        while True:
            try:
                with app.app_context():
                    from .backup import run_backup
                    run_backup(app)
            except Exception as e:
                print(f"[BACKUP] Auto-backup error: {e}", flush=True)
            time.sleep(86400)  # 24 hours

    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN"):
        # Only start in the main process (not the reloader)
        backup_thread = threading.Thread(target=_daily_backup_loop, daemon=True)
        backup_thread.start()

    # Serve landing page images from src/website/
    import pathlib
    website_dir = str(pathlib.Path(__file__).resolve().parent.parent / "website")
    print(f"[APP] Website dir: {website_dir}", flush=True)
    print(f"[APP] Website dir exists: {os.path.isdir(website_dir)}", flush=True)
    if os.path.isdir(website_dir):
        print(f"[APP] Website files: {os.listdir(website_dir)}", flush=True)

    @app.route("/site/<path:filename>")
    def website_static(filename):
        from flask import send_from_directory
        return send_from_directory(website_dir, filename)

    # Debug route to check what's being served
    @app.route("/debug/info")
    def debug_info():
        from flask import jsonify
        files = os.listdir(website_dir) if os.path.isdir(website_dir) else "DIR NOT FOUND"
        return jsonify({
            "website_dir": website_dir,
            "exists": os.path.isdir(website_dir),
            "files": files,
            "index_exists": os.path.isfile(os.path.join(website_dir, "index.html")),
        })

    # Root: landing page for visitors, dashboard for logged-in users
    @app.route("/")
    def index():
        from flask import session, redirect, url_for, send_from_directory
        if "user_id" in session:
            return redirect(url_for("dashboard.dashboard"))
        return send_from_directory(website_dir, "index.html")

    return app
