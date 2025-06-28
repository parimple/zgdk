# n8n dla ZGDK Discord Bot

## Co to jest n8n?

**n8n** to open-source'owy (fair-code) workflow automation tool - coś jak Zapier, ale self-hosted i darmowy!

### Kluczowe zalety:
- ✅ **Self-hosted** = pełna kontrola
- ✅ **Fair-code license** = darmowy dla self-hosting
- ✅ **Visual workflow builder** = łatwe do zrozumienia
- ✅ **Kod + No-code** = elastyczność
- ✅ **350+ integracji** = w tym Discord!

## Koszty n8n

### Self-hosted (Rekomendowane):
```bash
# Na twoim serwerze/VPS
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n

# Koszt: $0 (tylko VPS ~$5/miesiąc)
```

### Cloud (opcja):
- Starter: €20/miesiąc
- Pro: €50/miesiąc
- Ale po co, skoro możesz self-host? 😉

## Przykłady Użycia dla ZGDK

### 1. **Bump Reminder Workflow**

```javascript
// n8n workflow dla przypominania o bumpach
{
  "nodes": [
    {
      "name": "Schedule Trigger",
      "type": "n8n-nodes-base.scheduleTrigger",
      "parameters": {
        "rule": {
          "interval": [{ "minutes": 5 }]
        }
      }
    },
    {
      "name": "Check Bump Cooldowns",
      "type": "n8n-nodes-base.postgres",
      "parameters": {
        "query": "SELECT * FROM bump_cooldowns WHERE expires_at < NOW()"
      }
    },
    {
      "name": "Discord Message",
      "type": "n8n-nodes-base.discord",
      "parameters": {
        "resource": "message",
        "operation": "send",
        "channelId": "{{$json.channel_id}}",
        "content": "{{$json.user_mention}} Możesz już zbumpować na {{$json.service}}!"
      }
    }
  ]
}
```

### 2. **Moderation Workflow**

```javascript
// Złożony workflow moderacji w n8n
{
  "nodes": [
    {
      "name": "Discord Webhook",
      "type": "n8n-nodes-base.webhook",
      "webhookId": "discord-message"
    },
    {
      "name": "Analyze Message",
      "type": "n8n-nodes-base.function",
      "parameters": {
        "functionCode": `
          // Prosta analiza spam
          const message = $input.item.json.content;
          const spamScore = 0;
          
          // Sprawdź powtórzenia
          if (/(.)\1{10,}/.test(message)) {
            spamScore += 50;
          }
          
          // Sprawdź linki
          const links = message.match(/https?:\/\/\S+/g);
          if (links && links.length > 3) {
            spamScore += 30;
          }
          
          return { spamScore, shouldModerate: spamScore > 40 };
        `
      }
    },
    {
      "name": "If Spam Detected",
      "type": "n8n-nodes-base.if",
      "parameters": {
        "conditions": {
          "boolean": [{
            "value1": "={{$json.shouldModerate}}",
            "value2": true
          }]
        }
      }
    },
    {
      "name": "Delete Message",
      "type": "n8n-nodes-base.discord",
      "parameters": {
        "resource": "message",
        "operation": "delete"
      }
    },
    {
      "name": "Log to Database",
      "type": "n8n-nodes-base.postgres",
      "parameters": {
        "operation": "insert",
        "table": "moderation_logs"
      }
    }
  ]
}
```

### 3. **Premium Purchase Flow**

```javascript
// Workflow dla zakupu premium
{
  "nodes": [
    {
      "name": "Payment Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "premium-purchase"
      }
    },
    {
      "name": "Verify Payment",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "https://api.tpay.com/verify",
        "method": "POST"
      }
    },
    {
      "name": "Update Database",
      "type": "n8n-nodes-base.postgres",
      "parameters": {
        "query": "INSERT INTO premium_purchases..."
      }
    },
    {
      "name": "Add Discord Role",
      "type": "n8n-nodes-base.discord",
      "parameters": {
        "resource": "member",
        "operation": "roleAdd",
        "guildId": "{{$env.GUILD_ID}}",
        "userId": "{{$json.discord_id}}",
        "roleId": "{{$json.role_id}}"
      }
    },
    {
      "name": "Send Confirmation",
      "type": "n8n-nodes-base.discord",
      "parameters": {
        "resource": "message",
        "operation": "send",
        "channelId": "{{$json.user_dm_channel}}",
        "content": "Dziękujemy za zakup premium! 🎉"
      }
    }
  ]
}
```

### 4. **Activity Tracking z AI**

```javascript
// Integracja z Gemini dla analizy aktywności
{
  "nodes": [
    {
      "name": "Collect Daily Stats",
      "type": "n8n-nodes-base.scheduleTrigger",
      "parameters": {
        "rule": { "interval": [{ "field": "days", "days": 1 }] }
      }
    },
    {
      "name": "Get User Activities",
      "type": "n8n-nodes-base.postgres",
      "parameters": {
        "query": "SELECT * FROM user_activities WHERE date = CURRENT_DATE"
      }
    },
    {
      "name": "Analyze with Gemini",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent",
        "method": "POST",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [{
            "name": "x-goog-api-key",
            "value": "{{$credentials.geminiApiKey}}"
          }]
        },
        "sendBody": true,
        "bodyParameters": {
          "parameters": [{
            "name": "contents",
            "value": {
              "parts": [{
                "text": "Przeanalizuj aktywność użytkowników: {{$json}}"
              }]
            }
          }]
        }
      }
    }
  ]
}
```

