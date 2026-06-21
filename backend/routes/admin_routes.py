"""
Admin Routes
Platform-wide data endpoints for admin users only.
All routes require JWT auth + admin email verification.
"""

import os
import io
import csv
import logging
from functools import wraps
from datetime import date
from flask import Blueprint, request, jsonify, Response
from sqlalchemy import func, or_

from auth.jwt_handler import require_auth
from models import db, User, Audit, AlgorithmUpdate

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

ADMIN_EMAILS = set(os.getenv('ADMIN_EMAILS', 'innovativeideas116@gmail.com').split(','))


def require_admin(f):
    """Decorator: JWT auth + admin email check."""
    @wraps(f)
    def check_admin(current_user, *args, **kwargs):
        if current_user.email not in ADMIN_EMAILS:
            return jsonify({'error': 'Forbidden'}), 403
        return f(current_user, *args, **kwargs)
    return require_auth(check_admin)


# ── Stats ────────────────────────────────────────────────────────────────────

@admin_bp.route('/stats', methods=['GET'])
@require_admin
def get_stats(current_user):
    total_users = User.query.count()
    total_audits = Audit.query.filter(Audit.is_competitive != True).count()
    avg_result = db.session.query(func.avg(Audit.overall_score)).filter(
        Audit.status == 'completed',
        Audit.is_competitive != True,
        Audit.overall_score.isnot(None)
    ).scalar()
    avg_score = round(float(avg_result), 1) if avg_result else 0
    gsc_connected = User.query.filter_by(gsc_connected=True).count()
    running_now = Audit.query.filter_by(status='running').count()

    # Score distribution across completed audits
    scores = db.session.query(Audit.overall_score).filter(
        Audit.status == 'completed',
        Audit.is_competitive != True,
    ).all()
    dist = {'good': 0, 'medium': 0, 'bad': 0, 'unscored': 0}
    for (s,) in scores:
        if s is None:
            dist['unscored'] += 1
        elif s >= 70:
            dist['good'] += 1
        elif s >= 40:
            dist['medium'] += 1
        else:
            dist['bad'] += 1
    dist['total'] = sum(dist.values())

    # Audit status breakdown
    status_counts = db.session.query(
        Audit.status, func.count(Audit.id)
    ).group_by(Audit.status).all()
    status_breakdown = {s: c for s, c in status_counts}

    return jsonify({
        'users': total_users,
        'audits': total_audits,
        'avg_score': avg_score,
        'gsc_connected': gsc_connected,
        'running': running_now,
        'score_distribution': dist,
        'status_breakdown': status_breakdown,
    }), 200


# ── Recent Activity ───────────────────────────────────────────────────────────

@admin_bp.route('/recent-activity', methods=['GET'])
@require_admin
def get_recent_activity(current_user):
    rows = db.session.query(Audit, User).join(User, Audit.user_id == User.id)\
        .filter(Audit.status == 'completed')\
        .order_by(Audit.completed_at.desc()).limit(10).all()

    return jsonify({
        'activity': [{
            'audit_id': a.id,
            'url': a.url,
            'user_email': u.email,
            'user_name': u.name,
            'overall_score': a.overall_score,
            'is_competitive': bool(a.is_competitive),
            'completed_at': a.completed_at.isoformat() if a.completed_at else None,
        } for a, u in rows]
    }), 200


# ── Users ─────────────────────────────────────────────────────────────────────

