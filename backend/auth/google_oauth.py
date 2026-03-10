import os
import json
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google_auth_oauthlib.flow import Flow
from flask import current_app


def get_google_auth_url() -> str:
    """Generate Google OAuth authorization URL."""
    flow = _create_flow()
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='select_account'
    )
    return auth_url


def exchange_code_for_tokens(auth_code: str) -> dict:
    """Exchange authorization code for access/refresh tokens and user info."""
    flow = _create_flow()

    # Exchange the code
    flow.fetch_token(code=auth_code)
    credentials = flow.credentials

    # Get user info from Google
    user_info = _get_google_user_info(credentials.token)

    return {
        'access_token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'user_info': user_info
    }


def verify_google_token(token: str) -> dict:
    """Verify a Google ID token and return user info."""
    client_id = current_app.config['GOOGLE_CLIENT_ID']
    idinfo = id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        client_id
    )
    return idinfo


def _create_flow() -> Flow:
    """Create a Google OAuth flow."""
    client_config = {
        "web": {
            "client_id": current_app.config['GOOGLE_CLIENT_ID'],
            "client_secret": current_app.config['GOOGLE_CLIENT_SECRET'],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [current_app.config.get('GOOGLE_AUTH_REDIRECT_URI',
                              f"{os.environ.get('BACKEND_URL', 'http://localhost:5000')}/api/auth/google/callback")]
        }
    }

    redirect_uri = current_app.config.get(
        'GOOGLE_AUTH_REDIRECT_URI',
        f"{os.environ.get('BACKEND_URL', 'http://localhost:5000')}/api/auth/google/callback"
    )

    flow = Flow.from_client_config(
        client_config,
        scopes=current_app.config['GOOGLE_AUTH_SCOPES'],
        redirect_uri=redirect_uri
    )
    return flow


def _get_google_user_info(access_token: str) -> dict:
    """Fetch user profile info using access token."""
    response = requests.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    response.raise_for_status()
    return response.json()
