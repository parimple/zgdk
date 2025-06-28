# Python-Based E-commerce Architecture dla zgdk

## 🐍 Dlaczego Python zamiast JavaScript?

### Zalety podejścia "All-Python":
1. **Jedna technologia** - zespół zna już Python z bota
2. **Wspólne modele** - SQLAlchemy używane przez bota i web
3. **Django Admin** - gotowy panel admina oszczędza miesiące pracy
4. **Prostota** - brak kompilacji, bundlerów, node_modules
5. **Szybszy development** - Django batteries-included

## 🏗️ Rekomendowana Architektura: Django + HTMX

```
┌─────────────────────────────────────────────────────┐
│                    Użytkownicy                      │
└──────────┬─────────────────────┬───────────────────┘
           │                     │
    ┌──────▼──────┐       ┌─────▼──────┐
    │   Sklep     │       │   Discord   │
    │  (Django)   │       │    Bot      │
    └──────┬──────┘       └─────┬──────┘
           │                     │
           └──────────┬──────────┘
                      │
            ┌─────────▼─────────┐
            │  Shared Database  │
            │   (PostgreSQL)    │
            └───────────────────┘
```

## 💻 Stack Technologiczny

### Backend & Frontend (All-in-One)
```python
# requirements-web.txt
Django==5.0.1
django-htmx==1.17.2
django-crispy-forms==2.1
django-allauth==0.57.0  # Discord OAuth
dj-stripe==2.8.3  # Stripe integration
django-redis==5.4.0
celery==5.3.4  # Background tasks
django-environ==0.11.2
django-cors-headers==4.3.1
django-extensions==3.2.3
gunicorn==21.2.0
whitenoise==6.6.0  # Static files

# UI & Interactivity
django-tailwind==3.8.0
django-cotton==0.9.0  # Component system
```

### JavaScript (Minimalne)
```html
<!-- Tylko 3 biblioteki, zero buildu -->
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
<script src="https://unpkg.com/alpinejs@3.13.3/dist/cdn.min.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
```

## 📁 Struktura Projektu

```
zgdk_web/
├── zgdk_web/           # Główny projekt Django
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
│
├── apps/
│   ├── shop/           # E-commerce
│   │   ├── models.py   # Produkty, zamówienia
│   │   ├── views.py    # Widoki sklepu
│   │   ├── forms.py    # Formularze
│   │   └── templates/
│   │
│   ├── premium/        # Zarządzanie premium
│   │   ├── models.py   # Współdzielone z botem!
│   │   ├── views.py
│   │   └── tasks.py    # Celery tasks
│   │
│   ├── dashboard/      # Admin dashboard
│   │   ├── admin.py    # Customizacja Django Admin
│   │   ├── views.py    # Dodatkowe widoki
│   │   └── charts.py   # Wykresy
│   │
│   └── accounts/       # Użytkownicy
│       ├── models.py   # Rozszerzenie User
│       ├── views.py    # Login/logout
│       └── adapters.py # Discord OAuth
│
├── templates/          # Szablony HTML
│   ├── base.html
│   ├── components/     # Reusable components
│   └── partials/       # HTMX fragments
│
├── static/            # CSS, JS, images
└── media/             # User uploads
```

## 🛍️ Implementacja Sklepu

### 1. Landing Page z HTMX

```django
<!-- templates/shop/index.html -->
{% extends "base.html" %}
{% load cotton %}

{% block content %}
<div class="container mx-auto px-4">
    <!-- Hero Section -->
    <section class="py-20 text-center">
        <h1 class="text-5xl font-bold mb-4">zaGadka Premium</h1>
        <p class="text-xl text-gray-600 mb-8">
            Odblokuj pełny potencjał swojego serwera Discord
        </p>
        
        <!-- Live counter with HTMX -->
        <div hx-get="{% url 'shop:active_users' %}" 
             hx-trigger="load, every 30s"
             hx-swap="innerHTML">
            <div class="animate-pulse">Ładowanie...</div>
        </div>
    </section>

    <!-- Pricing Cards -->
    <section class="py-16">
        <div class="grid md:grid-cols-4 gap-6">
            {% for plan in plans %}
                {% c-pricing-card plan=plan %}
            {% endfor %}
        </div>
    </section>
</div>
{% endblock %}
```

