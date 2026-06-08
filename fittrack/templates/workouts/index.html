{% extends 'base.html' %}
{% block title %}Planos{% endblock %}

{% block topbar %}
<div class="topbar">
    <h1>Meus Planos</h1>
    <div class="topbar-right">
        <a href="{{ url_for('workouts.new') }}" class="topbar-btn">+ Novo</a>
    </div>
</div>
{% endblock %}

{% block content %}
<div class="content">
    {% if plans %}
        {% for plan in plans %}
        <div class="card" style="margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
                <div>
                    <h3 style="font-family:'Syne',sans-serif; font-size:1.05rem; font-weight:800;">{{ plan.name }}</h3>
                    <div style="font-size:0.8rem; color:#888; margin-top:2px;">
                        {{ plan.plan_exercises|length }} exercício{% if plan.plan_exercises|length != 1 %}s{% endif %}
                        · Criado em {{ plan.created_at.strftime('%d/%m/%Y') }}
                    </div>
                </div>
            </div>
            {% if plan.description %}
            <p style="font-size:0.88rem; color:#666; margin-bottom:10px; line-height:1.5;">{{ plan.description }}</p>
            {% endif %}
            <!-- Exercises preview -->
            {% if plan.plan_exercises %}
            <div style="display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px;">
                {% for pe in plan.plan_exercises[:4] %}
                <span class="tag">{{ pe.exercise.name }}</span>
                {% endfor %}
                {% if plan.plan_exercises|length > 4 %}
                <span class="tag" style="background:#eee; color:#888;">+{{ plan.plan_exercises|length - 4 }}</span>
                {% endif %}
            </div>
            {% endif %}
            <div style="display:flex; gap:8px;">
                <a href="{{ url_for('workouts.detail', plan_id=plan.id) }}" class="btn btn-coral btn-sm" style="flex:1; justify-content:center;">Ver plano</a>
                <a href="{{ url_for('history.record') }}?plan={{ plan.id }}" class="btn btn-outline btn-sm" style="flex:1; justify-content:center;">Treinar</a>
                <form method="POST" action="{{ url_for('workouts.delete', plan_id=plan.id) }}" onsubmit="return confirm('Remover este plano?')">
                    <button type="submit" class="btn btn-sm" style="background:#FEE; color:#E74C3C; padding:8px 10px;">🗑</button>
                </form>
            </div>
        </div>
        {% endfor %}
    {% else %}
        <div class="empty-state">
            <div class="empty-icon">📋</div>
            <div class="empty-title">Nenhum plano criado</div>
            <p style="font-size:0.85rem; margin-top:6px; margin-bottom:20px; color:#888;">Monte seu treino personalizado</p>
            <a href="{{ url_for('workouts.new') }}" class="btn btn-coral">+ Criar primeiro plano</a>
        </div>
    {% endif %}
</div>
{% endblock %}
