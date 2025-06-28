# Stripe Integration Best Practices dla Discord Botów

## 🎯 Kluczowe Wyzwania i Rozwiązania

### 1. Łączenie Tożsamości Discord ↔ Stripe

#### Problem
Discord ID ≠ Stripe Customer ID - potrzebujemy sposobu na ich połączenie.

#### Rozwiązanie
```python
# models/customer_mapping.py
class CustomerMapping(Base):
    __tablename__ = 'customer_mappings'
    
    discord_id = Column(String, primary_key=True)
    stripe_customer_id = Column(String, unique=True, nullable=False)
    email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Metadata
    discord_username = Column(String)
    discord_avatar = Column(String)
```

#### Best Practice
Zawsze używaj `metadata` w Stripe do przechowywania Discord ID:

```python
# Tworzenie klienta
customer = stripe.Customer.create(
    email=user_email,
    metadata={
        'discord_id': discord_user_id,
        'discord_username': discord_username,
        'guild_id': guild_id  # Jeśli bot obsługuje wiele serwerów
    }
)

# Tworzenie checkout session
session = stripe.checkout.sessions.create(
    customer=customer.id,
    payment_method_types=['card', 'blik', 'p24'],
    line_items=[{
        'price': price_id,
        'quantity': 1,
    }],
    mode='subscription',
    metadata={
        'discord_id': discord_user_id,
        'premium_tier': 'zG500',
        'guild_id': guild_id
    },
    success_url=success_url,
    cancel_url=cancel_url
)
```

### 2. Webhook Security

#### Critical Implementation
```python
import stripe
from fastapi import Header, Request, HTTPException

async def verify_webhook_signature(
    payload: bytes,
    signature: str,
    webhook_secret: str
) -> stripe.Event:
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, webhook_secret
        )
        return event
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

@app.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None)
):
    payload = await request.body()
    
    event = await verify_webhook_signature(
        payload,
        stripe_signature,
        settings.STRIPE_WEBHOOK_SECRET
    )
    
    # Process event...
```

### 3. Idempotency

#### Problem
Webhooks mogą być wysłane wielokrotnie - unikaj duplikacji rang.

#### Solution
```python
class ProcessedEvent(Base):
    __tablename__ = 'processed_stripe_events'
    
    event_id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    processed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default='success')

async def process_webhook(event: stripe.Event):
    # Check if already processed
    existing = await db.query(ProcessedEvent).filter_by(
        event_id=event.id
    ).first()
    
    if existing:
        logger.info(f"Event {event.id} already processed")
        return {"status": "already_processed"}
    
    # Process event
    try:
        await handle_event(event)
        
        # Mark as processed
        await db.add(ProcessedEvent(
            event_id=event.id,
            event_type=event.type
        ))
        await db.commit()
        
    except Exception as e:
        await db.rollback()
        raise
```

### 4. Subscription Lifecycle Management

#### Key Events to Handle
```python
CRITICAL_EVENTS = {
    # Nowa subskrypcja
    'checkout.session.completed': handle_new_subscription,
    'customer.subscription.created': handle_subscription_created,
    
    # Odnowienia
    'customer.subscription.updated': handle_subscription_updated,
    'invoice.payment_succeeded': handle_payment_success,
    
    # Problemy
    'invoice.payment_failed': handle_payment_failed,
    'customer.subscription.deleted': handle_subscription_cancelled,
    'customer.subscription.paused': handle_subscription_paused,
    
    # Zmiany planu
    'customer.subscription.updated': handle_plan_change,
}

async def handle_new_subscription(event: stripe.Event):
    session = event.data.object
    discord_id = session.metadata.get('discord_id')
    
    if not discord_id:
        logger.error("No discord_id in metadata!")
        return
    
    # Activate premium in bot
    await activate_premium_role(
        discord_id=discord_id,
        tier=session.metadata.get('premium_tier'),
        subscription_id=session.subscription,
        expires_at=calculate_expiry(session)
    )
```

### 5. Grace Period i Retry Logic

#### Implementation
```python
class SubscriptionStatus:
    ACTIVE = "active"
    PAST_DUE = "past_due"  # Grace period
    CANCELED = "canceled"
    UNPAID = "unpaid"

async def handle_subscription_status(subscription: stripe.Subscription):
    discord_id = subscription.metadata.get('discord_id')
    
    if subscription.status == SubscriptionStatus.ACTIVE:
        await ensure_premium_role(discord_id)
        
    elif subscription.status == SubscriptionStatus.PAST_DUE:
        # Grace period - zachowaj rolę ale wyślij ostrzeżenie
        await send_payment_warning(discord_id)
        
    elif subscription.status in [SubscriptionStatus.CANCELED, 
                                SubscriptionStatus.UNPAID]:
        # Remove premium after grace period
        await remove_premium_role(discord_id)
```

### 6. Testing w Development

#### Stripe CLI dla lokalnych webhooks
```bash
# Instalacja
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks do lokalnego serwera
stripe listen --forward-to localhost:8000/stripe/webhook

# Test specific events
stripe trigger checkout.session.completed \
  --add checkout_session:metadata.discord_id=123456789
```

