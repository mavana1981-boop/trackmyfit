{% extends 'base.html' %}
{% block title %}Novo Plano{% endblock %}

{% block topbar %}
<div class="topbar">
    <a href="{{ url_for('workouts.index') }}" class="topbar-back">←</a>
    <h1>Novo Plano</h1>
</div>
{% endblock %}

{% block extra_css %}
<style>
.exercise-picker { background:#F7F5F3; border-radius:12px; padding:12px; margin-top:10px; }
.ex-checkbox { display:flex; align-items:center; gap:10px; padding:8px 0; border-bottom:1px solid var(--border); cursor:pointer; }
.ex-checkbox:last-child { border-bottom:none; }
.ex-checkbox input[type=checkbox] { accent-color: var(--coral); width:18px; height:18px; flex-shrink:0; }
.selected-list { margin-top:12px; }
.selected-item {
    background:white; border:1.5px solid var(--border); border-radius:12px;
    padding:12px; margin-bottom:8px;
}
.selected-item h4 { font-family:'Syne',sans-serif; font-size:0.9rem; font-weight:700; margin-bottom:8px; }
.ex-params { display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; }
.ex-params input { padding:8px 10px; border:1.5px solid var(--border); border-radius:8px; font-size:0.85rem; text-align:center; outline:none; width:100%; }
.ex-params input:focus { border-color:var(--coral); }
.ex-params label { font-size:0.72rem; color:#888; text-align:center; font-weight:600; font-family:'Syne',sans-serif; }
</style>
{% endblock %}

{% block content %}
<div class="content">
    <form method="POST" id="planForm">
        <div class="card" style="margin-bottom:16px;">
            <div class="form-group">
                <label class="form-label">Nome do Plano *</label>
                <input type="text" name="name" class="form-control" placeholder="Ex: Treino A — Peito e Tríceps" required>
            </div>
            <div class="form-group" style="margin-bottom:0;">
                <label class="form-label">Descrição (opcional)</label>
                <textarea name="description" class="form-control" rows="2" placeholder="Objetivo, observações..."></textarea>
            </div>
        </div>

        <!-- Exercise picker -->
        <div class="section-header" style="margin-bottom:10px;">
            <span class="section-title">Exercícios</span>
        </div>
        <div class="card" style="margin-bottom:16px;">
            <div class="form-group" style="margin-bottom:10px;">
                <label class="form-label">Filtrar por grupo muscular</label>
                <select id="groupFilter" class="form-control" onchange="loadExercises()">
                    <option value="">Todos os grupos</option>
                    {% for group in groups %}
                    <option value="{{ group.id }}">{{ group.icon }} {{ group.name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="exercise-picker" id="exercisePicker">
                {% for group in groups %}
                    {% for ex in group.exercises %}
                    <label class="ex-checkbox" data-group="{{ group.id }}">
                        <input type="checkbox" value="{{ ex.id }}" data-name="{{ ex.name }}" onchange="updateSelected(this)">
                        <div>
                            <div style="font-weight:600; font-size:0.9rem;">{{ ex.name }}</div>
                            <div style="font-size:0.75rem; color:#888;">{{ group.name }} · <span class="chip chip-{{ ex.difficulty|lower }}">{{ ex.difficulty }}</span></div>
                        </div>
                    </label>
                    {% endfor %}
                {% endfor %}
            </div>
        </div>

        <!-- Selected exercises with params -->
        <div id="selectedList" class="selected-list"></div>

        <button type="submit" class="btn btn-coral btn-block" id="submitBtn">Salvar Plano</button>
    </form>
</div>
{% endblock %}

{% block extra_js %}
<script>
let selected = {};

function loadExercises() {
    const gid = document.getElementById('groupFilter').value;
    document.querySelectorAll('.ex-checkbox').forEach(el => {
        el.style.display = (!gid || el.dataset.group === gid) ? 'flex' : 'none';
    });
}

function updateSelected(cb) {
    const id = cb.value;
    const name = cb.dataset.name;
    if (cb.checked) {
        selected[id] = { name, sets: 3, reps: '10-12', rest: 60 };
    } else {
        delete selected[id];
    }
    renderSelected();
}

function renderSelected() {
    const list = document.getElementById('selectedList');
    const ids = Object.keys(selected);
    if (!ids.length) { list.innerHTML = ''; return; }

    let html = '<div class="section-header" style="margin-bottom:10px;"><span class="section-title">Configurar exercícios</span></div>';
    ids.forEach(id => {
        const ex = selected[id];
        html += `
        <div class="selected-item">
            <h4>💪 ${ex.name}</h4>
            <input type="hidden" name="exercise_ids" value="${id}">
            <div class="ex-params">
                <div>
                    <label>Séries</label>
                    <input type="number" name="sets" value="${ex.sets}" min="1" max="20" placeholder="Séries">
                </div>
                <div>
                    <label>Reps</label>
                    <input type="text" name="reps" value="${ex.reps}" placeholder="10-12">
                </div>
                <div>
                    <label>Descanso (s)</label>
                    <input type="number" name="rest" value="${ex.rest}" min="10" max="300" placeholder="60">
                </div>
            </div>
        </div>`;
    });
    list.innerHTML = html;
}
</script>
{% endblock %}
