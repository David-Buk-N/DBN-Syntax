from flask import Blueprint, render_template, redirect, url_for, request, flash
from auth import get_current_user, therapist_required, admin_required
from models import (
    get_user,
    get_therapist_patients,
    get_patient_progress,
    get_db,
    get_patients,
    assign_patient as assign_patient_func,
    unassign_patient as unassign_patient_func
)

therapists_bp = Blueprint('therapists', __name__, url_prefix='/therapists')


@therapists_bp.route('/dashboard')
@therapist_required
def dashboard():
    """Display therapist dashboard."""
    user = get_current_user()

    try:
        # Get assigned patients
        patients = get_therapist_patients(user.get('id'))
        patients.sort(key=lambda x: x.get('name', ''))
        patient_count = len(patients)

        # Get recent progress updates
        recent_updates = []
        for patient in patients:
            updates = get_patient_progress(patient.get('id'))
            if updates:
                recent_updates.append({
                    'patient': patient,
                    'update': updates[0]  # Most recent update
                })

        # Sort updates (ensure proper datetime sorting)
        recent_updates.sort(
            key=lambda x: x['update'].get('date'),
            reverse=True
        )
        recent_updates = recent_updates[:5]

    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "danger")
        patients, patient_count, recent_updates = [], 0, []

    return render_template(
        'therapists/dashboard.html',
        user=user,
        patients=patients,
        patient_count=patient_count,
        recent_updates=recent_updates
    )


@therapists_bp.route('/')
@admin_required
def index():
    """Display list of therapists (admin only)."""
    try:
        therapists_ref = get_db().collection('users').where('role', '==', 'therapist').stream()
        therapists = []

        for therapist in therapists_ref:
            data = therapist.to_dict()
            data['id'] = therapist.id
            data['patient_count'] = len(get_therapist_patients(therapist.id))
            therapists.append(data)

        therapists.sort(key=lambda x: x.get('name', ''))

    except Exception as e:
        flash(f"Error loading therapists: {str(e)}", "danger")
        therapists = []

    return render_template('therapists/index.html', therapists=therapists)


@therapists_bp.route('/view/<therapist_id>')
@admin_required
def view(therapist_id):
    """View detailed therapist information (admin only)."""
    therapist = get_user(therapist_id)

    if not therapist or therapist.get('role') != 'therapist':
        flash('Therapist not found', 'danger')
        return redirect(url_for('therapists.index'))

    therapist['id'] = therapist_id
    patients = get_therapist_patients(therapist_id)

    return render_template('therapists/view.html',
                           therapist=therapist,
                           patients=patients)


@therapists_bp.route('/<therapist_id>/patients')
@admin_required
def therapist_patients(therapist_id):
    """View patients assigned to a therapist (admin only)."""
    therapist = get_user(therapist_id)

    if not therapist or therapist.get('role') != 'therapist':
        flash('Therapist not found', 'danger')
        return redirect(url_for('therapists.index'))

    therapist['id'] = therapist_id
    patients = get_therapist_patients(therapist_id)

    all_patients = get_patients()
    assigned_ids = [p.get('id') for p in patients]
    unassigned_patients = [p for p in all_patients if p.get('id') not in assigned_ids]

    return render_template('therapists/patients.html',
                           therapist=therapist,
                           patients=patients,
                           unassigned_patients=unassigned_patients)


@therapists_bp.route('/<therapist_id>/assign', methods=['POST'])
@admin_required
def assign_patient(therapist_id):
    """Assign a patient to a therapist (admin only)."""
    therapist = get_user(therapist_id)

    if not therapist or therapist.get('role') != 'therapist':
        flash('Therapist not found', 'danger')
        return redirect(url_for('therapists.index'))

    patient_id = request.form.get('patient_id')
    if not patient_id:
        flash('No patient selected', 'danger')
        return redirect(url_for('therapists.therapist_patients', therapist_id=therapist_id))

    try:
        assign_patient_func(therapist_id, patient_id)
        flash('Patient assigned successfully', 'success')
    except Exception as e:
        flash(f'Error assigning patient: {str(e)}', 'danger')

    return redirect(url_for('therapists.therapist_patients', therapist_id=therapist_id))


@therapists_bp.route('/<therapist_id>/unassign/<patient_id>', methods=['POST'])
@admin_required
def unassign_patient(therapist_id, patient_id):
    """Remove a patient-therapist assignment (admin only)."""
    therapist = get_user(therapist_id)

    if not therapist or therapist.get('role') != 'therapist':
        flash('Therapist not found', 'danger')
        return redirect(url_for('therapists.index'))

    try:
        unassign_patient_func(therapist_id, patient_id)
        flash('Patient unassigned successfully', 'success')
    except Exception as e:
        flash(f'Error unassigning patient: {str(e)}', 'danger')

    return redirect(url_for('therapists.therapist_patients', therapist_id=therapist_id))
