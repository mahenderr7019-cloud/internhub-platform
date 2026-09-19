from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='student')
    photo = db.Column(db.String(300), nullable=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    school = db.relationship('School', backref='students')
    enrollments = db.relationship('Enrollment', backref='user', cascade='all, delete-orphan')
    certificates = db.relationship('Certificate', backref='user', cascade='all, delete-orphan')

    def get_id(self):
        return str(self.id)


class School(db.Model):
    __tablename__ = 'schools'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=True)
    contact_email = db.Column(db.String(120))
    contact_phone = db.Column(db.String(20))
    monthly_fee = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    approved_students = db.relationship('ApprovedStudent', backref='school', cascade='all, delete-orphan')
    classes = db.relationship('SchoolClass', backref='school', cascade='all, delete-orphan')


class ApprovedStudent(db.Model):
    __tablename__ = 'approved_students'
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    is_registered = db.Column(db.Boolean, default=False)


class Internship(db.Model):
    __tablename__ = 'internships'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    price = db.Column(db.Float, default=0)
    duration = db.Column(db.String(50))
    is_paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    contents = db.relationship('InternshipContent', backref='internship',
                               cascade='all, delete-orphan',
                               order_by='InternshipContent.order')
    enrollments = db.relationship('Enrollment', backref='internship', cascade='all, delete-orphan')
    certificates = db.relationship('Certificate', backref='internship', cascade='all, delete-orphan')


class InternshipContent(db.Model):
    __tablename__ = 'internship_contents'
    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id'), nullable=False)
    type = db.Column(db.String(20))
    title = db.Column(db.String(200), nullable=False)
    video_url = db.Column(db.String(500))
    quiz_data = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)


class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id'), nullable=False)
    payment_status = db.Column(db.String(20), default='free')
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    progress = db.relationship('Progress', backref='enrollment', cascade='all, delete-orphan')


class Progress(db.Model):
    __tablename__ = 'progress'
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'), nullable=False)
    content_id = db.Column(db.Integer, db.ForeignKey('internship_contents.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    score = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SchoolClass(db.Model):
    __tablename__ = 'school_classes'
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    youtube_live_url = db.Column(db.String(500))
    recording_url = db.Column(db.String(500))
    scheduled_time = db.Column(db.String(100))
    is_live = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default='')

    @staticmethod
    def get(key, default=''):
        s = Setting.query.filter_by(key=key).first()
        if s and s.value:
            return s.value
        return default


class Certificate(db.Model):
    __tablename__ = 'certificates'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id'), nullable=False)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'), nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    avg_score = db.Column(db.Float, default=0)
    total_quizzes = db.Column(db.Integer, default=0)
    is_revoked = db.Column(db.Boolean, default=False)
    revoked_reason = db.Column(db.String(300))

    enrollment = db.relationship('Enrollment',
                                 backref=db.backref('certificate', uselist=False))