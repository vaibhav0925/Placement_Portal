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
        expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
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

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "Email already registered. Please log in."

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role="student"
        )
        db.session.add(user)
        db.session.commit() # Save user to get user.user_id

        student_count = StudentProfile.query.count()
        new_roll = f"IITM-{str(student_count + 1).zfill(3)}"

        student = StudentProfile(
            user_id=user.user_id,
            roll_number=new_roll
        )

        db.session.add(student)
        db.session.commit() # Final save

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

        if user.role == "student":
            profile = StudentProfile.query.filter_by(user_id=user.user_id).first()
        if profile.is_blacklisted:
            return "Your account has been blacklisted. Contact Admin on email iitm_admin@portal.com."
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
        name = request.form['company_name']
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

    drives = PlacementDrive.query.filter_by(company_id=current_user.company_profile.company_id).all()

    return render_template("company_dashboard.html", company=current_user, drives=drives)



@app.route('/create_drive', methods=['GET', 'POST'])
@token_required
def create_drive(current_user):
    if current_user.role != 'company': return redirect('/')

    if request.method == 'POST':
        # 1. Collect form data
        job_title = request.form.get('job_title')
        salary = request.form.get('salary')
        location = request.form.get('location')
        deadline_str = request.form.get('deadline')
        drive_date_str = request.form.get('drive_date')
        eligibility = request.form.get('eligibility')
        description = request.form.get('description')

        # 2. Convert date strings to Python date objects
        deadline = datetime.datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None
        drive_date = datetime.datetime.strptime(drive_date_str, '%Y-%m-%d').date() if drive_date_str else None

        # 3. Create and Save to DB
        new_drive = PlacementDrive(
            company_id=current_user.company_profile.company_id,
            job_title=job_title,
            job_description=description,
            eligibility_criteria=eligibility,
            location=location,
            salary_package=float(salary) if salary else 0.0,
            application_deadline=deadline,
            drive_date=drive_date,
            status="Pending"  # This ensures it hits the Admin's "Pending" table
        )

        db.session.add(new_drive)
        db.session.commit()

        return redirect('/company_dashboard')

    return render_template("create_drive.html")


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
    
    
    stats = {
        'total_students': StudentProfile.query.count(),
        'total_companies': CompanyProfile.query.count(),
        'total_drives': PlacementDrive.query.count(),
        'total_apps': Application.query.count()
    }
    pending_companies = CompanyProfile.query.filter_by(approval_status="Pending").all()

    pending_drives = PlacementDrive.query.filter_by(status="Pending").all()
    
    return render_template("admin_dashboard.html", admin=current_user, stats=stats, pending_companies=pending_companies, pending_drives=pending_drives)


@app.route('/admin/approve_company/<int:id>')
@token_required
def approve_company(current_user, id):
    if current_user.role != 'admin': return redirect('/')
    company = CompanyProfile.query.get_or_404(id)
    company.approval_status = "Approved"
    db.session.commit()
    return redirect('/admin_dashboard')

@app.route('/admin/approve_drive/<int:id>')
@token_required
def approve_drive(current_user, id):
    if current_user.role != 'admin': return redirect('/')
    drive = PlacementDrive.query.get_or_404(id)
    drive.status = "Approved"
    db.session.commit()
    return redirect('/admin_dashboard')

# --- BLACKLISTING ---

@app.route('/admin/blacklist_student/<int:id>')
@token_required
def blacklist_student(current_user, id):
    if current_user.role != 'admin': return redirect('/')
    student = StudentProfile.query.get_or_404(id)
    student.is_blacklisted = not student.is_blacklisted  # Toggles blacklist
    db.session.commit()
    return redirect('/admin_dashboard')


@app.route('/admin/manage_students')
@token_required
def manage_students(current_user):
    if current_user.role != 'admin': return redirect('/')
    search_query = request.args.get('search', '')
    
    # Search by Name (via User join), Email, or Roll Number
    students = db.session.query(StudentProfile).join(User).filter(
        (User.name.ilike(f'%{search_query}%')) | 
        (User.email.ilike(f'%{search_query}%')) |
        (StudentProfile.roll_number.ilike(f'%{search_query}%'))
    ).all()
    
    return render_template("admin_students.html", students=students)

@app.route('/admin/reject_company/<int:id>')
@token_required
def reject_company(current_user, id):
    if current_user.role != 'admin': return redirect('/')
    company = CompanyProfile.query.get_or_404(id)
    company.approval_status = "Rejected"
    db.session.commit()
    return redirect('/admin_dashboard')

@app.route('/admin/blacklist_company/<int:id>')
@token_required
def blacklist_company(current_user, id):
    if current_user.role != 'admin': return redirect('/')
    company = CompanyProfile.query.get_or_404(id)
    company.is_blacklisted = not company.is_blacklisted # Toggle
    db.session.commit()
    return redirect('/admin/manage_companies')


@app.route('/admin/reject_drive/<int:id>')
@token_required
def reject_drive(current_user, id):
    if current_user.role != 'admin': 
        return redirect('/')
    
    drive = PlacementDrive.query.get_or_404(id)
    drive.status = "Rejected"
    db.session.commit()

    return redirect('/admin/manage_drives')


@app.route('/admin/manage_companies')
@token_required
def manage_companies(current_user):
    if current_user.role != 'admin': return redirect('/')
    
    search_query = request.args.get('search', '')

    query = CompanyProfile.query.join(User)
    # Fetch companies filtered by name or email if search is provided
    if search_query:
        query = query.filter(
            (CompanyProfile.company_name.ilike(f'%{search_query}%')) |
            (User.email.ilike(f'%{search_query}%')) |
            (CompanyProfile.hr_contact.ilike(f'%{search_query}%'))
        )
    
    companies = query.all()
    return render_template("admin_companies.html", companies=companies)

@app.route('/admin/manage_drives')
@token_required
def manage_drives(current_user):
    if current_user.role != 'admin': return redirect('/')
    
    search_query = request.args.get('search', '')
    # Fetch drives filtered by company name or job title if search is provided
    drives = PlacementDrive.query.join(CompanyProfile).filter(
        (PlacementDrive.job_title.ilike(f'%{search_query}%')) |
        (CompanyProfile.company_name.ilike(f'%{search_query}%'))
    ).all()
    
    return render_template("admin_drives.html", drives=drives)



@app.route('/admin/global_search')
@token_required
def global_search(current_user):
    if current_user.role != 'admin': return redirect('/')
    
    query = request.args.get('q', '').strip()
    
    if not query:
        return redirect('/admin_dashboard')

    # Search Students (Name, Email, or Roll No)
    students = StudentProfile.query.join(User).filter(
        (User.name.ilike(f'%{query}%')) | 
        (User.email.ilike(f'%{query}%')) |
        (StudentProfile.roll_number.ilike(f'%{query}%'))
    ).all()

    # Search Companies (Name)
    companies = CompanyProfile.query.filter(
        CompanyProfile.company_name.ilike(f'%{query}%')
    ).all()

    return render_template("admin_search.html", 
                           query=query, 
                           students=students, 
                           companies=companies)


@app.route('/contact')
def contact():
    return render_template("contact.html")


@app.route('/logout')
def logout():
    resp = make_response(redirect('/'))
    resp.set_cookie('token', '', expires=0)
    return resp


if __name__ == "__main__":
    app.run(debug=True)