### 2. Komponent Pricing Card

```django
<!-- templates/components/pricing_card.html -->
<div class="border rounded-lg p-6 hover:shadow-lg transition-shadow
            {% if plan.is_popular %}border-primary ring-2 ring-primary{% endif %}"
     x-data="{ loading: false }">
     
    {% if plan.is_popular %}
        <div class="bg-primary text-white px-3 py-1 rounded-full text-sm mb-4 inline-block">
            Najpopularniejszy
        </div>
    {% endif %}
    
    <h3 class="text-2xl font-bold mb-2">{{ plan.name }}</h3>
    <div class="text-4xl font-bold mb-4">
        {{ plan.price_display }}
        <span class="text-lg text-gray-600">/miesiąc</span>
    </div>
    
    <ul class="space-y-2 mb-6">
        {% for feature in plan.features %}
            <li class="flex items-center">
                <svg class="w-5 h-5 text-green-500 mr-2">...</svg>
                {{ feature }}
            </li>
        {% endfor %}
    </ul>
    
    <button hx-post="{% url 'shop:create_checkout' plan.id %}"
            hx-target="#modal"
            hx-swap="innerHTML"
            @click="loading = true"
            :disabled="loading"
            class="w-full btn btn-primary">
        <span x-show="!loading">Wybierz plan</span>
        <span x-show="loading">Ładowanie...</span>
    </button>
</div>
```

### 3. Views z HTMX

```python
# apps/shop/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django_htmx.http import HttpResponseClientRedirect
import stripe

class ShopView(View):
    def get(self, request):
        plans = PremiumPlan.objects.filter(active=True)
        return render(request, 'shop/index.html', {
            'plans': plans
        })

@login_required
@require_POST
def create_checkout(request, plan_id):
    """HTMX endpoint - tworzy sesję Stripe"""
    plan = get_object_or_404(PremiumPlan, id=plan_id)
    
    # Sprawdź czy user jest na serwerze
    if not request.user.is_on_discord_server():
        return render(request, 'partials/error_modal.html', {
            'message': 'Musisz być członkiem serwera zaGadka!'
        })
    
    # Utwórz sesję Stripe
    session = stripe.checkout.Session.create(
        payment_method_types=['card', 'blik', 'p24'],
        line_items=[{
            'price': plan.stripe_price_id,
            'quantity': 1,
        }],
        mode='subscription',
        metadata={
            'discord_id': request.user.discord_id,
            'plan_id': plan.id,
        },
        success_url=request.build_absolute_uri('/success/'),
        cancel_url=request.build_absolute_uri('/premium/'),
    )
    
    # HTMX redirect do Stripe
    return HttpResponseClientRedirect(session.url)

def active_users_counter(request):
    """HTMX fragment - live counter"""
    count = cache.get('active_premium_users', 0)
    return render(request, 'partials/active_users.html', {
        'count': count
    })
```

## 🎨 Django Admin jako Dashboard

### 1. Customizacja dla Premium Management

