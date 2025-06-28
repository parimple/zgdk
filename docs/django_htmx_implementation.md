# Django + HTMX Implementation Guide dla zgdk

## 🚀 Dlaczego Django + HTMX?

### Prostota bez kompromisów
- **90% mniej JavaScriptu** - HTMX zastępuje React/Vue
- **Zero build steps** - nie ma webpack, babel, node_modules
- **Server-side rendering** - SEO friendly z natury
- **Django Admin** - gotowy panel admina za darmo

## 📋 Praktyczny Przykład: Strona Premium

### 1. Setup Projektu

```bash
# Struktura katalogów
zgdk/
├── bot/                 # Istniejący bot Discord
├── web/                 # Nowa aplikacja Django
│   ├── manage.py
│   ├── zgdk_web/       # Settings
│   ├── apps/           # Django apps
│   ├── templates/      # HTML + HTMX
│   └── static/         # CSS, obrazki
└── shared/             # Wspólny kod
    └── models.py       # SQLAlchemy models
```

### 2. Minimalna Konfiguracja

```python
# web/requirements.txt
Django==5.0.1
django-htmx==1.17.2
dj-stripe==2.8.3
django-allauth==0.57.0  # Discord login
python-decouple==3.8
psycopg2-binary==2.9.9
redis==5.0.1
gunicorn==21.2.0
```

```python
# web/zgdk_web/settings.py
from decouple import config

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'django_htmx',
    'djstripe',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.discord',
    
    # Our apps
    'apps.shop',
    'apps.dashboard',
]

# Discord OAuth
SOCIALACCOUNT_PROVIDERS = {
    'discord': {
        'APP': {
            'client_id': config('DISCORD_CLIENT_ID'),
            'secret': config('DISCORD_CLIENT_SECRET'),
        },
        'SCOPE': ['identify', 'email', 'guilds'],
    }
}

# Stripe
STRIPE_LIVE_PUBLIC_KEY = config('STRIPE_LIVE_PUBLIC_KEY')
STRIPE_LIVE_SECRET_KEY = config('STRIPE_LIVE_SECRET_KEY')
STRIPE_TEST_PUBLIC_KEY = config('STRIPE_TEST_PUBLIC_KEY')
STRIPE_TEST_SECRET_KEY = config('STRIPE_TEST_SECRET_KEY')
DJSTRIPE_WEBHOOK_SECRET = config('DJSTRIPE_WEBHOOK_SECRET')
DJSTRIPE_FOREIGN_KEY_TO_FIELD = 'id'
```

### 3. Model Integracji z Botem

```python
# web/apps/shop/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from djstripe.models import Customer, Subscription

class DiscordUser(AbstractUser):
    """Użytkownik z danymi Discord"""
    discord_id = models.CharField(max_length=64, unique=True)
    discord_username = models.CharField(max_length=255)
    discord_avatar = models.CharField(max_length=255, null=True)
    is_guild_member = models.BooleanField(default=False)
    
    # Połączenie ze Stripe
    stripe_customer = models.ForeignKey(
        Customer, null=True, blank=True,
        on_delete=models.SET_NULL
    )
    
    def get_active_subscription(self):
        if not self.stripe_customer:
            return None
        return self.stripe_customer.subscriptions.filter(
            status='active'
        ).first()
    
    @property
    def avatar_url(self):
        if self.discord_avatar:
            return f"https://cdn.discordapp.com/avatars/{self.discord_id}/{self.discord_avatar}.png"
        return "/static/img/default-avatar.png"

class PremiumPlan(models.Model):
    """Plany premium zG50/100/500/1000"""
    name = models.CharField(max_length=20)  # zG50
    display_name = models.CharField(max_length=50)  # "Starter"
    price = models.DecimalField(max_digits=6, decimal_places=2)
    stripe_price_id = models.CharField(max_length=255)
    features = models.JSONField(default=list)
    is_popular = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
```

### 4. Views z HTMX Magic

