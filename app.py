import os
import jwt
import datetime
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, make_response, url_for
from models import db, User, StudentProfile, CompanyProfile, PlacementDrive, Application
from werkzeug.security import generate_password_hash, check_password_hash


load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
db.init_app(app)

with app.app_context():
    db.create_all()


#JWT Decorator to protect routes
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('token')
        if not token: return redirect('/')
        try:
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
        except: return redirect('/')
        return f(current_user, *args, **kwargs)
    return decorated


# Create Database for default Admin
with app.app_context():
    db.create_all()
    
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    
    if not User.query.filter_by(role="admin").first():
        admin = User(
            name="System Admin", 
            email=admin_email, 
            password_hash=generate_password_hash(admin_password), 
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()


#Authenticate 
def create_jwt_response(user, target_url):
    token = jwt.encode({'user_id': user.user_id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)}, app.config["SECRET_KEY"])
    resp = make_response(redirect(target_url))
    resp.set_cookie('token', token, httponly=True)
    return resp

@app.route('/login_action', methods=['POST'])
def login_action():
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role') # Passed from hidden input in HTML
    
    user = User.query.filter_by(email=email, role=role).first()
    if user and check_password_hash(user.password_hash, password):
        if role == "company" and user.company_profile.approval_status != "Approved":
            return "Company account pending admin approval."
        
        dashboard = f"/{role}_dashboard"
        return create_jwt_response(user, dashboard)
    return "Invalid Credentials"


@app.route('/')
def home():
    return render_template("index.html")



@app.route('/student_register', methods=['GET', 'POST'])
def student_register():

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role="student"
        )

        db.session.add(user)
        db.session.commit()

        student = StudentProfile(
            user_id=user.user_id
        )

        db.session.add(student)
        db.session.commit()

        return redirect('/student_login')

    return render_template("student_register.html")


@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email, role="student").first()
        
        if user and check_password_hash(user.password_hash, password):
            return create_jwt_response(user, '/student_dashboard')
        return "Invalid Student Credentials"
    return render_template("student_login.html")


@app.route('/student_dashboard')
@token_required
def student_dashboard(current_user):
    if current_user.role != 'student': return redirect('/')
    
    # Students should see approved drives they can apply to
    available_drives = PlacementDrive.query.filter_by(status="Approved").all()
    my_applications = Application.query.filter_by(student_id=current_user.student_profile.student_id).all()
    
    return render_template("student_dashboard.html", student=current_user, drives=available_drives, applications=my_applications)


@app.route('/company_register', methods=['GET', 'POST'])
def company_register():
    if request.method == 'POST':
        name = request.form['name']
        website = request.form['website']
        hr = request.form['hr']
        email = request.form['email']
        password = request.form['password']

        user = User(
            name=name, email=email,
            password_hash=generate_password_hash(password),
            role="company"
        )
        db.session.add(user)
        db.session.commit()

        company = CompanyProfile(
            user_id=user.user_id,
            company_name=name,
            website=website,
            hr_contact=hr,
            approval_status="Pending"
        )
        db.session.add(company)
        db.session.commit()
        return redirect('/company_login') 
    return render_template("company_register.html")


@app.route('/company_login', methods=['GET', 'POST'])
def company_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email, role="company").first()
        
        if user and check_password_hash(user.password_hash, password):
            if user.company_profile.approval_status != "Approved":
                return "Account pending admin approval."
            return create_jwt_response(user, '/company_dashboard')
        return "Invalid Company Credentials"
    return render_template("company_login.html")


@app.route('/company_dashboard')
@token_required
def company_dashboard(current_user):
    if current_user.role != 'company': return redirect('/')
    return render_template("company_dashboard.html", company=current_user)


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email, role="admin").first()
        
        if user and check_password_hash(user.password_hash, password):
            return create_jwt_response(user, '/admin_dashboard')
        return "Invalid Admin Credentials"
    return render_template("admin_login.html")


@app.route('/admin_dashboard')
@token_required
def admin_dashboard(current_user):
    if current_user.role != 'admin': return redirect('/')
    
    # Fetch real data for your dashboard cards
    stats = {
        'total_students': StudentProfile.query.count(),
        'total_companies': CompanyProfile.query.count(),
        'total_drives': PlacementDrive.query.count(),
        'total_apps': Application.query.count()
    }
    pending_companies = CompanyProfile.query.filter_by(approval_status="Pending").all()
    
    return render_template("admin_dashboard.html", admin=current_user, stats=stats, pending_companies=pending_companies)


@app.route('/logout')
def logout():
    resp = make_response(redirect('/'))
    resp.set_cookie('token', '', expires=0)
    return resp


if __name__ == "__main__":
    app.run(debug=True)