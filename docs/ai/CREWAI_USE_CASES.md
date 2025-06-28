# CrewAI dla ZGDK - Praktyczne Zastosowania

## Gdzie CrewAI się przyda w ZGDK?

### 1. **Team Management Crew** 🎯
Zarządzanie drużynami to skomplikowany proces - idealny dla CrewAI!

```python
# core/ai/crews/team_management_crew.py
from crewai import Agent, Task, Crew
from typing import List, Dict

class TeamManagementCrew:
    """Crew do zarządzania drużynami premium."""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Agent 1: Walidator uprawnień
        self.permission_validator = Agent(
            role="Walidator Uprawnień Drużyny",
            goal="Sprawdzić czy użytkownik może wykonać akcję w drużynie",
            backstory="""Jestem ekspertem od systemu rang premium i uprawnień drużynowych.
            Znam wszystkie zasady: kto może zapraszać, wyrzucać, zmieniać kolor.""",
            tools=[
                CheckPremiumRole(),
                CheckTeamOwnership(),
                CheckTeamMemberLimit()
            ],
            verbose=True
        )
        
        # Agent 2: Manager składu
        self.roster_manager = Agent(
            role="Manager Składu Drużyny",
            goal="Zarządzać członkami drużyny, dodawać i usuwać graczy",
            backstory="""Specjalizuję się w optymalnym składzie drużyn.
            Pilnuję limitów, rang i hierarchii w zespole.""",
            tools=[
                AddTeamMember(),
                RemoveTeamMember(),
                UpdateTeamRoles(),
                CheckMemberActivity()
            ]
        )
        
        # Agent 3: Komunikator
        self.team_communicator = Agent(
            role="Komunikator Drużynowy",
            goal="Informować członków drużyny o zmianach",
            backstory="""Jestem mistrzem komunikacji po polsku.
            Wysyłam powiadomienia, podsumowania i ogłoszenia drużynowe.""",
            tools=[
                SendDiscordMessage(),
                CreateTeamAnnouncement(),
                GenerateTeamSummary()
            ]
        )
        
        # Agent 4: Analityk drużyny
        self.team_analyst = Agent(
            role="Analityk Drużynowy",
            goal="Analizować aktywność i wydajność drużyny",
            backstory="""Analizuję statystyki, aktywność i zaangażowanie.
            Pomagam liderom podejmować decyzje o składzie.""",
            tools=[
                AnalyzeTeamActivity(),
                GenerateActivityReport(),
                SuggestImprovements()
            ]
        )
    
    def create_team_action_crew(self, action: str) -> Crew:
        """Stwórz crew dla konkretnej akcji drużynowej."""
        
        if action == "add_member":
            return Crew(
                agents=[
                    self.permission_validator,
                    self.roster_manager,
                    self.team_communicator
                ],
                tasks=[
                    Task(
                        description="Sprawdź czy lider może dodać nowego członka",
                        agent=self.permission_validator
                    ),
                    Task(
                        description="Dodaj członka do drużyny jeśli jest miejsce",
                        agent=self.roster_manager
                    ),
                    Task(
                        description="Wyślij powiadomienie o nowym członku",
                        agent=self.team_communicator
                    )
                ],
                verbose=True
            )
        
        elif action == "monthly_review":
            return Crew(
                agents=[
                    self.team_analyst,
                    self.roster_manager,
                    self.team_communicator
                ],
                tasks=[
                    Task(
                        description="Przeanalizuj miesięczną aktywność drużyny",
                        agent=self.team_analyst
                    ),
                    Task(
                        description="Zasugeruj zmiany w składzie na podstawie aktywności",
                        agent=self.roster_manager
                    ),
                    Task(
                        description="Wyślij miesięczne podsumowanie do lidera",
                        agent=self.team_communicator
                    )
                ]
            )
```

### 2. **Shop Purchase Decision Crew** 💰
Złożony proces decyzyjny przy zakupie/upgrade rang:

