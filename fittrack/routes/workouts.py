from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import WorkoutPlan, PlanExercise, Exercise, MuscleGroup

workouts_bp = Blueprint('workouts', __name__)


@workouts_bp.route('/plans')
@login_required
def index():
    plans = WorkoutPlan.query.filter_by(user_id=current_user.id).order_by(WorkoutPlan.created_at.desc()).all()
    return render_template('workouts/index.html', plans=plans)


@workouts_bp.route('/plans/new', methods=['GET', 'POST'])
@login_required
def new():
    groups = MuscleGroup.query.all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        exercise_ids = request.form.getlist('exercise_ids')
        sets_list = request.form.getlist('sets')
        reps_list = request.form.getlist('reps')
        rest_list = request.form.getlist('rest')

        if not name:
            flash('Nome do plano é obrigatório.', 'error')
            return render_template('workouts/new.html', groups=groups)

        plan = WorkoutPlan(name=name, description=description, user_id=current_user.id)
        db.session.add(plan)
        db.session.flush()

        for i, ex_id in enumerate(exercise_ids):
            pe = PlanExercise(
                plan_id=plan.id,
                exercise_id=int(ex_id),
                sets=int(sets_list[i]) if i < len(sets_list) else 3,
                reps=reps_list[i] if i < len(reps_list) else '10-12',
                rest_seconds=int(rest_list[i]) if i < len(rest_list) else 60,
                order=i
            )
            db.session.add(pe)

        db.session.commit()
        flash(f'Plano "{name}" criado com sucesso!', 'success')
        return redirect(url_for('workouts.index'))

    return render_template('workouts/new.html', groups=groups)


@workouts_bp.route('/plans/<int:plan_id>')
@login_required
def detail(plan_id):
    plan = WorkoutPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    return render_template('workouts/detail.html', plan=plan)


@workouts_bp.route('/plans/<int:plan_id>/delete', methods=['POST'])
@login_required
def delete(plan_id):
    plan = WorkoutPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    db.session.delete(plan)
    db.session.commit()
    flash('Plano removido.', 'success')
    return redirect(url_for('workouts.index'))


@workouts_bp.route('/api/exercises/by-group/<int:group_id>')
@login_required
def exercises_by_group(group_id):
    exercises = Exercise.query.filter_by(muscle_group_id=group_id).all()
    return jsonify([{'id': e.id, 'name': e.name, 'difficulty': e.difficulty} for e in exercises])
