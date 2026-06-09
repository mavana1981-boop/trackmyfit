from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import WorkoutSession, SessionExercise, WorkoutPlan, PlanExercise, Exercise, MuscleGroup
from datetime import datetime
import json

history_bp = Blueprint('history', __name__)


def _exercise_history(user_id, exercise_id, limit=6):
    return (
        db.session.query(SessionExercise)
        .join(WorkoutSession)
        .filter(
            WorkoutSession.user_id == user_id,
            SessionExercise.exercise_id == exercise_id,
            SessionExercise.weight_kg.isnot(None)
        )
        .order_by(WorkoutSession.date.desc())
        .limit(limit)
        .all()
    )[::-1]


def _attach_muscle_groups(session, group_ids):
    """Set explicit muscle groups on a session from a list of IDs."""
    session.muscle_groups = []
    for gid in group_ids:
        mg = MuscleGroup.query.get(gid)
        if mg:
            session.muscle_groups.append(mg)


# ── History list & detail ─────────────────────────────────────────────────────

@history_bp.route('/history')
@login_required
def index():
    sessions = WorkoutSession.query.filter_by(user_id=current_user.id)\
        .order_by(WorkoutSession.date.desc()).all()
    return render_template('history/index.html', sessions=sessions)


@history_bp.route('/history/<int:session_id>')
@login_required
def detail(session_id):
    session = WorkoutSession.query.filter_by(
        id=session_id, user_id=current_user.id).first_or_404()
    groups = MuscleGroup.query.all()
    return render_template('history/detail.html', session=session, all_groups=groups)


@history_bp.route('/history/<int:session_id>/edit', methods=['POST'])
@login_required
def edit(session_id):
    session = WorkoutSession.query.filter_by(
        id=session_id, user_id=current_user.id).first_or_404()
    custom_name = request.form.get('custom_name', '').strip()
    group_ids = [int(g) for g in request.form.getlist('muscle_group_ids') if g.isdigit()]
    session.custom_name = custom_name or None
    _attach_muscle_groups(session, group_ids)
    db.session.commit()
    flash('Treino atualizado.', 'success')
    return redirect(url_for('history.detail', session_id=session_id))


@history_bp.route('/history/<int:session_id>/delete', methods=['POST'])
@login_required
def delete(session_id):
    session = WorkoutSession.query.filter_by(
        id=session_id, user_id=current_user.id).first_or_404()
    db.session.delete(session)
    db.session.commit()
    flash('Registro removido.', 'success')
    return redirect(url_for('history.index'))


# ── Start workout selection ───────────────────────────────────────────────────

@history_bp.route('/start')
@login_required
def start():
    plans = WorkoutPlan.query.filter_by(user_id=current_user.id).all()
    groups = MuscleGroup.query.all()
    return render_template('history/start.html', plans=plans, groups=groups)


# ── Live workout ──────────────────────────────────────────────────────────────

@history_bp.route('/live/<plan_id>')
@login_required
def live(plan_id):
    class ExData:
        pass

    exercises = []
    selected_group_ids = []

    if plan_id == 'free':
        group_ids = [int(g) for g in request.args.get('groups', '').split(',') if g.isdigit()]
        if not group_ids:
            flash('Selecione pelo menos um grupo muscular.', 'error')
            return redirect(url_for('history.start'))
        selected_group_ids = group_ids
        raw = Exercise.query.filter(Exercise.muscle_group_id.in_(group_ids)).all()
        for ex in raw:
            e = ExData()
            e.id = ex.id
            e.name = ex.name
            e.muscle_group = ex.muscle_group
            e.sets = 3
            e.reps = '10-12'
            e.rest_seconds = 60
            e.weight = None
            e.history = _exercise_history(current_user.id, ex.id)
            exercises.append(e)
        plan_name = 'Treino Avulso'
        plan_id_val = None
    else:
        plan = WorkoutPlan.query.filter_by(
            id=int(plan_id), user_id=current_user.id).first_or_404()
        plan_name = plan.name
        plan_id_val = plan.id
        # Infer group IDs from plan exercises
        for pe in sorted(plan.plan_exercises, key=lambda x: x.order):
            gid = pe.exercise.muscle_group_id
            if gid not in selected_group_ids:
                selected_group_ids.append(gid)
            last = (
                db.session.query(SessionExercise)
                .join(WorkoutSession)
                .filter(
                    WorkoutSession.user_id == current_user.id,
                    SessionExercise.exercise_id == pe.exercise_id,
                    SessionExercise.weight_kg.isnot(None)
                )
                .order_by(WorkoutSession.date.desc())
                .first()
            )
            e = ExData()
            e.id = pe.exercise_id
            e.name = pe.exercise.name
            e.muscle_group = pe.exercise.muscle_group
            e.sets = pe.sets
            e.reps = pe.reps
            e.rest_seconds = pe.rest_seconds
            e.weight = last.weight_kg if last else None
            e.history = _exercise_history(current_user.id, pe.exercise_id)
            exercises.append(e)

    # ── Create session immediately on load ────────────────────────────────────
    ws = WorkoutSession(
        user_id=current_user.id,
        plan_id=plan_id_val,
        date=datetime.utcnow().date(),
    )
    db.session.add(ws)
    db.session.flush()
    _attach_muscle_groups(ws, selected_group_ids)
    db.session.commit()
    session_id = ws.id
    # ─────────────────────────────────────────────────────────────────────────

    import json as _json
    exercise_ids_json = _json.dumps([e.id for e in exercises])
    all_groups = MuscleGroup.query.all()

    return render_template('history/live.html',
                           exercises=exercises,
                           plan_name=plan_name,
                           plan_id=plan_id_val,
                           session_id=session_id,
                           exercise_ids_json=exercise_ids_json,
                           all_groups=all_groups,
                           selected_group_ids=selected_group_ids)


