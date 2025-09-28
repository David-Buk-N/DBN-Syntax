from flask import Flask, render_template, redirect, url_for, flash, request, session
from dotenv import load_dotenv
import os
from datetime import datetime

# Import custom modules
from auth import auth_bp, get_current_user
from patients import patients_bp
from therapists import therapists_bp
from admin import admin_bp
from patient_user import patient_user_bp
from models import initialize_firebase

# Load environment variables
load_dotenv()

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'

# Initialize Firebase
initialize_firebase()

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(patients_bp)
app.register_blueprint(therapists_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(patient_user_bp)

# Global template context
@app.context_processor
def inject_template_globals():
    """
    Injects global variables into Jinja templates:
    - current_user: object with is_authenticated attribute
    - now: current datetime function
    """
    user = get_current_user()
    # Create a simple object with is_authenticated for template checks
    current_user = type('CurrentUser', (), {
        'is_authenticated': bool(user),
        'data': user
    })()
    return {
        'current_user': current_user,
        'now': datetime.now  # now() is available in templates
    }

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# Home route
@app.route('/')
def home():
    user = get_current_user()
    if user:
        role = user.get('role')
        if role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif role == 'therapist':
            return redirect(url_for('therapists.dashboard'))
        elif role == 'patient':
            return redirect(url_for('patient_user.index'))
    return render_template('index.html')

# Main execution
if __name__ == '__main__':
    app.run(debug=True)
