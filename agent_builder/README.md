# Agent Builder

Narzędzie do błyskawicznego tworzenia autonomicznych agentów AI (Jay-agentów) dla bota Discord.

## 🚀 Szybki start

### 1. Instalacja

```bash
# W katalogu projektu
pip install -r requirements.txt
```

### 2. Tworzenie agenta z szablonu

```python
from agent_builder import AgentFactory

factory = AgentFactory()

# Stwórz agenta moderacji w 1 linijce
moderation_agent = await factory.create_moderation_agent()
```

### 3. Tworzenie własnego agenta

```python
# Definiuj konfigurację
config = factory.create_custom_agent_config(
    name="Mój Agent",
    purpose="Analiza i przetwarzanie wiadomości",
    workflow=[
        {
            "name": "Pobierz dane",
            "action": "Pobierz wiadomość z Discord",
            "outputs": ["message_data"]
        },
        {
            "name": "Przetwórz AI",
            "action": "Analizuj z Gemini AI",
            "outputs": ["result"]
        }
    ]
)

# Zarejestruj i uruchom
agent_id = factory.register_agent(config)
agent = await factory.create_agent(agent_id)
```

## 📋 Dostępne szablony

### 1. **Moderation Agent**
- Cel: Moderacja treści na serwerze
- Workflow: Analiza → Cache → AI → Akcja
- Auto-skalowanie: 2-10 replik

### 2. **Analytics Agent**
- Cel: Analiza aktywności serwera
- Workflow: Zbieranie → Agregacja → AI Insights → Raport
- Generuje wykresy i rekomendacje

### 3. **Test Runner Agent**
- Cel: Automatyczne testowanie komend
- Workflow: Wykryj zmiany → Generuj testy → Wykonaj → Analizuj
- Sugeruje poprawki dla błędów

### 4. **Command Optimizer**
- Cel: Optymalizacja wydajności komend
- Workflow: Monitor → Analiza → Optymalizacja → Walidacja
- Automatyczne ulepszanie kodu

## 🛠️ CLI

```bash
# Utwórz agenta
agent-builder create moderation

# Listuj agentów
agent-builder list

# Uruchom agenta
agent-builder start sentiment_analyzer

# Testuj agenta
agent-builder test sentiment_analyzer

# Deploy do K8s
agent-builder deploy sentiment_analyzer

# Interaktywny kreator
agent-builder quickstart
```

## 🏗️ Architektura

```
Agent Builder
├── Core (AgentBuilder)
│   ├── Generowanie kodu Python
│   ├── Generowanie testów
│   └── Generowanie K8s YAML
├── Templates (AgentTemplate)
│   └── Predefiniowane szablony
├── Factory (AgentFactory)
│   ├── Zarządzanie agentami
│   └── Dependency Injection
└── Monitor (AgentMonitor)
    ├── Metryki wydajności
    └── Auto-optymalizacja
```

## 📊 Monitoring

Każdy agent automatycznie zbiera metryki:
- Liczba przetworzonych zadań
- Średni czas odpowiedzi
- Współczynnik sukcesu
- Zużycie zasobów

```python
# Pobierz metryki
metrics = await agent.get_metrics()
print(f"Sukces: {metrics['success_rate']}%")
```

## 🚀 Kubernetes

Automatyczne generowanie konfiguracji:
- Deployment z auto-skalowaniem
- Service dla load balancing
- HPA (Horizontal Pod Autoscaler)
- ConfigMap i Secrets

```yaml
# Przykład wygenerowanego Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sentiment-analyzer-agent
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: agent
        image: zgdk/sentiment-analyzer-agent:latest
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
```

## 🔄 Workflow agenta

1. **Input Processing** - Walidacja i przygotowanie danych
2. **AI Processing** - Przetwarzanie przez Gemini AI
3. **Output Formatting** - Formatowanie wyniku
4. **Metrics Update** - Aktualizacja metryk

## 🧪 Testowanie

Automatycznie generowane testy:

```python
# tests/agents/test_sentiment_analyzer_agent.py
@pytest.mark.asyncio
async def test_sentiment_analyzer_process_success(agent):
    input_data = SentimentAnalyzerInput(
        message_id="123",
        content="Test message",
        author_id=456
    )
    
    output = await agent.process(input_data)
    assert output.sentiment in ["positive", "negative", "neutral"]
```

## 💡 Przykłady użycia

### Discord Bot Integration

```python
@bot.command()
async def analyze(ctx, *, message):
    # Użyj agenta do analizy
    agent = await factory.get_agent("sentiment_analyzer")
    
    result = await agent.process(
        SentimentAnalyzerInput(
            message_id=str(ctx.message.id),
            content=message,
            author_id=ctx.author.id
        )
    )
    
    await ctx.send(f"Sentiment: {result.sentiment} ({result.confidence:.0%})")
```

### Batch Processing

```python
# Przetwarzanie wielu wiadomości
messages = await channel.history(limit=100).flatten()

for msg in messages:
    result = await agent.process(
        SentimentAnalyzerInput(
            message_id=str(msg.id),
            content=msg.content,
            author_id=msg.author.id
        )
    )
    # Zapisz wyniki do bazy
```

## 🔧 Konfiguracja

Zmienne środowiskowe:
- `GEMINI_API_KEY` - Klucz API do Google Gemini
- `REDIS_HOST` - Host Redis (domyślnie: redis-service)
- `DEV_MODE` - Tryb developerski

## 📈 Skalowanie

Agenty automatycznie skalują się na podstawie obciążenia:
- CPU > 70% → zwiększ repliki
- Memory > 80% → zwiększ repliki
- Min repliki: zdefiniowane w konfiguracji
- Max repliki: zdefiniowane w konfiguracji

## 🎯 Best Practices

1. **Małe, wyspecjalizowane agenty** - Jeden agent, jedno zadanie
2. **Cache wszystko** - Używaj Redis do cache'owania
3. **Async everywhere** - Wszystkie operacje asynchroniczne
4. **Metryki od początku** - Monitoruj od pierwszego dnia
5. **Testy automatyczne** - Każdy agent ma testy

## 🚨 Troubleshooting

### Agent nie startuje
```bash
# Sprawdź logi
docker logs <container_id>

# Sprawdź czy API key jest ustawiony
echo $GEMINI_API_KEY
```

### Wolna odpowiedź
- Sprawdź metryki: `agent.get_metrics()`
- Zwiększ repliki: `kubectl scale deployment <name> --replicas=5`
- Sprawdź cache hit rate

### Błędy AI
- Sprawdź limit API
- Sprawdź format promptu
- Zwiększ timeout