```python
# core/ai/crews/shop_crew.py
class ShopPurchaseCrew:
    """Crew do obsługi skomplikowanych zakupów w sklepie."""
    
    def __init__(self):
        # Agent 1: Doradca zakupowy
        self.purchase_advisor = Agent(
            role="Doradca Zakupowy Premium",
            goal="Doradzić najlepszą opcję zakupu dla użytkownika",
            backstory="""Znam wszystkie rangi premium, ich benefity i ceny.
            Pomagam użytkownikom wybrać najlepszą opcję dla ich potrzeb.""",
            tools=[
                CompareRoles(),
                CalculateSavings(),
                CheckUserNeeds()
            ]
        )
        
        # Agent 2: Kalkulator finansowy
        self.financial_calculator = Agent(
            role="Kalkulator Finansowy",
            goal="Obliczyć koszty, zwroty i oszczędności",
            backstory="""Jestem ekspertem od matematyki finansowej.
            Liczę zwroty za upgrade, proration, najlepsze deale.""",
            tools=[
                CalculateRefund(),
                CalculateProration(),
                ComparePrices()
            ]
        )
        
        # Agent 3: Negocjator benefitów
        self.benefit_negotiator = Agent(
            role="Negocjator Benefitów",
            goal="Maksymalizować korzyści dla użytkownika",
            backstory="""Znajduję najlepsze kombinacje rang i okresów.
            Negocjuję dodatkowe benefity dla lojalnych klientów.""",
            tools=[
                CheckLoyaltyStatus(),
                FindBestDeal(),
                SuggestBundles()
            ]
        )
    
    async def advise_purchase(self, user_data: Dict) -> Dict:
        """Doradź użytkownikowi najlepszy zakup."""
        crew = Crew(
            agents=[
                self.purchase_advisor,
                self.financial_calculator,
                self.benefit_negotiator
            ],
            tasks=[
                Task(
                    description=f"Przeanalizuj potrzeby użytkownika: {user_data}",
                    agent=self.purchase_advisor
                ),
                Task(
                    description="Oblicz wszystkie opcje finansowe",
                    agent=self.financial_calculator
                ),
                Task(
                    description="Znajdź najlepszą ofertę z dodatkowymi benefitami",
                    agent=self.benefit_negotiator
                )
            ]
        )
        
        result = await crew.kickoff()
        return result
```

### 3. **Moderation Investigation Crew** 🔍
Dla skomplikowanych przypadków moderacji:

```python
# core/ai/crews/moderation_crew.py
class ModerationInvestigationCrew:
    """Crew do głębokiej analizy skomplikowanych przypadków."""
    
    def __init__(self):
        # Agent 1: Detektyw
        self.detective = Agent(
            role="Detektyw Moderacyjny",
            goal="Zbadać kontekst i historię użytkownika",
            backstory="""Jestem ekspertem od wykrywania wzorców nadużyć.
            Badam historię, kontekst i powiązania między użytkownikami.""",
            tools=[
                SearchMessageHistory(),
                AnalyzeUserPatterns(),
                CheckAltAccounts()
            ]
        )
        
        # Agent 2: Sędzia
        self.judge = Agent(
            role="Sędzia Społeczności",
            goal="Wydać sprawiedliwy wyrok na podstawie dowodów",
            backstory="""Jestem bezstronnym sędzią, kieruję się zasadami serwera.
            Wydaję wyroki proporcjonalne do przewinienia.""",
            tools=[
                EvaluateEvidence(),
                CheckServerRules(),
                DetermineAppropriatePunishment()
            ]
        )
        
        # Agent 3: Mediator
        self.mediator = Agent(
            role="Mediator Konfliktów",
            goal="Rozwiązać konflikty między użytkownikami",
            backstory="""Specjalizuję się w deeskalacji i mediacji.
            Pomagam znaleźć rozwiązania satysfakcjonujące obie strony.""",
            tools=[
                AnalyzeConflict(),
                SuggestResolution(),
                CreatePeaceAgreement()
            ]
        )
```

### 4. **Event Planning Crew** 🎉
Do organizacji eventów na serwerze:

