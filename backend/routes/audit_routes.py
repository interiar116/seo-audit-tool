"""
Audit Routes
Endpoints for starting audits, checking status, and retrieving results.
All audit endpoints require JWT authentication.
"""

from flask import Blueprint, request, jsonify
from auth.jwt_handler import require_auth
from models import db, Audit
from datetime import datetime, timezone, timedelta
import logging
import re

logger = logging.getLogger(__name__)

audit_bp = Blueprint("audit", __name__)


def _validate_url(url: str) -> tuple:
    """Basic URL validation. Returns (is_valid, error_or_normalized_url)."""
    if not url:
        return False, "URL is required"
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    if not pattern.match(url):
        return False, "Invalid URL format"
    blocked = ["localhost", "127.0.0.1", "0.0.0.0", "192.168.", "10.", "172.16."]
    if any(b in url for b in blocked):
        return False, "Auditing internal/private URLs is not permitted"
    return True, url


def _check_daily_limit(user_id: int) -> tuple:
    """
    Check if user has exceeded daily audit limit (1 per day).
    Returns (allowed: bool, next_available_at: datetime or None)
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=24)

    last_audit = Audit.query.filter(
        Audit.user_id == user_id,
        Audit.created_at >= window_start,
        Audit.status.in_(['queued', 'running', 'completed'])
    ).order_by(Audit.created_at.desc()).first()

    if not last_audit:
        return True, None

    next_available = last_audit.created_at + timedelta(hours=24)
    return False, next_available


@audit_bp.route("/start", methods=["POST"])
@require_auth
def start_audit(current_user):
    """
    Start a new SEO audit.
    Body: { "url": str, "target_keyword": str (optional), "run_cloaking_check": bool }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    raw_url = data.get("url", "").strip()
    target_keyword = data.get("target_keyword", "").strip() or None
    run_cloaking = data.get("run_cloaking_check", True)

    is_valid, result = _validate_url(raw_url)
    if not is_valid:
        return jsonify({"error": result}), 400

    url = result

    # Check daily limit — 1 audit per 24 hours
    allowed, next_available = _check_daily_limit(current_user.id)
    if not allowed:
        return jsonify({
            "error": "Daily audit limit reached",
            "code": "DAILY_LIMIT_REACHED",
            "next_available_at": next_available.isoformat()
        }), 429

    # Prevent duplicate running audits
    existing = Audit.query.filter_by(
        user_id=current_user.id, url=url, status="running"
    ).first()
    if existing:
        return jsonify({
            "error": "An audit for this URL is already running",
            "audit_id": existing.id,
            "status": "running"
        }), 409

    # Create audit record
    audit = Audit(
        user_id=current_user.id,
        url=url,
        target_keyword=target_keyword,
        status="queued",
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(audit)
    db.session.commit()

    # Start background audit thread
    from audit.audit_engine import run_audit
    from flask import current_app
    app = current_app._get_current_object()

    run_audit(
        audit_id=audit.id,
        url=url,
        target_keyword=target_keyword,
        run_cloaking_check=run_cloaking,
        app=app
    )

    logger.info(f"Audit {audit.id} queued: {url}")

    return jsonify({
        "audit_id": audit.id,
        "status": "queued",
        "url": url,
        "message": "Audit started. Poll /api/audit/status/{id} for updates."
    }), 202


@audit_bp.route("/status/<int:audit_id>", methods=["GET"])
@require_auth
def get_audit_status(current_user, audit_id):
    """Poll audit progress. Frontend calls this every 3-5 seconds."""
    audit = Audit.query.filter_by(id=audit_id, user_id=current_user.id).first()
    if not audit:
        return jsonify({"error": "Audit not found"}), 404

    response = {
        "audit_id": audit.id,
        "status": audit.status,
        "url": audit.url,
        "created_at": audit.created_at.isoformat() if audit.created_at else None,
        "started_at": audit.started_at.isoformat() if audit.started_at else None,
        "completed_at": audit.completed_at.isoformat() if audit.completed_at else None,
    }

    if audit.status == "failed":
        response["error_message"] = audit.error_message

    if audit.status == "completed" and audit.results:
        response["scores"] = audit.results.get("scores", {})
        response["summary"] = audit.results.get("summary", {})

    return jsonify(response), 200


@audit_bp.route("/results/<int:audit_id>", methods=["GET"])
@require_auth
def get_audit_results(current_user, audit_id):
    """Get full audit results."""
    audit = Audit.query.filter_by(id=audit_id, user_id=current_user.id).first()
    if not audit:
        return jsonify({"error": "Audit not found"}), 404

    if audit.status != "completed":
        return jsonify({"error": "Audit not yet completed", "status": audit.status}), 400

    if not audit.results:
        return jsonify({"error": "Audit results not found"}), 500

    section = request.args.get("section", "all")

    if section == "all":
        return jsonify(audit.results), 200

    valid_sections = ["technical", "content", "blackhat", "meta", "scores",
                      "summary", "page_info", "recovery_priority"]
    if section in valid_sections:
        data = audit.results.get(section)
        if data is None:
            return jsonify({"error": f"Section '{section}' not found"}), 404
        return jsonify({section: data}), 200

    return jsonify({"error": f"Invalid section. Valid: {', '.join(valid_sections)}"}), 400


@audit_bp.route("/history", methods=["GET"])
@require_auth
def get_audit_history(current_user):
    """Get user's audit history with pagination."""
    try:
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 20)), 100)
        limit = min(int(request.args.get("limit", per_page)), 100)
        offset = int(request.args.get("offset", (page - 1) * limit))
    except ValueError:
        return jsonify({"error": "Invalid pagination parameters"}), 400

    audits = Audit.query.filter_by(user_id=current_user.id)\
        .order_by(Audit.created_at.desc())\
        .limit(limit).offset(offset).all()

    total = Audit.query.filter_by(user_id=current_user.id).count()

    # Check daily limit to include in response
    allowed, next_available = _check_daily_limit(current_user.id)

    return jsonify({
        "audits": [
            {
                "audit_id": a.id,
                "url": a.url,
                "status": a.status,
                "overall_score": a.overall_score,
                "technical_score": a.technical_score,
                "content_score": a.content_score,
                "blackhat_risk_score": a.blackhat_risk_score,
                "primary_keyword": a.target_keyword or a.primary_keyword,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in audits
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "daily_limit": {
            "allowed": allowed,
            "next_available_at": next_available.isoformat() if next_available else None
        }
    }), 200


@audit_bp.route("/limit", methods=["GET"])
@require_auth
def get_limit_status(current_user):
    """Check if user can run an audit right now."""
    allowed, next_available = _check_daily_limit(current_user.id)
    return jsonify({
        "allowed": allowed,
        "next_available_at": next_available.isoformat() if next_available else None
    }), 200


@audit_bp.route("/<int:audit_id>", methods=["DELETE"])
@require_auth
def delete_audit(current_user, audit_id):
    """Delete an audit record."""
    audit = Audit.query.filter_by(id=audit_id, user_id=current_user.id).first()
    if not audit:
        return jsonify({"error": "Audit not found"}), 404
    if audit.status == "running":
        return jsonify({"error": "Cannot delete a running audit"}), 409

    db.session.delete(audit)
    db.session.commit()
    return jsonify({"message": f"Audit {audit_id} deleted"}), 200