#### Test Cards
```python
TEST_CARDS = {
    "success": "4242424242424242",
    "decline": "4000000000000002",
    "insufficient_funds": "4000000000009995",
    "3d_secure": "4000002500003155",
    "blik_pl": "Use BLIK test code: 777666"
}
```

### 7. Error Handling i Recovery

```python
class StripeErrorHandler:
    @staticmethod
    async def handle_webhook_error(event_type: str, error: Exception):
        if isinstance(error, stripe.error.StripeError):
            logger.error(f"Stripe error for {event_type}: {error}")
            
            # Notify admins
            await notify_admin_channel(
                f"⚠️ Stripe Error\n"
                f"Event: {event_type}\n"
                f"Error: {error.user_message}"
            )
            
            # Retry logic for temporary failures
            if error.code in ['rate_limit', 'api_connection_error']:
                await schedule_retry(event_type, delay=300)  # 5 min
        
        else:
            # Log to Sentry/monitoring
            capture_exception(error)
```

### 8. Multi-Server Support

```python
# Jeśli bot obsługuje wiele serwerów
class PremiumSubscription(Base):
    __tablename__ = 'premium_subscriptions'
    
    id = Column(Integer, primary_key=True)
    discord_id = Column(String, nullable=False)
    guild_id = Column(String, nullable=False)  # Server ID
    stripe_subscription_id = Column(String, unique=True)
    tier = Column(String)
    status = Column(String)
    expires_at = Column(DateTime)
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('discord_id', 'guild_id'),
    )
```

### 9. Compliance i Bezpieczeństwo

#### PCI Compliance
- **NIE przechowuj** danych kart kredytowych
- Używaj Stripe Checkout lub Elements
- Regularnie aktualizuj SDK

#### GDPR/RODO
```python
async def handle_gdpr_request(discord_id: str):
    # Export user data
    customer = await get_stripe_customer(discord_id)
    invoices = stripe.Invoice.list(customer=customer.id)
    subscriptions = stripe.Subscription.list(customer=customer.id)
    
    return {
        "customer_data": customer,
        "invoices": invoices.data,
        "subscriptions": subscriptions.data
    }
    
async def handle_deletion_request(discord_id: str):
    # Cancel subscriptions
    customer = await get_stripe_customer(discord_id)
    for sub in stripe.Subscription.list(customer=customer.id):
        stripe.Subscription.delete(sub.id)
    
    # Delete from our database
    await db.query(CustomerMapping).filter_by(
        discord_id=discord_id
    ).delete()
```

### 10. Monitoring i Alerty

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram

subscription_created = Counter(
    'stripe_subscription_created_total',
    'Total created subscriptions',
    ['tier', 'guild_id']
)

payment_processing_time = Histogram(
    'stripe_payment_processing_seconds',
    'Time to process payment webhook'
)

webhook_errors = Counter(
    'stripe_webhook_errors_total',
    'Total webhook processing errors',
    ['event_type', 'error_type']
)
```

### 11. Best Practices Summary

#### DO ✅
1. Zawsze weryfikuj webhook signatures
2. Implementuj idempotency
3. Używaj metadata do łączenia Discord ↔ Stripe
4. Loguj wszystkie transakcje
5. Implementuj retry logic
6. Testuj z Stripe CLI
7. Monitoruj webhook failures
8. Używaj Stripe's built-in features (np. trials, discounts)

#### DON'T ❌
1. Nie przechowuj danych kart
2. Nie ignoruj webhook failures
3. Nie zakładaj, że webhook przyjdzie tylko raz
4. Nie hardcode'uj price IDs
5. Nie zapominaj o grace periods
6. Nie modyfikuj subskrypcji bez Stripe API

### 12. Przykładowa Implementacja

```python
# services/stripe_service.py
class StripeService:
    def __init__(self, bot_service: BotService):
        self.bot = bot_service
        stripe.api_key = settings.STRIPE_SECRET_KEY
    
    async def create_checkout_session(
        self,
        discord_id: str,
        discord_username: str,
        tier: str,
        guild_id: str
    ) -> str:
        # Get or create customer
        customer = await self.get_or_create_customer(
            discord_id, discord_username
        )
        
        # Create session
        session = stripe.checkout.sessions.create(
            customer=customer.id,
            payment_method_types=['card', 'blik', 'p24'],
            line_items=[{
                'price': TIER_PRICES[tier],
                'quantity': 1,
            }],
            mode='subscription',
            metadata={
                'discord_id': discord_id,
                'premium_tier': tier,
                'guild_id': guild_id
            },
            success_url=f"{settings.FRONTEND_URL}/success",
            cancel_url=f"{settings.FRONTEND_URL}/premium"
        )
        
        return session.url
    
    async def handle_webhook(self, event: stripe.Event):
        handler = self.EVENT_HANDLERS.get(event.type)
        if handler:
            await handler(self, event)
        else:
            logger.info(f"Unhandled event type: {event.type}")
```

Ta dokumentacja powinna pomóc w prawidłowej implementacji integracji Stripe z botem Discord.