# ── Save live workout ─────────────────────────────────────────────────────────

@history_bp.route('/live/save', methods=['POST'])
@login_required
def save_live():
    session_id = request.form.get('session_id')
    duration   = request.form.get('duration') or None
    custom_name = request.form.get('custom_name', '').strip()
    group_ids  = [int(g) for g in request.form.getlist('muscle_group_ids') if g.isdigit()]
    raw_data   = request.form.get('exercise_data', '[]')

    try:
        ex_data = json.loads(raw_data)
    except Exception:
        ex_data = []

    try:
        exercise_ids = json.loads(request.form.get('exercise_ids_json', '[]'))
    except Exception:
        exercise_ids = []

    # Fetch the session created at live() start
    ws = None
    if session_id:
        ws = WorkoutSession.query.filter_by(
            id=int(session_id), user_id=current_user.id).first()

    if not ws:
        # Fallback: create now
        ws = WorkoutSession(
            user_id=current_user.id,
            plan_id=int(request.form.get('plan_id')) if request.form.get('plan_id') else None,
            date=datetime.utcnow().date()
        )
        db.session.add(ws)
        db.session.flush()

    # Update fields
    ws.duration_minutes = int(duration) if duration else None
    ws.custom_name = custom_name or None
    if group_ids:
        _attach_muscle_groups(ws, group_ids)

    # Remove old exercises (in case of re-save) and add new ones
    SessionExercise.query.filter_by(session_id=ws.id).delete()

    for item in ex_data:
        ex_idx = item.get('ex_idx', 0)
        sets = item.get('sets', [])
        done_sets = [s for s in sets if s.get('done')]
        if not done_sets or ex_idx >= len(exercise_ids):
            continue
        last_set = done_sets[-1]
        try:
            weight = float(last_set.get('weight')) if last_set.get('weight') else None
        except (ValueError, TypeError):
            weight = None
        se = SessionExercise(
            session_id=ws.id,
            exercise_id=exercise_ids[ex_idx],
            sets_done=len(done_sets),
            reps_done=last_set.get('reps', ''),
            weight_kg=weight
        )
        db.session.add(se)

    db.session.commit()
    flash(f'Treino finalizado! Duração: {duration or "?"}min', 'success')
    return redirect(url_for('history.index'))


# ── Manual record ─────────────────────────────────────────────────────────────

@history_bp.route('/record', methods=['GET', 'POST'])
@login_required
def record():
    plans  = WorkoutPlan.query.filter_by(user_id=current_user.id).all()
    groups = MuscleGroup.query.all()

    if request.method == 'POST':
        date_str    = request.form.get('date')
        plan_id     = request.form.get('plan_id') or None
        notes       = request.form.get('notes', '').strip()
        duration    = request.form.get('duration') or None
        custom_name = request.form.get('custom_name', '').strip()
        group_ids   = [int(g) for g in request.form.getlist('muscle_group_ids') if g.isdigit()]
        exercise_ids = request.form.getlist('exercise_ids')
        sets_done   = request.form.getlist('sets_done')
        reps_done   = request.form.getlist('reps_done')
        weights     = request.form.getlist('weight_kg')
        ex_notes    = request.form.getlist('ex_notes')

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            date = datetime.utcnow().date()

        ws = WorkoutSession(
            user_id=current_user.id,
            plan_id=int(plan_id) if plan_id else None,
            date=date, notes=notes,
            custom_name=custom_name or None,
            duration_minutes=int(duration) if duration else None
        )
        db.session.add(ws)
        db.session.flush()
        _attach_muscle_groups(ws, group_ids)

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
