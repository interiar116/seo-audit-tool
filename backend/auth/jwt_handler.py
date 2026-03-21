import jwt
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify, current_app


def generate_token(user_id: int) -> str:
    """Generate a JWT token for a user."""
    expiry_hours = int(os.environ.get('JWT_EXPIRY_HOURS', 24))
    payload = {
        'user_id': user_id,
        'exp': datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    return jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])


def require_auth(f):
    """
    Decorator to protect routes requiring authentication.
    Fetches the User from DB and passes it as the first argument (current_user).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Check Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        # Cookie fallback
        if not token:
            token = request.cookies.get('auth_token')

        if not token:
            return jsonify({
                'status': 'error',
                'error': {
                    'code': 'UNAUTHORIZED',
                    'message': 'Authentication required'
                }
            }), 401

        try:
            payload = decode_token(token)
            user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({
                'status': 'error',
                'error': {
                    'code': 'TOKEN_EXPIRED',
                    'message': 'Session expired, please sign in again'
                }
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'status': 'error',
                'error': {
                    'code': 'INVALID_TOKEN',
                    'message': 'Invalid authentication token'
                }
            }), 401

        # Fetch user from DB and pass as current_user
        from models import User
        current_user = User.query.get(user_id)
        if not current_user:
            return jsonify({
                'status': 'error',
                'error': {
                    'code': 'USER_NOT_FOUND',
                    'message': 'User account not found'
                }
            }), 401

        # Make user_id available on request object as well (convenience)
        request.user_id = user_id
        request.current_user = current_user

        return f(current_user, *args, **kwargs)
    return decorated