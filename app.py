import json
import re
import os
import random
import secrets
import string
import requests
from functools import wraps
from datetime import datetime
from flask import (Flask, render_template, request, redirect, url_for, flash,
                   jsonify, abort, session)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from config import Config
from models import (db, User, School, ApprovedStudent, Internship,
                    InternshipContent, Enrollment, Progress, SchoolClass,
                    Setting, Certificate)
from flask_migrate import Migrate

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Razorpay client
try:
    import razorpay
    razorpay_client = razorpay.Client(
        auth=(app.config['RAZORPAY_KEY_ID'], app.config['RAZORPAY_KEY_SECRET'])
    )
except Exception as e:
    razorpay_client = None
    print('⚠️ Razorpay not configured:', e)

# ---------- Upload config ----------
UPLOAD_FOLDER = os.path.join('static', 'uploads', 'profiles')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------- Default settings ----------
DEFAULT_SETTINGS = {
    'about_title': 'About InternHub',
    'about_tagline': 'Bridging the gap between students and real-world experience',
    'about_card_1_icon': '🎯',
    'about_card_1_title': 'Our Mission',
    'about_card_1_text': 'At InternHub, we believe every student deserves access to quality internships and practical learning opportunities.',
    'about_card_2_icon': '🌟',
    'about_card_2_title': 'Our Vision',
    'about_card_2_text': "To become India's most trusted platform where students learn, grow, and launch their careers.",
    'about_card_3_icon': '🏫',
    'about_card_3_title': 'School Partnerships',
    'about_card_3_text': 'We collaborate with schools to provide live classes, mentorship, and structured internship programs.',
    'cert_title': 'Our Certificates',
    'cert_tagline': 'Recognized certifications for every completed internship',
    'cert_card_1_badge': '🏅',
    'cert_card_1_title': 'Internship Completion Certificate',
    'cert_card_1_text': 'Awarded to students who successfully complete all modules with a passing score.',
    'cert_card_2_badge': '⭐',
    'cert_card_2_title': 'Excellence Certificate',
    'cert_card_2_text': 'For students who score above 90% and demonstrate outstanding performance.',
    'cert_card_3_badge': '📜',
    'cert_card_3_title': 'Skill Certification',
    'cert_card_3_text': 'Verifies specific skills learned during the internship.',
    'why_title': 'Why Choose InternHub?',
    'why_item_1': '100% Free for Students',
    'why_item_2': 'Verified Internships',
    'why_item_3': 'Video Lessons & Quizzes',
    'why_item_4': 'School Collaboration Program',
    'why_item_5': 'Recognized Certificates',
    'why_item_6': 'Live Classes & Mentorship',
}


# ---------- Jinja filter ----------
@app.template_filter('fromjson')
def fromjson_filter(s):
    try:
        return json.loads(s) if s else []
    except Exception:
        return []


# ---------- Helpers ----------
def youtube_embed_url(url):
    if not url:
        return ''
    url = url.strip()
    if '/embed/' in url:
        return url
    m = re.search(r'/live/([A-Za-z0-9_-]{6,})', url)
    if m:
        return f'https://www.youtube.com/embed/{m.group(1)}'
    m = re.search(r'youtu\.be/([A-Za-z0-9_-]{6,})', url)
    if m:
        return f'https://www.youtube.com/embed/{m.group(1)}'
    m = re.search(r'[?&]v=([A-Za-z0-9_-]{6,})', url)
    if m:
        return f'https://www.youtube.com/embed/{m.group(1)}'
    m = re.search(r'/shorts/([A-Za-z0-9_-]{6,})', url)
    if m:
        return f'https://www.youtube.com/embed/{m.group(1)}'
    return url