@admin_bp.route('/users', methods=['GET'])
@require_admin
def get_users(current_user):
    users = User.query.order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        audit_count = Audit.query.filter(
            Audit.user_id == u.id,
            Audit.is_competitive != True
        ).count()
        result.append({
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'profile_picture': u.profile_picture,
            'created_at': u.created_at.isoformat() if u.created_at else None,
            'last_login': u.last_login.isoformat() if u.last_login else None,
            'gsc_connected': bool(u.gsc_connected),
            'audit_count': audit_count,
        })
    return jsonify({'users': result}), 200


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@require_admin
def delete_user(current_user, user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if user.email in ADMIN_EMAILS:
        return jsonify({'error': 'Cannot delete an admin account'}), 403

    # Delete all user data explicitly before removing the user record
    Audit.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': f'User {user_id} and all their data deleted'}), 200


@admin_bp.route('/users/<int:user_id>/audits', methods=['GET'])
@require_admin
def get_user_audits(current_user, user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    audits = Audit.query.filter_by(user_id=user_id)\
        .order_by(Audit.created_at.desc()).limit(10).all()

    return jsonify({
        'audits': [{
            'audit_id': a.id,
            'url': a.url,
            'status': a.status,
            'overall_score': a.overall_score,
            'technical_score': a.technical_score,
            'content_score': a.content_score,
            'blackhat_risk_score': a.blackhat_risk_score,
            'is_competitive': bool(a.is_competitive),
            'created_at': a.created_at.isoformat() if a.created_at else None,
        } for a in audits]
    }), 200


# ── All Audits ────────────────────────────────────────────────────────────────

@admin_bp.route('/audits/export', methods=['GET'])
@require_admin
def export_audits(current_user):
    """Download all audits as CSV."""
    rows = db.session.query(Audit, User).join(User, Audit.user_id == User.id)\
        .order_by(Audit.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'audit_id', 'url', 'user_email', 'user_name',
        'overall_score', 'technical_score', 'content_score', 'blackhat_risk_score',
        'status', 'is_competitive', 'target_keyword', 'created_at', 'completed_at',
    ])
    for a, u in rows:
        writer.writerow([
            a.id, a.url, u.email, u.name or '',
            a.overall_score, a.technical_score, a.content_score, a.blackhat_risk_score,
            a.status, bool(a.is_competitive), a.target_keyword or '',
            a.created_at.isoformat() if a.created_at else '',
            a.completed_at.isoformat() if a.completed_at else '',
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=audits-export.csv'},
    )


@admin_bp.route('/audits/<int:audit_id>', methods=['DELETE'])
@require_admin
def delete_audit(current_user, audit_id):
    audit = Audit.query.get(audit_id)
    if not audit:
        return jsonify({'error': 'Audit not found'}), 404
    if audit.status == 'running':
        return jsonify({'error': 'Cannot delete a running audit'}), 409
    db.session.delete(audit)
    db.session.commit()
    return jsonify({'message': f'Audit {audit_id} deleted'}), 200


@admin_bp.route('/audits', methods=['GET'])
@require_admin
def get_all_audits(current_user):
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 25)), 100)
    except ValueError:
        return jsonify({'error': 'Invalid pagination parameters'}), 400

    status_filter = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()

    query = db.session.query(Audit, User).join(User, Audit.user_id == User.id)

    if status_filter:
        query = query.filter(Audit.status == status_filter)

    if search:
        query = query.filter(
            or_(
                Audit.url.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                User.name.ilike(f'%{search}%'),
            )
        )

    total = query.count()
    offset = (page - 1) * per_page
    rows = query.order_by(Audit.created_at.desc()).limit(per_page).offset(offset).all()

    audits = [{
        'audit_id': a.id,
        'url': a.url,
        'user_email': u.email,
        'user_name': u.name,
        'overall_score': a.overall_score,
        'technical_score': a.technical_score,
        'content_score': a.content_score,
        'blackhat_risk_score': a.blackhat_risk_score,
        'is_competitive': bool(a.is_competitive),
        'status': a.status,
        'created_at': a.created_at.isoformat() if a.created_at else None,
    } for a, u in rows]

    return jsonify({
        'audits': audits,
        'total': total,
        'page': page,
        'per_page': per_page,
    }), 200


# ── Algorithm Updates ─────────────────────────────────────────────────────────

@admin_bp.route('/algorithm-updates', methods=['GET'])
@require_admin
def get_algorithm_updates(current_user):
    updates = AlgorithmUpdate.query.order_by(AlgorithmUpdate.update_date.desc()).all()
    return jsonify({
        'updates': [{
            'id': u.id,
            'update_name': u.update_name,
            'update_date': u.update_date.isoformat() if u.update_date else None,
            'update_type': u.update_type,
            'severity': u.severity,
            'description': u.description,
            'source_url': u.source_url,
            'created_at': u.created_at.isoformat() if u.created_at else None,
        } for u in updates]
    }), 200


@admin_bp.route('/algorithm-updates', methods=['POST'])
@require_admin
def create_algorithm_update(current_user):
    data = request.get_json()
    if not data or not data.get('update_name') or not data.get('update_date'):
        return jsonify({'error': 'update_name and update_date are required'}), 400

    try:
        update_date = date.fromisoformat(data['update_date'])
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    update = AlgorithmUpdate(
        update_name=data['update_name'].strip(),
        update_date=update_date,
        update_type=data.get('update_type') or None,
        severity=data.get('severity') or None,
        description=data.get('description') or None,
        source_url=data.get('source_url') or None,
    )
    db.session.add(update)
    db.session.commit()

    return jsonify({
        'update': {
            'id': update.id,
            'update_name': update.update_name,
            'update_date': update.update_date.isoformat(),
            'update_type': update.update_type,
            'severity': update.severity,
            'description': update.description,
            'source_url': update.source_url,
        }
    }), 201


@admin_bp.route('/algorithm-updates/<int:update_id>', methods=['DELETE'])
@require_admin
def delete_algorithm_update(current_user, update_id):
    update = AlgorithmUpdate.query.get(update_id)
    if not update:
        return jsonify({'error': 'Algorithm update not found'}), 404
    db.session.delete(update)
    db.session.commit()
    return jsonify({'message': f'Algorithm update {update_id} deleted'}), 200
