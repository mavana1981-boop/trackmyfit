from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from models import WorkoutSession, SessionExercise, WorkoutPlan, Exercise, MuscleGroup
from datetime import datetime

history_bp = Blueprint('history', __name__)


@history_bp.route('/history')
@login_required
def index():
    sessions = WorkoutSession.query.filter_by(user_id=current_user.id)\
        .order_by(WorkoutSession.date.desc()).all()
    return render_template('history/index.html', sessions=sessions)


@history_bp.route('/history/<int:session_id>')
@login_required
def detail(session_id):
    session = WorkoutSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    return render_template('history/detail.html', session=session)


@history_bp.route('/record', methods=['GET', 'POST'])
@login_required
def record():
    plans = WorkoutPlan.query.filter_by(user_id=current_user.id).all()
    groups = MuscleGroup.query.all()

    if request.method == 'POST':
        date_str = request.form.get('date')
        plan_id = request.form.get('plan_id') or None
        notes = request.form.get('notes', '').strip()
        duration = request.form.get('duration') or None
        exercise_ids = request.form.getlist('exercise_ids')
        sets_done = request.form.getlist('sets_done')
        reps_done = request.form.getlist('reps_done')
        weights = request.form.getlist('weight_kg')
        ex_notes = request.form.getlist('ex_notes')

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            date = datetime.utcnow().date()

        ws = WorkoutSession(
            user_id=current_user.id,
            plan_id=int(plan_id) if plan_id else None,
            date=date,
            notes=notes,
            duration_minutes=int(duration) if duration else None
        )
        db.session.add(ws)
        db.session.flush()

        for i, ex_id in enumerate(exercise_ids):
            se = SessionExercise(
                session_id=ws.id,
                exercise_id=int(ex_id),
                sets_done=int(sets_done[i]) if i < len(sets_done) and sets_done[i] else 0,
                reps_done=reps_done[i] if i < len(reps_done) else '',
                weight_kg=float(weights[i]) if i < len(weights) and weights[i] else None,
                notes=ex_notes[i] if i < len(ex_notes) else ''
            )
            db.session.add(se)

        db.session.commit()
        flash('Treino registrado com sucesso!', 'success')
        return redirect(url_for('history.index'))

    today = datetime.utcnow().date().strftime('%Y-%m-%d')
    return render_template('history/record.html', plans=plans, groups=groups, today=today)


@history_bp.route('/history/<int:session_id>/delete', methods=['POST'])
@login_required
def delete(session_id):
    session = WorkoutSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    db.session.delete(session)
    db.session.commit()
    flash('Registro removido.', 'success')
    return redirect(url_for('history.index'))