```python
# apps/dashboard/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count
from django.urls import reverse
from django.utils import timezone

@admin.register(PremiumSubscription)
class PremiumSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user_display', 'plan', 'status_badge', 
                   'created_at', 'expires_at', 'actions_buttons']
    list_filter = ['status', 'plan', 'created_at']
    search_fields = ['user__discord_username', 'user__discord_id']
    readonly_fields = ['stripe_subscription_id', 'created_at']
    
    def user_display(self, obj):
        return format_html(
            '<div class="flex items-center">'
            '<img src="{}" class="w-8 h-8 rounded-full mr-2">'
            '<span>{}</span>'
            '</div>',
            obj.user.discord_avatar_url,
            obj.user.discord_username
        )
    user_display.short_description = 'Użytkownik'
    
    def status_badge(self, obj):
        colors = {
            'active': 'green',
            'expired': 'red',
            'cancelled': 'yellow',
        }
        return format_html(
            '<span class="px-2 py-1 text-xs rounded-full bg-{}-100 text-{}-800">{}</span>',
            colors.get(obj.status, 'gray'),
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def actions_buttons(self, obj):
        return format_html(
            '<a href="{}" class="btn btn-sm btn-primary">Przedłuż</a> '
            '<a href="{}" class="btn btn-sm btn-secondary">Historia</a>',
            reverse('admin:extend_subscription', args=[obj.pk]),
            reverse('admin:payment_history', args=[obj.user.pk])
        )
    actions_buttons.short_description = 'Akcje'
    
    # Custom admin views
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('stats/', self.stats_view, name='premium_stats'),
            path('export/', self.export_view, name='premium_export'),
        ]
        return custom_urls + urls
    
    def stats_view(self, request):
        """Dashboard ze statystykami"""
        stats = {
            'total_active': PremiumSubscription.objects.filter(
                status='active'
            ).count(),
            'revenue_month': Payment.objects.filter(
                created_at__month=timezone.now().month
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
            'by_plan': PremiumSubscription.objects.values('plan__name').annotate(
                count=Count('id')
            ),
        }
        return render(request, 'admin/premium_stats.html', stats)
```

### 2. Dashboard Home z wykresami

```django
<!-- templates/admin/index.html -->
{% extends "admin/base_site.html" %}
{% load static %}

{% block extrahead %}
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
{% endblock %}

{% block content %}
<div class="dashboard-grid">
    <!-- KPI Cards -->
    <div class="grid grid-cols-4 gap-4 mb-8">
        <div class="stat-card" 
             hx-get="{% url 'admin:kpi_active_subs' %}"
             hx-trigger="load, every 60s">
            <div class="animate-pulse">...</div>
        </div>
        
        <div class="stat-card"
             hx-get="{% url 'admin:kpi_revenue' %}"
             hx-trigger="load, every 60s">
            <div class="animate-pulse">...</div>
        </div>
    </div>
    
    <!-- Charts -->
    <div class="grid grid-cols-2 gap-8">
        <div class="chart-container">
            <canvas id="revenueChart"></canvas>
        </div>
        
        <div class="chart-container">
            <canvas id="subscriptionsChart"></canvas>
        </div>
    </div>
    
    <!-- Recent Activity -->
    <div class="activity-feed mt-8"
         hx-get="{% url 'admin:recent_activity' %}"
         hx-trigger="load, every 30s">
        <div class="animate-pulse">...</div>
    </div>
</div>

<script>
// Wykresy z Alpine.js
document.addEventListener('alpine:init', () => {
    Alpine.data('dashboardCharts', () => ({
        async init() {
            const revenueData = await fetch('/admin/api/revenue-chart/').then(r => r.json());
            new Chart(document.getElementById('revenueChart'), revenueData);
        }
    }))
})
</script>
{% endblock %}
```

## 🔄 Integracja z Botem

### 1. Wspólne Modele

```python
# zgdk_common/models.py - współdzielone między botem a Django
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Member(Base):
    __tablename__ = 'members'
    
    id = Column(Integer, primary_key=True)
    discord_id = Column(String, unique=True, nullable=False)
    discord_username = Column(String)
    discord_avatar = Column(String)
    joined_at = Column(DateTime)

class PremiumRole(Base):
    __tablename__ = 'premium_roles'
    
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey('members.id'))
    role_name = Column(String)  # zG50, zG100, etc.
    expires_at = Column(DateTime)
    stripe_subscription_id = Column(String)
```