def gumlet_create_asset(title, source_url):
    """Create a Gumlet video asset from a source URL. Returns asset_id or None."""
    if not app.config.get('GUMLET_API_KEY'):
        print('⚠️ Gumlet API key not configured')
        return None
    url = 'https://api.gumlet.com/v1/video/assets'
    headers = {
        'Authorization': f'Bearer {app.config["GUMLET_API_KEY"]}',
        'Content-Type': 'application/json'
    }
    payload = {
        'title': title,
        'source': source_url,
        'format': 'mp4',
        'resolution': ['720p', '1080p']
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code in (200, 201):
            data = r.json()
            return data.get('asset_id') or data.get('id')
        else:
            print('Gumlet create error:', r.status_code, r.text)
            return None
    except Exception as e:
        print('Gumlet exception:', e)
        return None


def generate_school_code():
    while True:
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        if not School.query.filter_by(code=code).first():
            return code


def generate_certificate_code():
    year = datetime.utcnow().year
    while True:
        rand = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        code = f'IH-{year}-{rand}'
        if not Certificate.query.filter_by(code=code).first():
            return code


def check_and_issue_certificate(enrollment):
    """Issue certificate if student completed ALL content."""
    internship = enrollment.internship
    contents = internship.contents
    if not contents:
        return None

    completed_ids = {p.content_id for p in enrollment.progress if p.completed}
    all_ids = {c.id for c in contents}

    if not all_ids.issubset(completed_ids):
        return None

    existing = Certificate.query.filter_by(enrollment_id=enrollment.id).first()
    if existing:
        return existing

    quiz_scores = []
    quiz_count = 0
    for c in contents:
        if c.type == 'quiz':
            quiz_count += 1
            p = next((x for x in enrollment.progress if x.content_id == c.id), None)
            if p:
                quiz_scores.append(p.score)
    avg = (sum(quiz_scores) / len(quiz_scores)) if quiz_scores else 0

    cert = Certificate(
        code=generate_certificate_code(),
        user_id=enrollment.user_id,
        internship_id=enrollment.internship_id,
        enrollment_id=enrollment.id,
        avg_score=round(avg, 1),
        total_quizzes=quiz_count
    )
    db.session.add(cert)
    db.session.commit()
    return cert


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def seed_settings():
    for key, val in DEFAULT_SETTINGS.items():
        if not Setting.query.filter_by(key=key).first():
            db.session.add(Setting(key=key, value=val))
    db.session.commit()


def get_settings():
    db_settings = {s.key: s.value for s in Setting.query.all()}
    return {**DEFAULT_SETTINGS, **db_settings}


# ---------- Public ----------
@app.route('/')
def index():
    internships = Internship.query.order_by(Internship.created_at.desc()).limit(6).all()
    settings = get_settings()
    return render_template('index.html', internships=internships, settings=settings)


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            otp = str(random.randint(100000, 999999))
            session['reset_email'] = email
            session['reset_otp'] = otp
            flash(f'📱 Demo OTP (in real app sent via email/SMS): {otp}', 'info')
            return redirect(url_for('verify_otp'))
        flash('❌ No account found with that email.', 'danger')
        return redirect(url_for('forgot_password'))
    return render_template('forgot_password.html')


@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reset_email' not in session:
        flash('Please start from the forgot password page.', 'warning')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        entered = request.form.get('otp', '').strip()
        if entered == session.get('reset_otp'):
            session['reset_verified'] = True
            flash('✅ OTP verified! Now set a new password.', 'success')
            return redirect(url_for('reset_password'))
        flash('❌ Invalid OTP. Try again.', 'danger')
    return render_template('verify_otp.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('reset_verified'):
        flash('Please verify OTP first.', 'warning')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        pwd = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if pwd != confirm:
            flash('❌ Passwords do not match.', 'danger')
            return redirect(url_for('reset_password'))
        if len(pwd) < 6:
            flash('❌ Password must be at least 6 characters.', 'danger')
            return redirect(url_for('reset_password'))
        email = session.get('reset_email')
        user = User.query.filter_by(email=email).first()
        if user:
            user.password_hash = bcrypt.generate_password_hash(pwd).decode('utf-8')
            db.session.commit()
            flash('✅ Password reset successfully! Please login.', 'success')
        session.pop('reset_email', None)
        session.pop('reset_otp', None)
        session.pop('reset_verified', None)
        return redirect(url_for('login'))
    return render_template('reset_password.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email').lower().strip()
        phone = request.form.get('phone').strip()
        password = request.form.get('password')
        school_code = request.form.get('school_code', '').strip().upper()

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('signup'))

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')

        school_id = None
        approved = ApprovedStudent.query.filter(
            (ApprovedStudent.email == email) | (ApprovedStudent.phone == phone)
        ).first()
        if approved:
            school_id = approved.school_id
            approved.is_registered = True
            flash(f'You have been linked to {approved.school.name} via school approval.', 'success')
        elif school_code:
            school = School.query.filter_by(code=school_code, is_active=True).first()
            if school:
                school_id = school.id
                flash(f'You have been linked to {school.name}!', 'success')
            else:
                flash('School code entered is invalid. Account created without school link.', 'warning')

        user = User(name=name, email=email, phone=phone,
                    password_hash=hashed, role='student', school_id=school_id)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').lower().strip()
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('student_dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# ---------- Certificate / Verify ----------
@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        if code:
            return redirect(url_for('verify_certificate', code=code))
    return render_template('verify.html', cert=None, searched=False, code='')


@app.route('/verify/<code>')
def verify_certificate(code):
    code = code.strip().upper()
    cert = Certificate.query.filter_by(code=code).first()
    return render_template('verify.html', cert=cert, searched=True, code=code)


@app.route('/my-certificates')
@login_required
def my_certificates():
    certs = Certificate.query.filter_by(user_id=current_user.id)\
                             .order_by(Certificate.issued_at.desc()).all()
    return render_template('my_certificates.html', certificates=certs)


@app.route('/certificate/<code>')
@login_required
def view_certificate(code):
    cert = Certificate.query.filter_by(code=code).first_or_404()
    if cert.user_id != current_user.id and current_user.role != 'admin':
        abort(403)
    verify_url = url_for('verify_certificate', code=code, _external=True)
    return render_template('certificate.html', cert=cert, verify_url=verify_url)


# ---------- Student ----------
@app.route('/dashboard')
@login_required
def student_dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
    internships = Internship.query.order_by(Internship.created_at.desc()).limit(6).all()
    cert_count = Certificate.query.filter_by(user_id=current_user.id, is_revoked=False).count()
    return render_template('student_dashboard.html',
                           enrollments=enrollments,
                           internships=internships,
                           cert_count=cert_count)


@app.route('/internship/<int:iid>')
@login_required
def internship_detail(iid):
    internship = Internship.query.get_or_404(iid)
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, internship_id=iid).first()
    contents = internship.contents if enrollment and enrollment.payment_status in ['free', 'paid'] else []
    progress_map = {}
    if enrollment:
        for p in enrollment.progress:
            progress_map[p.content_id] = p
    cert = None
    if enrollment:
        cert = Certificate.query.filter_by(enrollment_id=enrollment.id).first()
    return render_template('internship_detail.html',
                           internship=internship,
                           enrollment=enrollment,
                           contents=contents,
                           progress_map=progress_map,
                           cert=cert)


@app.route('/enroll/<int:iid>', methods=['POST'])
@login_required
def enroll(iid):
    internship = Internship.query.get_or_404(iid)
    existing = Enrollment.query.filter_by(user_id=current_user.id, internship_id=iid).first()
    if existing:
        flash('Already enrolled.', 'info')
        return redirect(url_for('internship_detail', iid=iid))

    status = 'free' if not internship.is_paid else 'pending'
    enrollment = Enrollment(user_id=current_user.id, internship_id=iid, payment_status=status)
    db.session.add(enrollment)
    db.session.commit()

    if internship.is_paid:
        return redirect(url_for('payment_page', iid=iid))
    flash('Enrolled successfully!', 'success')
    return redirect(url_for('internship_detail', iid=iid))


@app.route('/payment/<int:iid>')
@login_required
def payment_page(iid):
    internship = Internship.query.get_or_404(iid)
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, internship_id=iid).first()
    if not enrollment:
        flash('Please enroll first.', 'warning')
        return redirect(url_for('internship_detail', iid=iid))

    if enrollment.payment_status == 'paid':
        flash('Already paid. Enjoy the internship!', 'success')
        return redirect(url_for('internship_detail', iid=iid))

    if not razorpay_client:
        flash('Payment gateway not configured. Contact admin.', 'danger')
        return redirect(url_for('internship_detail', iid=iid))

    amount_paise = int(float(internship.price) * 100)
    try:
        order = razorpay_client.order.create({
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': f'enroll_{enrollment.id}',
            'notes': {
                'internship_id': internship.id,
                'user_id': current_user.id,
                'enrollment_id': enrollment.id
            }
        })
    except Exception as e:
        flash(f'❌ Payment initialization failed: {str(e)}', 'danger')
        return redirect(url_for('internship_detail', iid=iid))

    return render_template('payment.html',
                           internship=internship,
                           enrollment=enrollment,
                           order=order,
                           razorpay_key=app.config['RAZORPAY_KEY_ID'])


