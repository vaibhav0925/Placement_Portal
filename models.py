from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# -------------------------
# USER TABLE
# -------------------------
class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    # roles: admin / student / company
    role = db.Column(db.String(20), nullable=False)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student_profile = db.relationship("StudentProfile", backref="user", uselist=False)
    company_profile = db.relationship("CompanyProfile", backref="user", uselist=False)


# -------------------------
# STUDENT PROFILE
# -------------------------
class StudentProfile(db.Model):
    __tablename__ = "student_profiles"

    student_id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        nullable=False
    )

    roll_number = db.Column(db.String(50), unique=True)
    branch = db.Column(db.String(100))
    graduation_year = db.Column(db.Integer)
    cgpa = db.Column(db.Float)

    phone = db.Column(db.String(15))
    resume = db.Column(db.String(200))
    skills = db.Column(db.Text)

    is_blacklisted = db.Column(db.Boolean, default=False)

    applications = db.relationship("Application", backref="student", lazy=True)


# -------------------------
# COMPANY PROFILE
# -------------------------
class CompanyProfile(db.Model):
    __tablename__ = "company_profiles"

    company_id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        nullable=False
    )

    company_name = db.Column(db.String(150), nullable=False)
    hr_contact = db.Column(db.String(100))
    website = db.Column(db.String(200))
    description = db.Column(db.Text)

    # Pending / Approved / Rejected
    approval_status = db.Column(db.String(20), default="Pending")

    is_blacklisted = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    drives = db.relationship("PlacementDrive", backref="company", lazy=True)


# -------------------------
# PLACEMENT DRIVE
# -------------------------
class PlacementDrive(db.Model):
    __tablename__ = "placement_drives"

    drive_id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("company_profiles.company_id"),
        nullable=False
    )

    #company = db.relationship('CompanyProfile', backref=db.backref('drives', lazy=True))

    job_title = db.Column(db.String(200), nullable=False)
    job_description = db.Column(db.Text)

    eligibility_criteria = db.Column(db.Text)

    location = db.Column(db.String(100))
    salary_package = db.Column(db.Float)

    application_deadline = db.Column(db.Date)
    drive_date = db.Column(db.Date)

    # Pending / Approved / Closed
    status = db.Column(db.String(20), default="Pending")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship("Application", backref="drive", lazy=True)


# -------------------------
# APPLICATION TABLE
# -------------------------
class Application(db.Model):
    __tablename__ = "applications"

    application_id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("student_profiles.student_id"),
        nullable=False
    )

    drive_id = db.Column(
        db.Integer,
        db.ForeignKey("placement_drives.drive_id"),
        nullable=False
    )

    application_date = db.Column(db.DateTime, default=datetime.utcnow)

    # Applied / Shortlisted / Selected / Rejected
    status = db.Column(db.String(20), default="Applied")

    remarks = db.Column(db.Text)


# -------------------------
# ADMIN ACTION LOGS
# -------------------------
class AdminLog(db.Model):
    __tablename__ = "admin_logs"

    log_id = db.Column(db.Integer, primary_key=True)

    admin_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        nullable=False
    )

    action = db.Column(db.String(200))
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)