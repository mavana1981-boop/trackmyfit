from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import WorkoutPlan, PlanExercise, Exercise, MuscleGroup
import os
import base64
import json
import requests as http_requests

workouts_bp = Blueprint('workouts', __name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _all_exercises_map():
    """Return {nome_lower: Exercise} for fuzzy matching."""
    return {e.name.lower(): e for e in Exercise.query.all()}


def _find_or_create_exercise(name, muscle_group_hint=None):
    """
    Try to match exercise name against existing exercises.
    If not found, create a new one under the best-matching muscle group.
    """
    name = name.strip()
    name_lower = name.lower()
    ex_map = _all_exercises_map()

    # Exact match
    if name_lower in ex_map:
        return ex_map[name_lower]

    # Partial match — name contains or is contained by existing
    for key, ex in ex_map.items():
        if name_lower in key or key in name_lower:
            return ex

    # Not found — create new exercise
    group = None
    if muscle_group_hint:
        group = MuscleGroup.query.filter(
            MuscleGroup.name.ilike(f'%{muscle_group_hint}%')
        ).first()
    if not group:
        group = MuscleGroup.query.first()

    new_ex = Exercise(
        name=name,
        description=f'Exercício importado via PDF.',
        instructions='Consulte o PDF original para instruções detalhadas.',
        difficulty='Intermediário',
        equipment='Consulte o plano',
        muscle_group_id=group.id
    )
    db.session.add(new_ex)
    db.session.flush()
    return new_ex


def _call_gemini(pdf_bytes):
    """
    Send PDF to Gemini 1.5 Flash and return parsed list of workout plans.
    Returns: [{'name': str, 'description': str, 'exercises': [
                {'name': str, 'sets': int, 'reps': str, 'rest_seconds': int,
                 'muscle_group': str}
              ]}]
    """
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('GEMINI_API_KEY não configurada nas variáveis de ambiente.')

    pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

    prompt = """Analise este PDF de treino e extraia todos os planos de treino encontrados.

Retorne SOMENTE um JSON válido, sem markdown, sem texto extra, no formato:
{
  "planos": [
    {
      "nome": "Treino A",
      "descricao": "Descrição opcional do treino",
      "exercicios": [
        {
          "nome": "Nome do exercício",
          "series": 3,
          "repeticoes": "10-12",
          "descanso_segundos": 60,
          "grupo_muscular": "Peito"
        }
      ]
    }
  ]
}

Regras:
- Extraia TODOS os treinos encontrados (Treino A, B, C, etc. ou qualquer nomenclatura usada)
- Se não encontrar séries/repetições, use valores padrão razoáveis (3 séries, 10-12 reps, 60s descanso)
- grupo_muscular deve ser um dos: Abdominais, Costas, Bíceps, Peito, Pernas, Ombros, Tríceps, Panturrilha
- Retorne apenas o JSON, sem explicações"""

    payload = {
        "contents": [{
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "application/pdf",
                        "data": pdf_b64
                    }
                },
                {"text": prompt}
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192
        }
    }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={api_key}"
    )

    resp = http_requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()

    data = resp.json()
    text = data['candidates'][0]['content']['parts'][0]['text']

    # Strip markdown fences if present
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        text = text.rsplit('```', 1)[0]

    parsed = json.loads(text.strip())
    return parsed.get('planos', [])


def _save_plans(planos, user_id):
    """Create WorkoutPlan + PlanExercise records from parsed Gemini output."""
    created = []
    for p in planos:
        plan = WorkoutPlan(
            name=p.get('nome', 'Plano Importado'),
            description=p.get('descricao', ''),
            user_id=user_id
        )
        db.session.add(plan)
        db.session.flush()

        for i, ex_data in enumerate(p.get('exercicios', [])):
            ex = _find_or_create_exercise(
                ex_data.get('nome', 'Exercício'),
                ex_data.get('grupo_muscular')
            )
            reps = str(ex_data.get('repeticoes', '10-12'))
            try:
                sets = int(ex_data.get('series', 3))
            except (ValueError, TypeError):
                sets = 3
            try:
                rest = int(ex_data.get('descanso_segundos', 60))
            except (ValueError, TypeError):
                rest = 60

            pe = PlanExercise(
                plan_id=plan.id,
                exercise_id=ex.id,
                sets=sets,
                reps=reps,
                rest_seconds=rest,
                order=i
            )
            db.session.add(pe)

        created.append(plan.name)

    db.session.commit()
    return created


# ── routes ───────────────────────────────────────────────────────────────────

@workouts_bp.route('/plans')
@login_required
def index():
    plans = WorkoutPlan.query.filter_by(user_id=current_user.id)\
        .order_by(WorkoutPlan.created_at.desc()).all()
    return render_template('workouts/index.html', plans=plans)


@workouts_bp.route('/plans/import-pdf', methods=['GET', 'POST'])
@login_required
def import_pdf():
    if request.method == 'POST':
        if 'pdf' not in request.files or request.files['pdf'].filename == '':
            flash('Selecione um arquivo PDF.', 'error')
            return redirect(url_for('workouts.import_pdf'))

        pdf_file = request.files['pdf']
        if not pdf_file.filename.lower().endswith('.pdf'):
            flash('O arquivo deve ser um PDF.', 'error')
            return redirect(url_for('workouts.import_pdf'))

        pdf_bytes = pdf_file.read()
        if len(pdf_bytes) > 20 * 1024 * 1024:  # 20MB limit
            flash('PDF muito grande. Máximo 20MB.', 'error')
            return redirect(url_for('workouts.import_pdf'))

        try:
            planos = _call_gemini(pdf_bytes)
            if not planos:
                flash('Nenhum treino encontrado no PDF. Verifique o conteúdo.', 'error')
                return redirect(url_for('workouts.import_pdf'))

            nomes = _save_plans(planos, current_user.id)
            flash(
                f'✅ {len(nomes)} plano(s) importado(s): {", ".join(nomes)}',
                'success'
            )
            return redirect(url_for('workouts.index'))

        except ValueError as e:
            flash(str(e), 'error')
        except http_requests.exceptions.Timeout:
            flash('Tempo esgotado ao consultar a IA. Tente novamente.', 'error')
        except http_requests.exceptions.HTTPError as e:
            flash(f'Erro na API Gemini: {e.response.status_code}. Verifique a GEMINI_API_KEY.', 'error')
        except json.JSONDecodeError:
            flash('A IA retornou um formato inesperado. Tente novamente.', 'error')
        except Exception as e:
            flash(f'Erro ao importar: {str(e)}', 'error')

        return redirect(url_for('workouts.import_pdf'))

    return render_template('workouts/import_pdf.html')


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
