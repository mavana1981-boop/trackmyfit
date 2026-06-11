from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import WorkoutSession, SessionExercise, WorkoutPlan, PlanExercise, Exercise, MuscleGroup
from datetime import datetime, timezone, timedelta
import json

history_bp = Blueprint('history', __name__)


def _today_brazil():
    return (datetime.now(timezone.utc) - timedelta(hours=3)).date()


def _exercise_history(user_id, exercise_id, limit=10):
    return (
        db.session.query(SessionExercise)
        .join(WorkoutSession)
        .filter(
            WorkoutSession.user_id == user_id,
            SessionExercise.exercise_id == exercise_id
        )
        .order_by(WorkoutSession.date.desc())
        .limit(limit)
        .all()
    )[::-1]


def _should_suggest_increase(history):
    weights = [h.weight_kg for h in history if h.weight_kg is not None]
    if len(weights) < 4:
        return False
    return len(set(weights[-4:])) == 1


def _attach_muscle_groups(session, group_ids):
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
            e.pe_id = None
            last = (
                db.session.query(SessionExercise)
                .join(WorkoutSession)
                .filter(WorkoutSession.user_id == current_user.id,
                        SessionExercise.exercise_id == ex.id,
                        SessionExercise.weight_kg.isnot(None))
                .order_by(WorkoutSession.date.desc()).first()
            )
            e.weight = last.weight_kg if last else None
            # Look up coach notes from any plan exercise for this user
            pe_with_notes = (
                db.session.query(PlanExercise)
                .join(WorkoutPlan, PlanExercise.plan_id == WorkoutPlan.id)
                .filter(WorkoutPlan.user_id == current_user.id,
                        PlanExercise.exercise_id == ex.id,
                        PlanExercise.notes.isnot(None))
                .first()
            )
            e.coach_notes = pe_with_notes.notes if pe_with_notes else ''
            e.series_data = None
            e.history = _exercise_history(current_user.id, ex.id)
            e.suggest_increase = _should_suggest_increase(e.history)
            exercises.append(e)
        plan_name = 'Treino Avulso'
        plan_id_val = None
    else:
        plan = WorkoutPlan.query.filter_by(
            id=int(plan_id), user_id=current_user.id).first_or_404()
        plan_name = plan.name
        plan_id_val = plan.id
        for pe in sorted(plan.plan_exercises, key=lambda x: x.order):
            gid = pe.exercise.muscle_group_id
            if gid not in selected_group_ids:
                selected_group_ids.append(gid)
            last = (
                db.session.query(SessionExercise)
                .join(WorkoutSession)
                .filter(WorkoutSession.user_id == current_user.id,
                        SessionExercise.exercise_id == pe.exercise_id,
                        SessionExercise.weight_kg.isnot(None))
                .order_by(WorkoutSession.date.desc()).first()
            )
            e = ExData()
            e.id = pe.exercise_id
            e.name = pe.exercise.name
            e.muscle_group = pe.exercise.muscle_group
            e.sets = pe.sets
            e.reps = pe.reps
            e.rest_seconds = pe.rest_seconds
            e.pe_id = pe.id
            e.weight = pe.suggested_weight if pe.suggested_weight else (last.weight_kg if last else None)
            e.coach_notes = pe.notes or ''
            e.series_data = getattr(pe, 'series_data', None) or None
            e.history = _exercise_history(current_user.id, pe.exercise_id)
            e.suggest_increase = _should_suggest_increase(e.history)
            exercises.append(e)

    # Session created lazily on first exercise save
    session_id = 'pending'
    plan_id_for_session = plan_id_val
    selected_group_ids_for_session = selected_group_ids

    import json as _json
    exercise_ids_json = _json.dumps([e.id for e in exercises])
    pe_ids_json = _json.dumps([getattr(e, 'pe_id', None) for e in exercises])
    plan_id_int = plan_id_val
    all_groups = MuscleGroup.query.all()

    return render_template('history/live.html',
                           exercises=exercises,
                           plan_name=plan_name,
                           plan_id=plan_id_val,
                           session_id=session_id,
                           plan_id_for_session=plan_id_for_session,
                           group_ids_for_session=selected_group_ids,
                           exercise_ids_json=exercise_ids_json,
                           pe_ids_json=pe_ids_json,
                           plan_id_int=plan_id_int,
                           all_groups=all_groups,
                           selected_group_ids=selected_group_ids)


# ── Real-time exercise save ───────────────────────────────────────────────────