```python
# core/ai/crews/event_crew.py
class EventPlanningCrew:
    """Crew do planowania i realizacji eventów."""
    
    def __init__(self):
        # Agent 1: Planista eventów
        self.event_planner = Agent(
            role="Planista Eventów Discord",
            goal="Zaplanować angażujące eventy dla społeczności",
            backstory="""Tworzę niezapomniane eventy na Discordzie.
            Znam polską społeczność i wiem co ją interesuje."""
        )
        
        # Agent 2: Koordynator nagród
        self.reward_coordinator = Agent(
            role="Koordynator Nagród",
            goal="Zarządzać nagrodami i motywować uczestników",
            backstory="""Dbam o atrakcyjne nagrody i sprawiedliwą dystrybucję.
            Motywuję społeczność do aktywnego uczestnictwa."""
        )
        
        # Agent 3: Promotor
        self.event_promoter = Agent(
            role="Promotor Eventów",
            goal="Wypromować event i przyciągnąć uczestników",
            backstory="""Jestem mistrzem promocji na Discordzie.
            Tworzę FOMO i ekscytację wokół eventów."""
        )
```

## Praktyczny Przykład Użycia

```python
# cogs/commands/team/team_ai.py
from discord.ext import commands
from core.ai.crews.team_management_crew import TeamManagementCrew

class TeamAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.team_crew = TeamManagementCrew(bot)
    
    @commands.hybrid_command(name="team_add_smart")
    async def smart_add_member(self, ctx, member: discord.Member):
        """Inteligentnie dodaj członka do drużyny."""
        # Uruchom CrewAI
        crew = self.team_crew.create_team_action_crew("add_member")
        
        # Przekaż kontekst
        context = {
            "leader": ctx.author,
            "new_member": member,
            "team_data": await self.get_team_data(ctx.author)
        }
        
        # Crew wykona:
        # 1. Sprawdzi uprawnienia lidera
        # 2. Sprawdzi limity drużyny
        # 3. Doda członka jeśli wszystko OK
        # 4. Wyśle powiadomienia
        result = await crew.kickoff_async(inputs=context)
        
        # Wyświetl rezultat
        embed = self.create_result_embed(result)
        await ctx.send(embed=embed)
```

## Kiedy CrewAI się opłaca?

### ✅ Używaj CrewAI gdy:
1. **Wiele kroków decyzyjnych** - np. upgrade rangi z refundem
2. **Potrzebna współpraca** - różne aspekty tego samego problemu
3. **Złożona logika biznesowa** - np. kalkulacje zespołów
4. **Potrzebny "human touch"** - naturalne odpowiedzi po polsku

### ❌ NIE używaj CrewAI gdy:
1. **Prosta logika** - if/else wystarczy
2. **Real-time wymagane** - CrewAI może być wolne
3. **Wysokie volume** - każdy agent = wywołanie AI = koszt

## Koszty CrewAI z Gemini

```python
# Przykładowe koszty
# Crew z 3 agentami, 3 zadania = ~6-9 wywołań AI

# Z Gemini (1M tokenów free):
- 1 wywołanie crew = ~3k tokenów
- Darmowe: ~300 wywołań crew/miesiąc
- Potem: ~$0.0015 per wywołanie

# Dla ZGDK (przykład):
- 10 upgrade'ów rang dziennie = 300/miesiąc
- 5 analiz drużyn dziennie = 150/miesiąc
- Total: 450 wywołań = MIEŚCI SIĘ W DARMOWYM! ✅
```

## Rekomendacja dla ZGDK

**TAK, CrewAI się przyda**, ale używaj mądrze:

1. **Team Management** - idealne dla CrewAI ✅
2. **Complex Shop Decisions** - bardzo dobre ✅
3. **Moderation** - tylko trudne przypadki ✅
4. **Daily Operations** - NIE, za drogie ❌

**Najlepsze podejście:**
```python
# Hybrid: Simple logic + CrewAI dla złożonych
if is_simple_purchase(request):
    # Zwykła logika
    return process_simple_purchase()
else:
    # CrewAI dla skomplikowanych przypadków
    return await shop_crew.advise_purchase(request)
```

Z Gemini będzie **praktycznie darmowe** dla typowego użycia! 🎉