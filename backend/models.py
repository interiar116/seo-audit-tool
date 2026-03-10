from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    profile_picture = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
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
    gsc_token_expiry = db.Column(db.DateTime)
    indexing_api_key = db.Column(db.Text)  # Encrypted service account JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Audit(db.Model):
    __tablename__ = 'audits'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    url = db.Column(db.Text, nullable=False)
    primary_keyword = db.Column(db.String(255))
    secondary_keyword = db.Column(db.String(255))
    lsi_keywords = db.Column(db.Text)
    is_competitive = db.Column(db.Boolean)
    brand_name = db.Column(db.String(255))

    # Scores
    overall_score = db.Column(db.Integer)
    overall_grade = db.Column(db.String(20))
    title_score = db.Column(db.Integer)
    meta_score = db.Column(db.Integer)
    header_score = db.Column(db.Integer)
    keyword_score = db.Column(db.Integer)
    url_checks = db.Column(db.JSON)
    blackhat_risk_score = db.Column(db.Integer)
    blackhat_grade = db.Column(db.String(20))
    penalty_risk_score = db.Column(db.Integer)
    penalty_confidence = db.Column(db.Integer)

    # Full data (JSONB)
    audit_data = db.Column(db.JSON)
    recommendations = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, full=False):
        base = {
            'id': self.id,
            'url': self.url,
            'primary_keyword': self.primary_keyword,
            'overall_score': self.overall_score,
            'overall_grade': self.overall_grade,
            'title_score': self.title_score,
            'meta_score': self.meta_score,
            'header_score': self.header_score,
            'keyword_score': self.keyword_score,
            'blackhat_risk_score': self.blackhat_risk_score,
            'blackhat_grade': self.blackhat_grade,
            'penalty_risk_score': self.penalty_risk_score,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if full:
            base['audit_data'] = self.audit_data
            base['recommendations'] = self.recommendations
            base['url_checks'] = self.url_checks
            base['secondary_keyword'] = self.secondary_keyword
            base['lsi_keywords'] = self.lsi_keywords
            base['is_competitive'] = self.is_competitive
            base['brand_name'] = self.brand_name
            base['penalty_confidence'] = self.penalty_confidence
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class IndexingSubmission(db.Model):
    __tablename__ = 'indexing_submissions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    url = db.Column(db.Text, nullable=False)
    page_type = db.Column(db.String(50))  # general, job_posting, livestream, news
    method = db.Column(db.String(50))  # indexing_api, gsc_inspection
    status = db.Column(db.String(50), default='submitted')  # submitted, indexed, failed
    response_data = db.Column(db.JSON)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    indexed_at = db.Column(db.DateTime)

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
