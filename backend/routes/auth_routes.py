from flask import Blueprint, jsonify, redirect, request, current_app
from datetime import datetime
from models import db, User
from auth.jwt_handler import generate_token, require_auth
from auth.google_oauth import get_google_auth_url, exchange_code_for_tokens

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/google', methods=['GET'])
def google_login():
    """Redirect user to Google OAuth consent screen."""
    try:
        auth_url = get_google_auth_url()
        return jsonify({
            'status': 'success',
            'data': {'auth_url': auth_url}
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': {'code': 'AUTH_ERROR', 'message': str(e)}
        }), 500


@auth_bp.route('/google/callback', methods=['GET'])
def google_callback():
    """Handle Google OAuth callback."""
    code = request.args.get('code')
    error = request.args.get('error')

    frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:3000')

    if error:
        return redirect(f"{frontend_url}/login?error=access_denied")

    if not code:
        return redirect(f"{frontend_url}/login?error=missing_code")

    try:
        # Exchange code for tokens + user info
        result = exchange_code_for_tokens(code)
        user_info = result['user_info']

        # Find or create user
        user = User.query.filter_by(google_id=user_info['id']).first()

        if not user:
            user = User(
                google_id=user_info['id'],
                email=user_info['email'],
                name=user_info.get('name', ''),
                profile_picture=user_info.get('picture', '')
            )
            db.session.add(user)

        user.last_login = datetime.utcnow()
        if user_info.get('picture'):
            user.profile_picture = user_info['picture']
        if user_info.get('name'):
            user.name = user_info['name']

        db.session.commit()

        # Generate JWT
        token = generate_token(user.id)

        # Redirect to frontend with token
        return redirect(f"{frontend_url}/dashboard?token={token}")

    except Exception as e:
        current_app.logger.error(f"OAuth callback error: {e}")
        return redirect(f"{frontend_url}/login?error=auth_failed")


@auth_bp.route('/user', methods=['GET'])
@require_auth
def get_current_user():
    """Get currently authenticated user."""
    user = User.query.get(request.user_id)

    if not user:
        return jsonify({
            'status': 'error',
            'error': {'code': 'NOT_FOUND', 'message': 'User not found'}
        }), 404

    return jsonify({
        'status': 'success',
        'data': user.to_dict()
    })


@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """Logout user (client should clear token)."""
    return jsonify({
        'status': 'success',
        'message': 'Logged out successfully'
    })
