{% extends 'base.html' %}
{% block title %}{{ plan.name }}{% endblock %}

{% block topbar %}
<div class="topbar">
    <a href="{{ url_for('workouts.index') }}" class="topbar-back">←</a>
    <h1>Plano</h1>
</div>
{% endblock %}

{% block content %}
<div class="content">
    <div class="card" style="background:var(--coral); border:none; margin-bottom:16px;">
        <h2 style="font-family:'Syne',sans-serif; color:white; font-size:1.3rem; font-weight:800; margin-bottom:4px;">{{ plan.name }}</h2>
        {% if plan.description %}
        <p style="color:rgba(255,255,255,0.8); font-size:0.9rem; margin-bottom:8px;">{{ plan.description }}</p>
        {% endif %}
        <span class="badge" style="background:rgba(255,255,255,0.25); font-size:0.75rem;">{{ plan.plan_exercises|length }} exercícios</span>
    </div>

    <div class="card" style="padding:0 16px; margin-bottom:16px;">
        {% for pe in plan.plan_exercises | sort(attribute='order') %}
        <div class="list-item" style="cursor:default;">
            <div style="width:28px; height:28px; border-radius:50%; background:var(--coral); color:white; font-family:'Syne',sans-serif; font-weight:800; font-size:0.85rem; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
                {{ loop.index }}
            </div>
            <div class="list-item-body">
                <div class="list-item-name">{{ pe.exercise.name }}</div>
                <div class="list-item-sub">
                    {{ pe.sets }} séries × {{ pe.reps }} reps
                    · {{ pe.rest_seconds }}s descanso
                </div>
            </div>
        </div>
        {% else %}
        <div class="empty-state" style="padding:24px 0;">
            <p style="color:#888;">Nenhum exercício no plano.</p>
        </div>
        {% endfor %}
    </div>

    <a href="{{ url_for('history.record') }}?plan={{ plan.id }}" class="btn btn-coral btn-block" style="margin-bottom:10px;">
        ▶️ Iniciar treino com este plano
    </a>
    <form method="POST" action="{{ url_for('workouts.delete', plan_id=plan.id) }}" onsubmit="return confirm('Remover este plano?')">
        <button type="submit" class="btn btn-block" style="background:#FEE; color:#E74C3C; width:100%;">🗑 Remover plano</button>
    </form>
</div>
{% endblock %}