## Integracja n8n z ZGDK

### 1. **Setup Docker Compose**

```yaml
# docker-compose.yml - dodaj n8n
services:
  bot:
    # ... twój bot config
  
  postgres:
    # ... twoja baza
  
  n8n:
    image: n8nio/n8n
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      - N8N_HOST=n8n.yourdomain.com
      - N8N_PROTOCOL=https
      - N8N_WEBHOOK_URL=https://n8n.yourdomain.com/
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_USER=zagadka
      - DB_POSTGRESDB_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - n8n_data:/home/node/.n8n
    networks:
      - zgdk_network

volumes:
  n8n_data:
```

### 2. **Bot Integration**

```python
# cogs/integrations/n8n_integration.py
import aiohttp
from discord.ext import commands

class N8NIntegration(commands.Cog):
    """Integracja z n8n workflows."""
    
    def __init__(self, bot):
        self.bot = bot
        self.n8n_webhook_url = "http://n8n:5678/webhook/"
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Wysyłaj wiadomości do n8n dla analizy."""
        if message.author.bot:
            return
        
        # Wyślij do n8n workflow
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{self.n8n_webhook_url}discord-messages",
                json={
                    "message_id": str(message.id),
                    "author_id": str(message.author.id),
                    "content": message.content,
                    "channel_id": str(message.channel.id),
                    "timestamp": message.created_at.isoformat()
                }
            )
    
    @commands.command(name="trigger_workflow")
    @commands.has_permissions(administrator=True)
    async def trigger_workflow(self, ctx, workflow_name: str):
        """Manualnie uruchom workflow n8n."""
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                f"{self.n8n_webhook_url}{workflow_name}"
            )
            
            if response.status == 200:
                await ctx.send(f"✅ Workflow '{workflow_name}' uruchomiony!")
            else:
                await ctx.send(f"❌ Błąd uruchamiania workflow")
```

## Porównanie z Innymi Rozwiązaniami

| Feature | n8n | LangGraph | CrewAI | Temporal | Prefect |
|---------|-----|-----------|---------|----------|---------|
| **Licencja** | Fair-code | MIT | MIT | MIT | Apache 2.0 |
| **Koszt (self-host)** | $0 | $0 | $0 | $0 | $0 |
| **Visual Builder** | ✅ Świetny | ❌ | ❌ | ❌ | ✅ Dobry |
| **Discord Integration** | ✅ Native | ❌ Custom | ❌ Custom | ❌ Custom | ❌ Custom |
| **AI Integration** | ✅ Łatwa | ✅ Native | ✅ Native | ❌ | ❌ |
| **Learning Curve** | 🟢 Łatwy | 🟡 Średni | 🟡 Średni | 🔴 Trudny | 🟡 Średni |
| **Polish Community** | 🟡 Mała | ❌ | ❌ | ❌ | ❌ |

## Kiedy Używać n8n dla ZGDK?

### ✅ Użyj n8n dla:
1. **Scheduled tasks** (bump reminders, daily stats)
2. **Webhook handling** (payment notifications)
3. **Multi-system integration** (Discord + DB + API)
4. **Visual debugging** workflows
5. **Quick prototyping** nowych features

### ❌ NIE używaj n8n dla:
1. **Real-time message handling** (za wolne)
2. **Complex AI orchestration** (użyj LangGraph)
3. **High-frequency operations** (>100/sec)

## Przykład Implementacji dla ZGDK

```python
# Hybrid approach: Bot + n8n
class HybridBot(commands.Bot):
    def __init__(self):
        super().__init__(...)
        self.n8n_client = N8NClient()
    
    async def on_ready(self):
        # Zarejestruj workflows
        await self.n8n_client.register_workflow('bump_reminders')
        await self.n8n_client.register_workflow('daily_stats')
        await self.n8n_client.register_workflow('payment_processor')
    
    # Bot obsługuje real-time
    async def on_message(self, message):
        # Szybka moderacja lokalna
        if self.is_spam(message):
            await message.delete()
        
        # Złożone analizy do n8n (async)
        await self.n8n_client.send_to_workflow(
            'message_analysis',
            message.to_dict()
        )
```

## Podsumowanie

**n8n to świetny wybór dla ZGDK bo:**
1. 💰 **Darmowy** (self-hosted)
2. 🎨 **Visual workflows** - łatwe do zrozumienia
3. 🔌 **Native Discord support** - gotowe node'y
4. 🤖 **AI ready** - łatwa integracja z Gemini
5. 📊 **Monitoring** - widzisz co się dzieje

**Rekomendacja:**
- Użyj **n8n** dla scheduled tasks i integracji
- Zostaw **real-time** w bocie Python
- **AI (Gemini)** przez n8n dla batch processing
- **LangGraph** tylko dla bardzo złożonych flows

Total koszt: **$5/miesiąc** (VPS) + **$0** (Gemini free tier) = **$5/miesiąc**! 🎉