```python
# web/apps/shop/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django_htmx.http import HttpResponseClientRedirect, trigger_client_event
import stripe

def index(request):
    """Landing page ze sklepem"""
    plans = PremiumPlan.objects.all()
    stats = {
        'active_users': cache.get('active_premium_users', 234),
        'happy_users': cache.get('happy_users', 1337),
    }
    return render(request, 'shop/index.html', {
        'plans': plans,
        'stats': stats,
    })

@login_required
@require_http_methods(["POST"])
def create_checkout(request, plan_id):
    """HTMX endpoint - rozpoczyna proces płatności"""
    plan = get_object_or_404(PremiumPlan, id=plan_id)
    
    # Sprawdź czy jest na serwerze
    if not request.user.is_guild_member:
        # HTMX partial response - modal z błędem
        return render(request, 'shop/partials/error_modal.html', {
            'title': 'Ups!',
            'message': 'Musisz być członkiem serwera zaGadka aby kupić premium!',
            'action_url': 'https://discord.gg/zagadka',
            'action_text': 'Dołącz do serwera'
        })
    
    # Utwórz/pobierz customer w Stripe
    if not request.user.stripe_customer:
        customer = stripe.Customer.create(
            email=request.user.email,
            metadata={
                'discord_id': request.user.discord_id,
                'discord_username': request.user.discord_username,
            }
        )
        request.user.stripe_customer_id = customer.id
        request.user.save()
    
    # Utwórz checkout session
    session = stripe.checkout.Session.create(
        customer=request.user.stripe_customer_id,
        payment_method_types=['card', 'blik', 'p24'],
        line_items=[{
            'price': plan.stripe_price_id,
            'quantity': 1,
        }],
        mode='subscription',
        metadata={
            'discord_id': request.user.discord_id,
            'plan_name': plan.name,
        },
        success_url=request.build_absolute_uri('/success/'),
        cancel_url=request.build_absolute_uri('/premium/'),
    )
    
    # HTMX redirect do Stripe
    return HttpResponseClientRedirect(session.url)

@require_http_methods(["GET"])
def subscription_status(request):
    """HTMX endpoint - live status subskrypcji"""
    if not request.user.is_authenticated:
        return render(request, 'shop/partials/login_prompt.html')
    
    subscription = request.user.get_active_subscription()
    return render(request, 'shop/partials/subscription_status.html', {
        'subscription': subscription,
        'user': request.user,
    })
```

### 5. Templates z HTMX

```django
<!-- web/templates/base.html -->
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}zaGadka Premium{% endblock %}</title>
    
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    
    <!-- HTMX -->
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    
    <!-- Alpine.js for small interactions -->
    <script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
    
    <style>
        /* Dark theme podobny do Discord */
        :root {
            --bg-primary: #36393f;
            --bg-secondary: #2f3136;
            --bg-tertiary: #202225;
            --text-primary: #dcddde;
            --text-secondary: #b9bbbe;
            --accent: #5865f2;
        }
        
        body {
            background-color: var(--bg-tertiary);
            color: var(--text-primary);
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="bg-gray-800 p-4">
        <div class="container mx-auto flex justify-between items-center">
            <a href="/" class="text-2xl font-bold">zaGadka</a>
            
            <!-- User status - live update co 30s -->
            <div hx-get="{% url 'shop:user_status' %}" 
                 hx-trigger="load, every 30s"
                 hx-swap="innerHTML">
                <!-- Loading skeleton -->
                <div class="animate-pulse h-10 w-32 bg-gray-700 rounded"></div>
            </div>
        </div>
    </nav>
    
    <!-- Main content -->
    <main>
        {% block content %}{% endblock %}
    </main>
    
    <!-- Modal container for HTMX -->
    <div id="modal" class="htmx-indicator"></div>
    
    <!-- Toast notifications -->
    <div id="toast-container" class="fixed bottom-4 right-4 space-y-2"></div>
    
    {% block extra_js %}{% endblock %}
</body>
</html>
```