@history_bp.route('/live/save-exercise', methods=['POST'])
@login_required
def save_exercise_realtime():
    """Save a single exercise with all its sets when user clicks OK."""
    data = request.json or {}
    session_id  = data.get('session_id')
    exercise_id = data.get('exercise_id')
    sets_data   = data.get('sets', [])   # list of {weight, reps}
    effort      = data.get('effort')
    notes       = data.get('notes', '')

    plan_id_fs    = data.get('plan_id_for_session')
    group_ids_fs  = data.get('group_ids_for_session', [])

    if not exercise_id:
        return jsonify({'ok': False, 'error': 'Missing exercise_id'}), 400

    # Lazy session creation: create on first exercise save
    ws = None
    if session_id and session_id != 'pending':
        ws = WorkoutSession.query.filter_by(
            id=int(session_id), user_id=current_user.id).first()

    if not ws:
        ws = WorkoutSession(
            user_id=current_user.id,
            plan_id=int(plan_id_fs) if plan_id_fs else None,
            date=_today_brazil(),
        )
        db.session.add(ws)
        db.session.flush()
        if group_ids_fs:
            _attach_muscle_groups(ws, [int(g) for g in group_ids_fs])
        db.session.commit()

    # Validate: at least one set with reps
    valid_sets = []
    for s in sets_data:
        r = (s.get('reps') or '').strip()
        w = s.get('weight')
        if r:
            try:
                weight_val = float(w) if w else None
            except (ValueError, TypeError):
                weight_val = None
            valid_sets.append({'reps': r, 'weight': weight_val})

    if not valid_sets:
        return jsonify({'ok': False, 'error': 'No valid sets'}), 400

    # Remove previous records for this exercise in this session
    SessionExercise.query.filter_by(
        session_id=ws.id, exercise_id=int(exercise_id)).delete()

    # Save one SessionExercise per set
    saved_ids = []
    for s in valid_sets:
        se = SessionExercise(
            session_id=ws.id,
            exercise_id=int(exercise_id),
            sets_done=1,
            reps_done=s['reps'],
            weight_kg=s['weight'],
            effort_level=effort,
            notes=notes or None
        )
        db.session.add(se)
        db.session.flush()
        saved_ids.append(se.id)

    db.session.commit()
    return jsonify({'ok': True, 'saved': len(saved_ids), 'session_id': ws.id})


@history_bp.route('/live/cancel/<path:session_id>', methods=['POST'])
@login_required
def cancel_live(session_id):
    if session_id == 'pending':
        return jsonify({'ok': True})  # Nothing was created
    try:
        sid = int(session_id)
    except ValueError:
        return jsonify({'ok': True})
    ws = WorkoutSession.query.filter_by(id=sid, user_id=current_user.id).first()
    if ws:
        count = SessionExercise.query.filter_by(session_id=ws.id).count()
        if count == 0:
            db.session.delete(ws)
            db.session.commit()
    return jsonify({'ok': True})


# ── Finalize session ──────────────────────────────────────────────────────────

@history_bp.route('/live/save', methods=['POST'])
@login_required
def save_live():
    session_id  = request.form.get('session_id')
    duration    = request.form.get('duration') or None
    custom_name = request.form.get('custom_name', '').strip()
    group_ids   = [int(g) for g in request.form.getlist('muscle_group_ids') if g.isdigit()]

    ws = None
    if session_id and session_id != 'pending':
        try:
            ws = WorkoutSession.query.filter_by(
                id=int(session_id), user_id=current_user.id).first()
        except (ValueError, TypeError):
            ws = None

    # If no session was ever created (user never saved an exercise), abort
    if not ws:
        flash('Nenhum exercício registrado. Treino não salvo.', 'info')
        return redirect(url_for('history.start'))

    # Count exercises already saved via real-time saves
    saved_count = SessionExercise.query.filter_by(session_id=ws.id).count()

    if saved_count == 0:
        db.session.delete(ws)
        db.session.commit()
        flash('Nenhum exercício registrado. Treino não salvo.', 'info')
        return redirect(url_for('history.start'))

    ws.duration_minutes = int(duration) if duration else None
    ws.custom_name = custom_name or None
    if group_ids:
        _attach_muscle_groups(ws, group_ids)

    db.session.commit()
    flash(f'Treino finalizado com {saved_count} série(s) registrada(s)!', 'success')
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
            date = _today_brazil()

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

    today = _today_brazil().strftime('%Y-%m-%d')
    return render_template('history/record.html', plans=plans, groups=groups, today=today)
