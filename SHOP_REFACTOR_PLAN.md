# Plan refaktoryzacji ShopCog

## Obecna struktura

Aktualnie `ShopCog` zawiera mieszaninę logiki prezentacji, logiki biznesowej i dostępu do danych:

```python
class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="shop")
    async def shop(self, ctx: Context, member: discord.Member = None):
        viewer = ctx.author
        target_member = member or viewer

        # Bezpośredni dostęp do bazy danych
        async with self.bot.get_db() as session:
            db_viewer = await MemberQueries.get_or_add_member(session, viewer.id)
            balance = db_viewer.wallet_balance
            premium_roles = await RoleQueries.get_member_premium_roles(session, target_member.id)
            await session.commit()

        # Logika prezentacji
        view = RoleShopView(...)
        embed = await create_shop_embed(...)
        await ctx.reply(embed=embed, view=view, mention_author=False)
```

## Docelowa struktura

Chcemy zaimplementować strukturę warstwową:

1. **Warstwa prezentacji (ShopCog)** - komenda Discord
2. **Warstwa usług (ShopService)** - koordynacja i obsługa błędów
3. **Warstwa domeny (ShopManager)** - logika biznesowa
4. **Warstwa dostępu do danych** - istniejące klasy MemberQueries, RoleQueries, itd.

## Kroki refaktoryzacji

### 1. Utworzenie ShopManager

```python
# domain/managers/shop_manager.py
class ShopManager:
    def __init__(self, bot):
        self.bot = bot
    
    async def get_shop_data(self, viewer_id: int, target_member_id: int) -> Dict[str, Any]:
        """Pobiera dane sklepu, w tym saldo i role premium."""
        async with self.bot.get_db() as session:
            db_viewer = await MemberQueries.get_or_add_member(session, viewer_id)
            balance = db_viewer.wallet_balance
            premium_roles = await RoleQueries.get_member_premium_roles(session, target_member_id)
            await session.commit()
        
        return {
            "balance": balance,
            "premium_roles": premium_roles,
        }
    
    # Inne metody biznesowe...
```

### 2. Utworzenie ShopService

```python
# services/shop_service.py
class ShopService:
    def __init__(self, bot):
        self.bot = bot
        self.shop_manager = ShopManager(bot)
    
    async def get_shop_data(self, viewer_id: int, target_member_id: int) -> Dict[str, Any]:
        """Pobiera dane sklepu."""
        return await self.shop_manager.get_shop_data(viewer_id, target_member_id)
    
    # Obsługa błędów i koordynacja...
```

### 3. Refaktoryzacja ShopCog

```python
# cogs/commands/shop.py (później presentation/commands/shop.py)
class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.shop_service = ShopService(bot)

    @commands.hybrid_command(name="shop")
    async def shop(self, ctx: Context, member: discord.Member = None):
        viewer = ctx.author
        target_member = member or viewer
        
        # Użycie serwisu zamiast bezpośredniego dostępu do bazy
        shop_data = await self.shop_service.get_shop_data(viewer.id, target_member.id)
        
        # Prezentacja
        view = RoleShopView(
            ctx,
            self.bot,
            self.bot.config["premium_roles"],
            shop_data["balance"],
            page=1,
            viewer=viewer,
            member=target_member,
        )
        
        embed = await create_shop_embed(
            ctx,
            shop_data["balance"],
            view.role_price_map,
            shop_data["premium_roles"],
            page=1,
            viewer=viewer,
            member=target_member,
        )
        
        await ctx.reply(embed=embed, view=view, mention_author=False)
```

## Zalety tego podejścia

1. **Lepsza separacja odpowiedzialności**
   - ShopCog: obsługa komend i formatowanie odpowiedzi
   - ShopService: koordynacja operacji i obsługa błędów
   - ShopManager: logika biznesowa
   - Queries: dostęp do bazy danych

2. **Łatwiejsze testowanie**
   - Każda warstwa może być testowana niezależnie
   - Możliwość mockowania zależności

3. **Zwiększona reużywalność**
   - ShopService i ShopManager mogą być używane przez inne komponenty
   - Wspólne wzorce obsługi błędów

4. **Łatwiejsza rozbudowa**
   - Nowe funkcje można dodawać bez modyfikacji istniejących komponentów
   - Jasna struktura dla nowych deweloperów

## Strategia wdrożenia

1. Utworzyć nowe komponenty bez usuwania istniejących
2. Zrefaktoryzować ShopCog do korzystania z nowych komponentów
3. Sprawdzić czy wszystko działa
4. Powtórzyć proces dla innych komponentów

## Metryki sukcesu

1. **Pokrycie testami**: zwiększenie pokrycia testami
2. **Duplikacja kodu**: zmniejszenie duplikacji kodu
3. **Złożoność cyklomatyczna**: zmniejszenie złożoności metod
4. **Długość metod**: zmniejszenie średniej długości metod