@app.route('/verify-payment', methods=['POST'])
@login_required
def verify_payment():
    data = request.get_json() or {}
    params_dict = {
        'razorpay_order_id': data.get('razorpay_order_id', ''),
        'razorpay_payment_id': data.get('razorpay_payment_id', ''),
        'razorpay_signature': data.get('razorpay_signature', '')
    }
    if not razorpay_client:
        return jsonify({'success': False, 'message': 'Payment not configured.'}), 500

    try:
        razorpay_client.utility.verify_payment_signature(params_dict)
    except Exception as e:
        print('Razorpay verify error:', e)
        return jsonify({'success': False, 'message': 'Signature verification failed.'}), 400

    enrollment_id = data.get('enrollment_id')
    enrollment = Enrollment.query.get(enrollment_id)
    if not enrollment or enrollment.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Enrollment not found.'}), 404

    enrollment.payment_status = 'paid'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Payment verified!'})


@app.route('/mark_complete/<int:content_id>', methods=['POST'])
@login_required
def mark_complete(content_id):
    content = InternshipContent.query.get_or_404(content_id)
    enrollment = Enrollment.query.filter_by(user_id=current_user.id,
                                            internship_id=content.internship_id).first()
    if not enrollment:
        abort(403)

    score = 0
    total = 0
    details = []
    if content.type == 'quiz':
        try:
            answers = json.loads(request.data or '{}')
            quiz = json.loads(content.quiz_data or '[]')
            total = len(quiz)
            for i, q in enumerate(quiz):
                user_ans = answers.get(str(i), '')
                correct = q.get('answer', '')
                is_correct = (user_ans == correct)
                if is_correct:
                    score += 1
                details.append({
                    'question': q.get('q', ''),
                    'user_answer': user_ans,
                    'correct_answer': correct,
                    'is_correct': is_correct
                })
        except Exception as e:
            print('Quiz error:', e)

    p = Progress.query.filter_by(enrollment_id=enrollment.id, content_id=content_id).first()
    if not p:
        p = Progress(enrollment_id=enrollment.id, content_id=content_id)
        db.session.add(p)
    p.completed = True
    p.score = score
    db.session.commit()

    cert = check_and_issue_certificate(enrollment)
    cert_code = cert.code if cert else None

    return jsonify({'success': True, 'score': score, 'total': total,
                    'details': details, 'certificate_issued': bool(cert),
                    'certificate_code': cert_code})


