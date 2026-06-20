import os
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime, timezone

# Allow HTTP for local OAuth development
os.environ.setdefault('OAUTHLIB_INSECURE_TRANSPORT', '1')


def create_app():
    app = Flask(__name__)

    # Load config
    from config import get_config
    app.config.from_object(get_config())

    # Add computed OAuth redirect URIs to config
    backend_url = os.environ.get('BACKEND_URL', 'http://localhost:5000')
    app.config['GOOGLE_AUTH_REDIRECT_URI'] = f"{backend_url}/api/auth/google/callback"
    app.config['GSC_REDIRECT_URI'] = f"{backend_url}/api/gsc/callback"

    # CORS
    CORS(app,
         origins=app.config.get('CORS_ORIGINS', ['http://localhost:3000']),
         supports_credentials=True,
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

    # Database
    from models import db
    db.init_app(app)

    # ── Register blueprints ──────────────────────────────────────────────────
    from routes.auth_routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    from routes.audit_routes import audit_bp
    app.register_blueprint(audit_bp, url_prefix='/api/audit')

    # ── Health check (public) ────────────────────────────────────────────────
    @app.route('/api/health')
    def health():
        return jsonify({
            'status': 'ok',
            'message': 'SEO Audit API is running',
            'version': '1.0.0',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'environment': os.environ.get('FLASK_ENV', 'development')
        })

    # ── Global error handlers ────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            'status': 'error',
            'error': {'code': 'NOT_FOUND', 'message': 'Endpoint not found'}
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({
            'status': 'error',
            'error': {'code': 'METHOD_NOT_ALLOWED', 'message': 'Method not allowed'}
        }), 405

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({
            'status': 'error',
            'error': {'code': 'SERVER_ERROR', 'message': 'Internal server error'}
        }), 500

    # ── Database init ────────────────────────────────────────────────────────
    with app.app_context():
        try:
            db.create_all()
            _seed_algorithm_updates()
            app.logger.info("Database tables ready")
        except Exception as e:
            app.logger.warning(f"DB init warning: {e}")

    return app


def _seed_algorithm_updates():
    """Seed known Google algorithm updates."""
    from models import db, AlgorithmUpdate

    if AlgorithmUpdate.query.count() > 0:
        return  # Already seeded

    import datetime as dt

    updates = [
        {'update_name': 'March 2025 Core Update',          'update_date': '2025-03-16', 'update_type': 'core',             'severity': 'major', 'description': 'Broad core algorithm update affecting site quality signals'},
        {'update_name': 'February 2025 Spam Update',       'update_date': '2025-02-10', 'update_type': 'spam',             'severity': 'minor', 'description': 'Targeting spammy link practices and AI-generated spam'},
        {'update_name': 'January 2025 Helpful Content',    'update_date': '2025-01-15', 'update_type': 'helpful-content',  'severity': 'major', 'description': 'Continued refinements to helpful content system'},
        {'update_name': 'November 2024 Core Update',       'update_date': '2024-11-11', 'update_type': 'core',             'severity': 'major', 'description': 'Broad core update with significant ranking changes'},
        {'update_name': 'August 2024 Core Update',         'update_date': '2024-08-15', 'update_type': 'core',             'severity': 'major', 'description': 'Major core update targeting content quality and E-E-A-T'},
        {'update_name': 'June 2024 Spam Update',           'update_date': '2024-06-20', 'update_type': 'spam',             'severity': 'minor', 'description': 'Targeting site reputation abuse and expired domain abuse'},
        {'update_name': 'March 2024 Core Update',          'update_date': '2024-03-05', 'update_type': 'core',             'severity': 'major', 'description': 'Major update combined with new spam policies'},
        {'update_name': 'November 2023 Core Update',       'update_date': '2023-11-02', 'update_type': 'core',             'severity': 'major', 'description': 'Broad core update focusing on content helpfulness'},
        {'update_name': 'October 2023 Spam Update',        'update_date': '2023-10-04', 'update_type': 'spam',             'severity': 'minor', 'description': 'Targeting scaled content abuse and link spam'},
        {'update_name': 'August 2023 Core Update',         'update_date': '2023-08-22', 'update_type': 'core',             'severity': 'major', 'description': 'Broad core algorithm update'},
    ]

    for u in updates:
        update = AlgorithmUpdate(
            update_name=u['update_name'],
            update_date=dt.date.fromisoformat(u['update_date']),
            update_type=u['update_type'],
            severity=u['severity'],
            description=u['description']
        )
        db.session.add(update)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


app = create_app()

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_ENV') != 'production'
    )