```django
<!-- web/templates/shop/index.html -->
{% extends "base.html" %}

{% block content %}
<div class="container mx-auto px-4 py-16">
    <!-- Hero Section -->
    <section class="text-center mb-16">
        <h1 class="text-5xl font-bold mb-4 bg-gradient-to-r from-blue-500 to-purple-600 bg-clip-text text-transparent">
            zaGadka Premium
        </h1>
        <p class="text-xl text-gray-400 mb-8">
            Odblokuj pełny potencjał swojego serwera Discord
        </p>
        
        <!-- Live stats -->
        <div class="flex justify-center gap-8 mb-8">
            <div class="text-center"
                 hx-get="{% url 'shop:live_stat' %}?type=active"
                 hx-trigger="load, every 10s"
                 hx-swap="innerHTML">
                <div class="text-3xl font-bold">{{ stats.active_users }}</div>
                <div class="text-gray-400">Aktywnych Premium</div>
            </div>
            
            <div class="text-center">
                <div class="text-3xl font-bold">{{ stats.happy_users }}+</div>
                <div class="text-gray-400">Zadowolonych użytkowników</div>
            </div>
        </div>
    </section>
    
    <!-- Pricing Cards -->
    <section class="grid md:grid-cols-4 gap-6 mb-16">
        {% for plan in plans %}
            <div class="bg-gray-800 rounded-lg p-6 relative
                        {% if plan.is_popular %}ring-2 ring-blue-500{% endif %}"
                 x-data="{ loading: false }">
                
                {% if plan.is_popular %}
                    <div class="absolute -top-3 left-1/2 transform -translate-x-1/2">
                        <span class="bg-blue-500 text-white px-3 py-1 rounded-full text-sm">
                            Najpopularniejszy
                        </span>
                    </div>
                {% endif %}
                
                <h3 class="text-2xl font-bold mb-2">{{ plan.display_name }}</h3>
                <div class="text-4xl font-bold mb-4">
                    {{ plan.price }} zł
                    <span class="text-lg text-gray-400">/miesiąc</span>
                </div>
                
                <ul class="space-y-2 mb-6">
                    {% for feature in plan.features %}
                        <li class="flex items-start">
                            <svg class="w-5 h-5 text-green-500 mr-2 mt-0.5 flex-shrink-0">
                                <path fill="currentColor" d="M20.285 2l-11.285 11.567-5.286-5.011-3.714 3.716 9 8.728 15-15.285z"/>
                            </svg>
                            <span class="text-gray-300">{{ feature }}</span>
                        </li>
                    {% endfor %}
                </ul>
                
                {% if user.is_authenticated %}
                    <button hx-post="{% url 'shop:create_checkout' plan.id %}"
                            hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'
                            @click="loading = true"
                            :disabled="loading"
                            class="w-full py-3 rounded-lg font-semibold transition
                                   bg-blue-600 hover:bg-blue-700 text-white
                                   disabled:opacity-50 disabled:cursor-not-allowed">
                        <span x-show="!loading">Wybierz plan</span>
                        <span x-show="loading" class="flex items-center justify-center">
                            <svg class="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Ładowanie...
                        </span>
                    </button>
                {% else %}
                    <a href="{% url 'account_login' %}?next=/premium/"
                       class="block w-full py-3 rounded-lg font-semibold text-center transition
                              bg-gray-700 hover:bg-gray-600 text-white">
                        Zaloguj się przez Discord
                    </a>
                {% endif %}
            </div>
        {% endfor %}
    </section>
    
    <!-- Features Section -->
    <section class="bg-gray-800 rounded-lg p-8">
        <h2 class="text-3xl font-bold mb-8 text-center">Co otrzymujesz z Premium?</h2>
        
        <div class="grid md:grid-cols-3 gap-8">
            <div class="text-center">
                <div class="bg-blue-500 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-white"><!-- Voice icon --></svg>
                </div>
                <h3 class="text-xl font-semibold mb-2">Prywatne kanały głosowe</h3>
                <p class="text-gray-400">Twórz własne kanały z pełną kontrolą uprawnień</p>
            </div>
            
            <div class="text-center">
                <div class="bg-purple-500 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-white"><!-- Coin icon --></svg>
                </div>
                <h3 class="text-xl font-semibold mb-2">Bonus zG coins</h3>
                <p class="text-gray-400">Zdobywaj więcej monet za aktywność (50-400% bonus)</p>
            </div>
            
            <div class="text-center">
                <div class="bg-green-500 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-white"><!-- Crown icon --></svg>
                </div>
                <h3 class="text-xl font-semibold mb-2">Ekskluzywne funkcje</h3>
                <p class="text-gray-400">Dostęp do specjalnych komend i funkcji bota</p>
            </div>
        </div>
    </section>
</div>

<!-- Success/Error Modals będą wstrzykiwane tutaj przez HTMX -->
<div id="modal-container"></div>
{% endblock %}
```

### 6. Django Admin jako Dashboard

