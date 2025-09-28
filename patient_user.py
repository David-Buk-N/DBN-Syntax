from flask import Blueprint, render_template, redirect, url_for, request, flash
import requests
from auth import login_required, get_current_user
from models import get_db
from google.cloud import firestore
from uuid import uuid4

patient_user_bp = Blueprint('patient_user', __name__, url_prefix='/patient')


@patient_user_bp.route('/dashboard')
@login_required
def index():
    user = get_current_user()
    return render_template('patients/patient_user/index.html', user=user)


@patient_user_bp.route('/survey', methods=['GET', 'POST'])
@login_required
def survey():
    user = get_current_user()
    diagnosis = None
    gemini_result = None

    if request.method == 'POST':
        mood = request.form.get('mood')
        stress = request.form.get('stress')
        sleep = request.form.get('sleep')
        support = request.form.get('support')
        notes = request.form.get('notes')

        # Store responses for logged-in users only
        if user and 'id' in user:
            db = get_db()
            db.collection('survey_responses').add({
                'user_id': user['id'],
                'mood': mood,
                'stress': stress,
                'sleep': sleep,
                'support': support,
                'notes': notes,
                'created_at': firestore.SERVER_TIMESTAMP
            })

        # Compose prompt for Gemini
        prompt = f"""
        Mental Health Survey Results:
        Mood: {mood}
        Stress: {stress}
        Sleep: {sleep}
        Support: {support}
        Notes: {notes}
        Please provide a brief, supportive, and actionable summary for the user based on these answers.
        """

        try:
            gemini_api_key = 'YOUR_GEMINI_API_KEY'
            gemini_url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_api_key}'
            response = requests.post(gemini_url, json={"contents": [{"parts": [{"text": prompt}]}]})
            if response.status_code == 200:
                gemini_data = response.json()
                gemini_result = gemini_data['candidates'][0]['content']['parts'][0]['text'] \
                    if gemini_data.get('candidates') else None
            else:
                gemini_result = "AI diagnosis unavailable. Please try again later."
        except Exception as e:
            gemini_result = f"Error contacting Gemini API: {str(e)}"

        # Fallback diagnosis logic
        if not gemini_result:
            if mood == 'crisis' or stress == 'severe':
                diagnosis = "You may be experiencing a mental health crisis. Please reach out for immediate support or book a consultation with a therapist."
            elif mood == 'poor' or sleep == 'poor':
                diagnosis = "You may be struggling with your mental health. Consider talking to a professional and practicing self-care."
            elif stress == 'moderate' or support == 'no':
                diagnosis = "You may be experiencing moderate stress or lack of support. Try connecting with support groups or a therapist."
            else:
                diagnosis = "Your responses indicate you are doing well. Keep up your wellness habits!"

        return render_template('patients/patient_user/survey.html',
                               user=user, diagnosis=diagnosis, gemini_result=gemini_result)

    return render_template('patients/patient_user/survey.html', user=user)


@patient_user_bp.route('/find_therapist')
@login_required
def find_therapist():
    user = get_current_user()
    db = get_db()

    therapists = []
    booked_therapist_ids = set()

    if user and 'id' in user:
        # Fetch all consult requests for this patient
        consults_ref = db.collection('consult_requests').where('patient_id', '==', user['id']).stream()
        for c in consults_ref:
            consult = c.to_dict()
            booked_therapist_ids.add(consult.get('therapist_id'))

    # Fetch all users with role == 'therapist'
    therapists_ref = db.collection('users').where('role', '==', 'therapist').stream()
    for t in therapists_ref:
        data = t.to_dict()
        data['id'] = t.id
        data['profession'] = data.get('profession', 'Therapist')
        data['bio'] = data.get('bio', 'No bio available.')
        data['already_booked'] = data['id'] in booked_therapist_ids
        therapists.append(data)

    max_booked = len(booked_therapist_ids) >= 3

    return render_template('patients/patient_user/find_therapist.html',
                           user=user, therapists=therapists, max_booked=max_booked)


@patient_user_bp.route('/request_consult/<therapist_id>', methods=['POST'])
@login_required
def request_consult(therapist_id):
    user = get_current_user()
    db = get_db()

    if not user or 'id' not in user:
        flash("You must be logged in as a patient to request a consult.", "danger")
        return redirect(url_for('patient_user.find_therapist'))

    try:
        consult_id = f"{user['id']}_{therapist_id}_{uuid4().hex[:8]}"

        db.collection('consult_requests').document(consult_id).set({
            'id': consult_id,
            'therapist_id': therapist_id,
            'patient_id': user['id'],
            'status': 'pending',
            'created_at': firestore.SERVER_TIMESTAMP
        })
        flash('Consult request sent to therapist!', 'success')
    except Exception as e:
        flash(f'Error sending request: {str(e)}', 'danger')

    return redirect(url_for('patient_user.find_therapist'))



# Chat page route
@patient_user_bp.route('/chat')
def chat():
    user = None
    try:
        user = get_current_user()
    except Exception:
        user = None
    return render_template('patients/patient_user/chat.html', user=user)

# ------------------ Progress ------------------ #
@patient_user_bp.route('/progress')
@login_required
def progress():
    user = get_current_user
    db = get_db()
    tasks = []

    tasks_ref = db.collection('tasks').where('user_id', '==', user['id']).stream()
    for t in tasks_ref:
        data = t.to_dict()
        data['id'] = t.id
        data['updated_at'] = str(data.get('updated_at', ''))
        tasks.append(data)

    return render_template('patients/patient_user/progress.html', user=user, tasks=tasks)
