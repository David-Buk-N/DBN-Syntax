from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from functools import wraps
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user, login_required
from firebase_admin import auth
from models import get_user, get_db, create_user
import re

# Authentication blueprint
auth_bp = Blueprint('auth', __name__)

# --------------------------
# Utility Functions
# --------------------------
def validate_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def get_current_user():
    """Get the current user based on session."""
    if 'user_id' in session:
        return get_user(session['user_id'])
    return None

# --------------------------
# Decorators
# --------------------------
def login_required(f):
    """Require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    """Require specific user role (admin, therapist, patient)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page', 'warning')
                return redirect(url_for('auth.login'))

            user = get_current_user()
            if not user or user.get('role') != role:
                flash(f'You must be a {role} to access this page', 'danger')
                return redirect(url_for('home'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --------------------------
# Auth Routes
# --------------------------
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Please enter both email and password', 'danger')
            return render_template('auth/login.html')

        try:
            # Authenticate with Firebase by email only (password validation would require Firebase REST)
            firebase_user = auth.get_user_by_email(email)
            user_data = get_user(firebase_user.uid)

            if not user_data:
                flash('User account not found', 'danger')
                return redirect(url_for('auth.login'))

            # Store session
            session['user_id'] = firebase_user.uid
            flash(f'Welcome back, {user_data.get("name", "")}!', 'success')

            # Redirect based on role
            role = user_data.get('role')
            if role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif role == 'therapist':
                return redirect(url_for('therapists.dashboard'))
            elif role == 'patient':
                return redirect(url_for('patient_user.index'))
            else:
                flash('Role not recognized. Contact support.', 'danger')
                return redirect(url_for('home'))

        except Exception as e:
            flash(f'Login failed: {str(e)}', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        phone = request.form.get('phone', '')

        # Validation
        if not all([name, email, password, confirm_password]):
            flash('Please fill out all required fields', 'danger')
            return render_template('auth/register.html', name=name, email=email, phone=phone)

        if not validate_email(email):
            flash('Please enter a valid email address', 'danger')
            return render_template('auth/register.html', name=name, email=email, phone=phone)

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('auth/register.html', name=name, email=email, phone=phone)

        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'danger')
            return render_template('auth/register.html', name=name, email=email, phone=phone)

        try:
            # Default new users as patients
            user_id = create_user(
                email=email,
                password=password,
                role='patient',
                name=name,
                phone=phone
            )

            if user_id:
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('Registration failed', 'danger')

        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'danger')

    return render_template('auth/register.html')


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))


@auth_bp.route('/profile')
@login_required
def profile():
    user = get_current_user()
    return render_template('auth/profile.html', user=user)


@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user = get_current_user()

    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone', '')

        if not name:
            flash('Name is required', 'danger')
            return render_template('auth/edit_profile.html', user=user)

        try:
            db = get_db()
            db.collection('users').document(session['user_id']).update({
                'name': name,
                'phone': phone
            })
            flash('Profile updated successfully', 'success')
            return redirect(url_for('auth.profile'))

        except Exception as e:
            flash(f'Failed to update profile: {str(e)}', 'danger')

    return render_template('auth/edit_profile.html', user=user)


def therapist_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != "therapist":
            flash("Access restricted to therapists only.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != "admin":
            flash("Access restricted to admins only.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function