```python
# web/apps/dashboard/admin.py
from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
import json

class PremiumAdminSite(AdminSite):
    site_header = 'zaGadka Premium Admin'
    site_title = 'zaGadka Admin'
    index_title = 'Dashboard'
    
    def index(self, request, extra_context=None):
        """Custom dashboard z statystykami"""
        extra_context = extra_context or {}
        
        # KPI
        now = timezone.now()
        month_start = now.replace(day=1)
        
        extra_context['stats'] = {
            'active_subscriptions': Subscription.objects.filter(
                status='active'
            ).count(),
            
            'monthly_revenue': Subscription.objects.filter(
                status='active'
            ).aggregate(
                total=Sum('plan__amount')
            )['total'] or 0,
            
            'new_this_month': Subscription.objects.filter(
                created__gte=month_start
            ).count(),
            
            'churn_rate': self.calculate_churn_rate(),
        }
        
        # Chart data for JS
        extra_context['chart_data'] = json.dumps({
            'revenue_by_month': self.get_revenue_chart_data(),
            'subscriptions_by_plan': self.get_plan_distribution(),
        })
        
        return super().index(request, extra_context)
    
    def get_revenue_chart_data(self):
        """Dane do wykresu przychodów"""
        # Implementation
        pass

# Rejestracja custom admin site
admin_site = PremiumAdminSite(name='premium_admin')

@admin.register(DiscordUser, site=admin_site)
class DiscordUserAdmin(admin.ModelAdmin):
    list_display = ['avatar_tag', 'discord_username', 'subscription_status', 
                   'joined_date', 'total_spent']
    list_filter = ['is_guild_member', 'date_joined']
    search_fields = ['discord_username', 'discord_id', 'email']
    readonly_fields = ['discord_id', 'stripe_customer']
    
    def avatar_tag(self, obj):
        return format_html(
            '<img src="{}" class="rounded-full" width="32" height="32">',
            obj.avatar_url
        )
    avatar_tag.short_description = ''
    
    def subscription_status(self, obj):
        sub = obj.get_active_subscription()
        if not sub:
            return format_html('<span class="text-gray-500">Brak</span>')
        
        color = 'green' if sub.status == 'active' else 'red'
        return format_html(
            '<span class="px-2 py-1 rounded text-white bg-{}">{}</span>',
            color, sub.plan.name
        )
    subscription_status.short_description = 'Premium'
    
    def total_spent(self, obj):
        if not obj.stripe_customer:
            return '0 zł'
        
        total = obj.stripe_customer.invoices.filter(
            status='paid'
        ).aggregate(Sum('total'))['total__sum'] or 0
        
        return f'{total/100:.2f} zł'
    total_spent.short_description = 'Wydane'
```

### 7. Webhook Integration

```python
# web/apps/shop/webhooks.py
from djstripe import webhooks
from djstripe.models import Event
import redis

r = redis.Redis()

@webhooks.handler("checkout.session.completed")
def handle_checkout_completed(event: Event):
    """Aktywacja premium po płatności"""
    session = event.data["object"]
    discord_id = session["metadata"]["discord_id"]
    plan_name = session["metadata"]["plan_name"]
    
    # Publikuj event dla bota
    bot_event = {
        "type": "premium_activated",
        "discord_id": discord_id,
        "plan": plan_name,
        "subscription_id": session["subscription"],
        "timestamp": timezone.now().isoformat()
    }
    
    r.publish('bot_events', json.dumps(bot_event))
    
    # Log w Django
    PremiumActivation.objects.create(
        user_id=discord_id,
        plan_name=plan_name,
        stripe_subscription_id=session["subscription"]
    )

@webhooks.handler("customer.subscription.deleted")
def handle_subscription_cancelled(event: Event):
    """Usunięcie premium po anulowaniu"""
    subscription = event.data["object"]
    discord_id = subscription["metadata"].get("discord_id")
    
    if discord_id:
        bot_event = {
            "type": "premium_cancelled",
            "discord_id": discord_id,
            "timestamp": timezone.now().isoformat()
        }
        
        r.publish('bot_events', json.dumps(bot_event))
```

## 🚀 Deployment

### Docker dla całości

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: zgdk
      POSTGRES_USER: zgdk
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
  
  django:
    build: ./web
    command: gunicorn zgdk_web.wsgi:application --bind 0.0.0.0:8000
    volumes:
      - ./web:/app
      - static_volume:/app/static
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://zgdk:${DB_PASSWORD}@postgres:5432/zgdk
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
  
  bot:
    build: ./bot
    volumes:
      - ./bot:/app
    environment:
      - DATABASE_URL=postgresql://zgdk:${DB_PASSWORD}@postgres:5432/zgdk
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
  
  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - static_volume:/static
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - django

volumes:
  postgres_data:
  static_volume:
```

## 🎯 Podsumowanie

Django + HTMX to **idealne rozwiązanie** dla zgdk ponieważ:

1. **Szybki start** - działający sklep w 2 tygodnie
2. **Prosty stack** - tylko Python, minimalne JS
3. **Django Admin** - gotowy dashboard od razu
4. **Łatwa integracja** - wspólna baza z botem
5. **Tanie utrzymanie** - jeden developer wystarczy

To pragmatyczne podejście pozwala skupić się na biznesie zamiast walczyć z technologią.