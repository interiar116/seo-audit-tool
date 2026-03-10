import jwt
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app


def generate_token(user_id: int) -> str:
    """Generate a JWT token for a user."""
    expiry_hours = int(os.environ.get('JWT_EXPIRY_HOURS', 24))
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=expiry_hours),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    return jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])


def require_auth(f):
    """Decorator to protect routes requiring authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Check Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        # Also check cookie as fallback
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
            request.user_id = payload['user_id']
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

        return f(*args, **kwargs)
    return decorated