### 2. Synchronizacja przez Events

```python
# apps/premium/tasks.py
from celery import shared_task
from zgdk_common.events import PremiumActivatedEvent
import redis

r = redis.Redis()

@shared_task
def activate_premium(discord_id, plan_name, subscription_id):
    """Wysyła event do bota przez Redis pub/sub"""
    event = PremiumActivatedEvent(
        discord_id=discord_id,
        plan_name=plan_name,
        subscription_id=subscription_id,
        expires_at=datetime.now() + timedelta(days=30)
    )
    
    # Publikuj event
    r.publish('bot_events', event.json())
    
    # Zapisz w DB
    PremiumSubscription.objects.create(
        user_id=discord_id,
        plan_name=plan_name,
        stripe_subscription_id=subscription_id
    )
```

## 🚀 Deployment

### 1. Docker Compose dla Development

```yaml
# docker-compose.yml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: zgdk
      POSTGRES_USER: zgdk
      POSTGRES_PASSWORD: zgdk
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
  
  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/code
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    environment:
      - DATABASE_URL=postgresql://zgdk:zgdk@db:5432/zgdk
      - REDIS_URL=redis://redis:6379
  
  celery:
    build: .
    command: celery -A zgdk_web worker -l info
    volumes:
      - .:/code
    depends_on:
      - db
      - redis
    environment:
      - DATABASE_URL=postgresql://zgdk:zgdk@db:5432/zgdk
      - REDIS_URL=redis://redis:6379
  
  bot:
    build: ../zgdk  # Bot directory
    depends_on:
      - db
      - redis
    environment:
      - DATABASE_URL=postgresql://zgdk:zgdk@db:5432/zgdk
      - REDIS_URL=redis://redis:6379

volumes:
  postgres_data:
```

### 2. Production z Gunicorn

```python
# gunicorn.conf.py
bind = "0.0.0.0:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
preload_app = True
accesslog = "-"
errorlog = "-"
```

## 📊 Porównanie z JavaScript

### Django + HTMX vs Next.js dla tego projektu:

| Aspekt | Django + HTMX | Next.js + React |
|--------|---------------|-----------------|
| **Czas developmentu** | ✅ 2-3 tygodnie | ❌ 4-6 tygodni |
| **Złożoność** | ✅ Prosta | ❌ Wymaga 2 stacków |
| **Admin Panel** | ✅ Gotowy Django Admin | ❌ Trzeba budować |
| **SEO** | ✅ Naturalnie dobre | ⚠️ Wymaga SSR |
| **Performance** | ⚠️ Dobre dla <10k users | ✅ Skaluje się lepiej |
| **Maintenance** | ✅ Jeden język | ❌ Python + JS |
| **Realtime** | ⚠️ Możliwe z HTMX | ✅ Natywne wsparcie |

## 🎯 Dlaczego to najlepsze rozwiązanie?

1. **Szybkość rozwoju** - Django Admin oszczędza miesiące pracy
2. **Prostota** - Cały zespół zna Python
3. **Integracja** - Łatwe współdzielenie kodu z botem
4. **Koszty** - Jeden developer może ogarnąć wszystko
5. **Wystarczające** - Dla <10k użytkowników to idealne rozwiązanie

## 🔧 Pierwsze kroki

```bash
# 1. Setup projektu
django-admin startproject zgdk_web
cd zgdk_web

# 2. Instalacja
pip install -r requirements-web.txt

# 3. Konfiguracja
python manage.py migrate
python manage.py createsuperuser

# 4. Stripe webhook
stripe listen --forward-to localhost:8000/stripe/webhook/

# 5. Start
python manage.py runserver
```

Django + HTMX to **pragmatyczne rozwiązanie** które pozwoli szybko dostarczyć działający produkt, zachowując możliwość skalowania w przyszłości.