@app.route('/my-internships')
@login_required
def my_internships():
    enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
    return render_template('my_internships.html', enrollments=enrollments)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        new_name = request.form.get('name', '').strip()
        if new_name and new_name != current_user.name:
            current_user.name = new_name
            db.session.commit()
            flash('Name updated.', 'success')

        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f'user_{current_user.id}.{ext}'
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                current_user.photo = f'uploads/profiles/{filename}'
                db.session.commit()
                flash('Profile photo updated.', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html')


@app.route('/profile/send-otp', methods=['POST'])
@login_required
def send_otp():
    otp = str(random.randint(100000, 999999))
    session['profile_otp'] = otp
    session['profile_otp_target'] = request.form.get('target', '')
    flash(f'📱 Demo OTP (in real app sent via SMS): {otp}', 'info')
    return redirect(url_for('profile'))


@app.route('/profile/update-contact', methods=['POST'])
@login_required
def update_contact():
    entered_otp = request.form.get('otp', '').strip()
    new_email = request.form.get('new_email', '').strip().lower()
    new_phone = request.form.get('new_phone', '').strip()

    if not session.get('profile_otp') or entered_otp != session['profile_otp']:
        flash('❌ Invalid OTP. Please try again.', 'danger')
        return redirect(url_for('profile'))

    session.pop('profile_otp', None)
    session.pop('profile_otp_target', None)

    if new_email and new_email != current_user.email:
        if User.query.filter_by(email=new_email).first():
            flash('Email already in use by another account.', 'danger')
            return redirect(url_for('profile'))
        current_user.email = new_email
    if new_phone:
        current_user.phone = new_phone
    db.session.commit()
    flash('✅ Contact details updated successfully!', 'success')
    return redirect(url_for('profile'))


@app.route('/join-school', methods=['GET', 'POST'])
@login_required
def join_school():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    if current_user.school_id:
        flash('You are already linked to a school.', 'info')
        return redirect(url_for('school_classes'))
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        school = School.query.filter_by(code=code, is_active=True).first()
        if school:
            current_user.school_id = school.id
            db.session.commit()
            flash(f'✅ Successfully linked to {school.name}!', 'success')
            return redirect(url_for('school_classes'))
        flash('❌ Invalid or inactive school code.', 'danger')
    return render_template('join_school.html')


@app.route('/leave-school', methods=['POST'])
@login_required
def leave_school():
    if current_user.role == 'admin' or not current_user.school_id:
        return redirect(url_for('student_dashboard'))
    current_user.school_id = None
    db.session.commit()
    flash('You have left your school.', 'info')
    return redirect(url_for('student_dashboard'))


@app.route('/school-classes')
@login_required
def school_classes():
    if not current_user.school_id:
        flash('You are not linked to any school.', 'warning')
        return redirect(url_for('join_school'))
    school = School.query.get(current_user.school_id)
    if not school or not school.is_active:
        flash('Your school subscription is inactive. Contact admin.', 'danger')
        return redirect(url_for('student_dashboard'))
    classes = SchoolClass.query.filter_by(school_id=school.id)\
                               .order_by(SchoolClass.created_at.desc()).all()
    return render_template('school_classes.html', school=school, classes=classes)


# ---------- Admin ----------
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    stats = {
        'students': User.query.filter_by(role='student').count(),
        'internships': Internship.query.count(),
        'schools': School.query.count(),
        'enrollments': Enrollment.query.count(),
        'certificates': Certificate.query.filter_by(is_revoked=False).count()
    }
    return render_template('admin/dashboard.html', stats=stats)


@app.route('/admin/certificates')
@login_required
@admin_required
def admin_certificates():
    certs = Certificate.query.order_by(Certificate.issued_at.desc()).all()
    return render_template('admin/certificates.html', certificates=certs)


@app.route('/admin/certificates/<int:cid>/revoke', methods=['POST'])
@login_required
@admin_required
def admin_certificate_revoke(cid):
    cert = Certificate.query.get_or_404(cid)
    cert.is_revoked = True
    cert.revoked_reason = request.form.get('reason', 'Revoked by admin').strip()
    db.session.commit()
    flash(f'Certificate {cert.code} revoked.', 'success')
    return redirect(url_for('admin_certificates'))


@app.route('/admin/certificates/<int:cid>/restore', methods=['POST'])
@login_required
@admin_required
def admin_certificate_restore(cid):
    cert = Certificate.query.get_or_404(cid)
    cert.is_revoked = False
    cert.revoked_reason = None
    db.session.commit()
    flash(f'Certificate {cert.code} restored.', 'success')
    return redirect(url_for('admin_certificates'))


@app.route('/admin/internships')
@login_required
@admin_required
def admin_internships():
    items = Internship.query.order_by(Internship.created_at.desc()).all()
    return render_template('admin/internships.html', internships=items)


@app.route('/admin/internships/new', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_internship_new():
    if request.method == 'POST':
        i = Internship(
            title=request.form['title'],
            description=request.form['description'],
            category=request.form['category'],
            price=float(request.form.get('price') or 0),
            duration=request.form.get('duration', ''),
            is_paid=request.form.get('is_paid') == 'on'
        )
        db.session.add(i)
        db.session.commit()
        flash('Internship created.', 'success')
        return redirect(url_for('admin_internship_content', iid=i.id))
    return render_template('admin/internship_form.html', internship=None)


@app.route('/admin/internships/<int:iid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_internship_edit(iid):
    i = Internship.query.get_or_404(iid)
    if request.method == 'POST':
        i.title = request.form['title']
        i.description = request.form['description']
        i.category = request.form['category']
        i.price = float(request.form.get('price') or 0)
        i.duration = request.form.get('duration', '')
        i.is_paid = request.form.get('is_paid') == 'on'
        db.session.commit()
        flash('Internship updated.', 'success')
        return redirect(url_for('admin_internships'))
    return render_template('admin/internship_form.html', internship=i)


@app.route('/admin/internships/<int:iid>/delete', methods=['POST'])
@login_required
@admin_required
def admin_internship_delete(iid):
    i = Internship.query.get_or_404(iid)
    db.session.delete(i)
    db.session.commit()
    flash('Internship deleted.', 'success')
    return redirect(url_for('admin_internships'))


@app.route('/admin/internships/<int:iid>/content')
@login_required
@admin_required
def admin_internship_content(iid):
    i = Internship.query.get_or_404(iid)
    return render_template('admin/internship_content.html', internship=i)


@app.route('/admin/internships/<int:iid>/content/add', methods=['POST'])
@login_required
@admin_required
def admin_content_add(iid):
    ctype = request.form['type']
    title = request.form['title']
    order = int(request.form.get('order') or 0)

    if ctype == 'video':
        source_url = request.form.get('video_url', '').strip()
        if not source_url:
            flash('Please provide a video source URL.', 'danger')
            return redirect(url_for('admin_internship_content', iid=iid))

        if 'youtube.com' in source_url or 'youtu.be' in source_url:
            c = InternshipContent(internship_id=iid, type='video', title=title,
                                  video_url=youtube_embed_url(source_url), order=order)
        else:
            asset_id = gumlet_create_asset(title, source_url)
            if not asset_id:
                flash('❌ Gumlet upload failed. Check the URL and try again.', 'danger')
                return redirect(url_for('admin_internship_content', iid=iid))
            c = InternshipContent(internship_id=iid, type='video', title=title,
                                  video_url=source_url,
                                  gumlet_video_id=asset_id,
                                  order=order)
    else:
        quiz_data = request.form.get('quiz_data', '[]')
        c = InternshipContent(internship_id=iid, type='quiz', title=title,
                              quiz_data=quiz_data, order=order)
    db.session.add(c)
    db.session.commit()
    flash('Content added.', 'success')
    return redirect(url_for('admin_internship_content', iid=iid))


@app.route('/admin/content/<int:cid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_content_edit(cid):
    c = InternshipContent.query.get_or_404(cid)
    if request.method == 'POST':
        c.title = request.form['title']
        c.order = int(request.form.get('order') or 0)
        if c.type == 'video':
            source_url = request.form.get('video_url', '').strip()
            if 'youtube.com' in source_url or 'youtu.be' in source_url:
                c.video_url = youtube_embed_url(source_url)
                c.gumlet_video_id = None
            else:
                asset_id = gumlet_create_asset(c.title, source_url)
                if asset_id:
                    c.video_url = source_url
                    c.gumlet_video_id = asset_id
        else:
            c.quiz_data = request.form.get('quiz_data', '[]')
        db.session.commit()
        flash('Content updated.', 'success')
        return redirect(url_for('admin_internship_content', iid=c.internship_id))
    return render_template('admin/content_edit.html', content=c)


@app.route('/admin/content/<int:cid>/delete', methods=['POST'])
@login_required
@admin_required
def admin_content_delete(cid):
    c = InternshipContent.query.get_or_404(cid)
    iid = c.internship_id
    db.session.delete(c)
    db.session.commit()
    flash('Content deleted.', 'success')
    return redirect(url_for('admin_internship_content', iid=iid))


@app.route('/admin/schools')
@login_required
@admin_required
def admin_schools():
    schools = School.query.all()
    return render_template('admin/schools.html', schools=schools)


@app.route('/admin/schools/new', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_school_new():
    if request.method == 'POST':
        s = School(
            name=request.form['name'],
            code=generate_school_code(),
            contact_email=request.form.get('contact_email', ''),
            contact_phone=request.form.get('contact_phone', ''),
            monthly_fee=float(request.form.get('monthly_fee') or 0),
            is_active=request.form.get('is_active') == 'on'
        )
        db.session.add(s)
        db.session.commit()
        flash(f'School created! Code: {s.code}', 'success')
        return redirect(url_for('admin_schools'))
    return render_template('admin/school_form.html', school=None)


@app.route('/admin/schools/<int:sid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_school_edit(sid):
    s = School.query.get_or_404(sid)
    if not s.code:
        s.code = generate_school_code()
        db.session.commit()
    if request.method == 'POST':
        s.name = request.form['name']
        s.contact_email = request.form.get('contact_email', '')
        s.contact_phone = request.form.get('contact_phone', '')
        s.monthly_fee = float(request.form.get('monthly_fee') or 0)
        s.is_active = request.form.get('is_active') == 'on'
        db.session.commit()
        flash('School updated.', 'success')
        return redirect(url_for('admin_schools'))
    return render_template('admin/school_form.html', school=s)


@app.route('/admin/schools/<int:sid>/regenerate-code', methods=['POST'])
@login_required
@admin_required
def admin_school_regen_code(sid):
    s = School.query.get_or_404(sid)
    s.code = generate_school_code()
    db.session.commit()
    flash(f'New school code: {s.code}', 'success')
    return redirect(url_for('admin_school_edit', sid=sid))


@app.route('/admin/schools/<int:sid>/delete', methods=['POST'])
@login_required
@admin_required
def admin_school_delete(sid):
    s = School.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    flash('School deleted.', 'success')
    return redirect(url_for('admin_schools'))


@app.route('/admin/schools/<int:sid>/approve_students', methods=['POST'])
@login_required
@admin_required
def admin_school_approve_students(sid):
    School.query.get_or_404(sid)
    raw = request.form.get('students', '')
    count = 0
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(',')
        email = parts[0].strip().lower()
        phone = parts[1].strip() if len(parts) > 1 else None
        if not email:
            continue
        existing = ApprovedStudent.query.filter_by(school_id=sid, email=email).first()
        if not existing:
            db.session.add(ApprovedStudent(school_id=sid, email=email, phone=phone))
            count += 1
    db.session.commit()
    flash(f'{count} students added.', 'success')
    return redirect(url_for('admin_schools'))


@app.route('/admin/schools/<int:sid>/classes', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_school_classes(sid):
    s = School.query.get_or_404(sid)
    if request.method == 'POST':
        raw_rec = request.form.get('recording_url', '')
        c = SchoolClass(
            school_id=sid,
            title=request.form['title'],
            description=request.form.get('description', ''),
            youtube_live_url='',
            recording_url=youtube_embed_url(raw_rec) if raw_rec else '',
            scheduled_time=request.form.get('scheduled_time', ''),
            is_live=request.form.get('is_live') == 'on'
        )
        db.session.add(c)
        db.session.commit()
        flash('Class added.', 'success')
        return redirect(url_for('admin_school_classes', sid=sid))
    return render_template('admin/school_classes.html', school=s, classes=s.classes)


@app.route('/admin/classes/<int:cid>/delete', methods=['POST'])
@login_required
@admin_required
def admin_class_delete(cid):
    c = SchoolClass.query.get_or_404(cid)
    sid = c.school_id
    db.session.delete(c)
    db.session.commit()
    flash('Class deleted.', 'success')
    return redirect(url_for('admin_school_classes', sid=sid))


@app.route('/admin/site-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_site_settings():
    if request.method == 'POST':
        for key in DEFAULT_SETTINGS.keys():
            val = request.form.get(key, '').strip()
            s = Setting.query.filter_by(key=key).first()
            if s:
                s.value = val
            else:
                db.session.add(Setting(key=key, value=val))
        db.session.commit()
        flash('Site settings updated.', 'success')
        return redirect(url_for('admin_site_settings'))
    settings = get_settings()
    return render_template('admin/site_settings.html', settings=settings)


@app.route('/admin/students')
@login_required
@admin_required
def admin_students():
    students = User.query.filter_by(role='student').all()
    return render_template('admin/students.html', students=students)


@app.route('/admin/students/<int:uid>')
@login_required
@admin_required
def admin_student_detail(uid):
    student = User.query.get_or_404(uid)
    schools = School.query.filter_by(is_active=True).all()
    return render_template('admin/student_detail.html', student=student, schools=schools)


@app.route('/admin/students/<int:uid>/link-school', methods=['POST'])
@login_required
@admin_required
def admin_student_link_school(uid):
    student = User.query.get_or_404(uid)
    school_id = request.form.get('school_id')
    if school_id:
        student.school_id = int(school_id)
        db.session.commit()
        flash(f'Student linked to {student.school.name}.', 'success')
    else:
        student.school_id = None
        db.session.commit()
        flash('Student unlinked.', 'info')
    return redirect(url_for('admin_student_detail', uid=uid))


def init_db():
    with app.app_context():
        db.create_all()
        admin_email = app.config['ADMIN_EMAIL'].lower()
        if not User.query.filter_by(email=admin_email).first():
            admin = User(
                name='Admin',
                email=admin_email,
                phone='0000000000',
                password_hash=bcrypt.generate_password_hash(app.config['ADMIN_PASSWORD']).decode('utf-8'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print(f"✅ Admin created: {admin_email} / {app.config['ADMIN_PASSWORD']}")
        seed_settings()


if __name__ == '__main__':
    init_db()
    app.run(debug=True)