from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import MuscleGroup, Exercise
from app import db

exercises_bp = Blueprint('exercises', __name__)


@exercises_bp.route('/exercises')
@login_required
def index():
    groups = MuscleGroup.query.all()
    return render_template('exercises/index.html', groups=groups)


@exercises_bp.route('/exercises/group/<int:group_id>')
@login_required
def group(group_id):
    muscle_group = MuscleGroup.query.get_or_404(group_id)
    exercises = Exercise.query.filter_by(muscle_group_id=group_id).all()
    return render_template('exercises/group.html', group=muscle_group, exercises=exercises)


@exercises_bp.route('/exercises/<int:exercise_id>')
@login_required
def detail(exercise_id):
    exercise = Exercise.query.get_or_404(exercise_id)
    return render_template('exercises/detail.html', exercise=exercise)


@exercises_bp.route('/exercises/new', methods=['GET', 'POST'])
@login_required
def new():
    groups = MuscleGroup.query.all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        group_id = request.form.get('muscle_group_id')
        description = request.form.get('description', '').strip()
        instructions = request.form.get('instructions', '').strip()
        difficulty = request.form.get('difficulty', 'Intermediário')
        equipment = request.form.get('equipment', '').strip()

        if not name or not group_id:
            flash('Nome e grupo muscular são obrigatórios.', 'error')
            return render_template('exercises/new.html', groups=groups)

        ex = Exercise(
            name=name,
            muscle_group_id=int(group_id),
            description=description or None,
            instructions=instructions or None,
            difficulty=difficulty,
            equipment=equipment or None
        )
        db.session.add(ex)
        db.session.commit()
        flash(f'Exercício "{name}" criado com sucesso!', 'success')
        return redirect(url_for('exercises.group', group_id=int(group_id)))

    return render_template('exercises/new.html', groups=groups)


@exercises_bp.route('/exercises/<int:exercise_id>/delete', methods=['POST'])
@login_required
def delete(exercise_id):
    exercise = Exercise.query.get_or_404(exercise_id)
    group_id = exercise.muscle_group_id
    db.session.delete(exercise)
    db.session.commit()
    flash('Exercício removido.', 'success')
    return redirect(url_for('exercises.group', group_id=group_id))


@exercises_bp.route('/api/exercises')
@login_required
def api_list():
    exercises = Exercise.query.all()
    return jsonify([{
        'id': e.id, 'name': e.name,
        'muscle_group': e.muscle_group.name,
        'difficulty': e.difficulty, 'equipment': e.equipment
    } for e in exercises])
