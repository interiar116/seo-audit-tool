from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    profile_picture = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime(timezone=True))
    gsc_connected = db.Column(db.Boolean, default=False)
    indexing_quota_used = db.Column(db.Integer, default=0)
    indexing_quota_reset_date = db.Column(db.Date)

    # Relationships
    audits = db.relationship('Audit', backref='user', lazy=True, cascade='all, delete-orphan')
    gsc_credentials = db.relationship('GscCredential', backref='user', uselist=False, cascade='all, delete-orphan')
    gsc_data = db.relationship('GscData', backref='user', lazy=True, cascade='all, delete-orphan')
    indexing_submissions = db.relationship('IndexingSubmission', backref='user', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'profile_picture': self.profile_picture,
            'gsc_connected': self.gsc_connected,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class GscCredential(db.Model):
    __tablename__ = 'gsc_credentials'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    gsc_access_token = db.Column(db.Text)
    gsc_refresh_token = db.Column(db.Text)
    gsc_token_expiry = db.Column(db.DateTime(timezone=True))
    indexing_api_key = db.Column(db.Text)  # Encrypted service account JSON
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Audit(db.Model):
    __tablename__ = 'audits'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    url = db.Column(db.Text, nullable=False)

    # ── Keyword inputs ──────────────────────────────────────────────────────
    # Phase 2 uses target_keyword as the unified field.
    # primary_keyword is kept as an alias for backward compatibility.
    target_keyword = db.Column(db.String(255))         # Phase 2 primary field
    primary_keyword = db.Column(db.String(255))         # Legacy alias (keep for old queries)
    secondary_keyword = db.Column(db.String(255))
    lsi_keywords = db.Column(db.Text)
    is_competitive = db.Column(db.Boolean)
    brand_name = db.Column(db.String(255))

    # ── Status & lifecycle ──────────────────────────────────────────────────
    # 'queued' → 'running' → 'completed' | 'failed'
    status = db.Column(db.String(20), default='queued', nullable=False)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))

    # ── Scores ──────────────────────────────────────────────────────────────
    # Phase 2 unified scores
    overall_score = db.Column(db.Integer)
    technical_score = db.Column(db.Integer)
    content_score = db.Column(db.Integer)
    blackhat_risk_score = db.Column(db.Integer)

    # Legacy granular scores (kept for backward compatibility)
    overall_grade = db.Column(db.String(20))
    title_score = db.Column(db.Integer)
    meta_score = db.Column(db.Integer)
    header_score = db.Column(db.Integer)
    keyword_score = db.Column(db.Integer)
    url_checks = db.Column(db.JSON)
    blackhat_grade = db.Column(db.String(20))
    penalty_risk_score = db.Column(db.Integer)
    penalty_confidence = db.Column(db.Integer)

    # ── Full results payload (JSONB) ────────────────────────────────────────
    # Phase 2 stores the complete structured audit report here.
    # Legacy fields below are kept for any existing queries.
    results = db.Column(db.JSON)            # Phase 2 complete report
    audit_data = db.Column(db.JSON)         # Legacy full data
    recommendations = db.Column(db.JSON)    # Legacy recommendations

    def to_dict(self, full=False):
        base = {
            'id': self.id,
            'url': self.url,
            'status': self.status,
            'target_keyword': self.target_keyword or self.primary_keyword,
            'overall_score': self.overall_score,
            'technical_score': self.technical_score,
            'content_score': self.content_score,
            'blackhat_risk_score': self.blackhat_risk_score,
            # Legacy fields
            'overall_grade': self.overall_grade,
            'title_score': self.title_score,
            'meta_score': self.meta_score,
            'header_score': self.header_score,
            'keyword_score': self.keyword_score,
            'blackhat_grade': self.blackhat_grade,
            'penalty_risk_score': self.penalty_risk_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
        if full:
            base['results'] = self.results
            base['audit_data'] = self.audit_data
            base['recommendations'] = self.recommendations
            base['url_checks'] = self.url_checks
            base['secondary_keyword'] = self.secondary_keyword
            base['lsi_keywords'] = self.lsi_keywords
            base['is_competitive'] = self.is_competitive
            base['brand_name'] = self.brand_name
            base['penalty_confidence'] = self.penalty_confidence
            base['error_message'] = self.error_message
        return base


class GscData(db.Model):
    __tablename__ = 'gsc_data'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    url = db.Column(db.Text, nullable=False)
    date = db.Column(db.Date, nullable=False)

    # Performance
    clicks = db.Column(db.Integer)
    impressions = db.Column(db.Integer)
    ctr = db.Column(db.Numeric(5, 4))
    position = db.Column(db.Numeric(5, 2))

    # Index coverage
    indexed_pages = db.Column(db.Integer)
    excluded_pages = db.Column(db.Integer)
    crawl_rate = db.Column(db.Integer)

    # Issues (JSON)
    manual_actions = db.Column(db.JSON)
    coverage_issues = db.Column(db.JSON)
    mobile_issues = db.Column(db.JSON)
    core_web_vitals = db.Column(db.JSON)

    data_source = db.Column(db.String(50), default='api')
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'url', 'date', name='uq_gsc_data'),
    )


class AlgorithmUpdate(db.Model):
    __tablename__ = 'algorithm_updates'

    id = db.Column(db.Integer, primary_key=True)
    update_name = db.Column(db.String(255), nullable=False)
    update_date = db.Column(db.Date, nullable=False)
    update_type = db.Column(db.String(50))  # core, spam, helpful-content, product-reviews
    description = db.Column(db.Text)
    source_url = db.Column(db.Text)
    severity = db.Column(db.String(20))  # major, minor
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class IndexingSubmission(db.Model):
    __tablename__ = 'indexing_submissions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    url = db.Column(db.Text, nullable=False)
    page_type = db.Column(db.String(50))  # general, job_posting, livestream, news
    method = db.Column(db.String(50))     # indexing_api, gsc_inspection
    status = db.Column(db.String(50), default='submitted')  # submitted, indexed, failed
    response_data = db.Column(db.JSON)
    submitted_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    indexed_at = db.Column(db.DateTime(timezone=True))

    def to_dict(self):
        return {
            'id': self.id,
            'url': self.url,
            'page_type': self.page_type,
            'method': self.method,
            'status': self.status,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'indexed_at': self.indexed_at.isoformat() if self.indexed_at else None
        }