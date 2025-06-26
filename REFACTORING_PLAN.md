# Plan Refaktoryzacji Models i Queries

## Problem
- `datasources/models.py` - 292 linie, wszystkie modele w jednym pliku
- `datasources/queries.py` - **1721 linii**, 9 klas query w jednym pliku
- Trudna nawigacja, maintenance i współpraca nad kodem

## Plan Reorganizacji

### 1. Models - Podział na domeny

```
datasources/models/
├── __init__.py          # Eksport wszystkich modeli
├── member_models.py     # Member, MemberRole
├── activity_models.py   # Activity  
├── role_models.py       # Role
├── payment_models.py    # HandledPayment
├── channel_models.py    # ChannelPermission
├── notification_models.py # NotificationLog
├── message_models.py    # Message
├── invite_models.py     # Invite
├── moderation_models.py # AutoKick, ModerationLog
└── base.py             # Base, constants
```

### 2. Queries - Podział na pliki

```
datasources/queries/
├── __init__.py              # Eksport wszystkich queries
├── member_queries.py        # MemberQueries (33-190)
├── role_queries.py          # RoleQueries (191-604) 
├── payment_queries.py       # HandledPaymentQueries (605-678)
├── channel_queries.py       # ChannelPermissionQueries (679-886)
├── notification_queries.py  # NotificationLogQueries (887-1052)
├── message_queries.py       # MessageQueries (1053-1078)
├── invite_queries.py        # InviteQueries (1079-1299)
├── autokick_queries.py      # AutoKickQueries (1300-1556)
└── moderation_queries.py    # ModerationLogQueries (1557-1721)
```

### 3. Korzyści

#### Przed refaktoryzacją:
- 1 plik models.py (292 linie)
- 1 plik queries.py (1721 linii)
- **Razem: 2013 linii w 2 plikach**

#### Po refaktoryzacji:
- 10 plików models (średnio 30 linii każdy)
- 9 plików queries (średnio 190 linii każdy)
- **Razem: ~2000 linii w 19 plikach**

#### Zalety:
- ✅ Łatwiejsza nawigacja
- ✅ Lepsze git merge conflicts
- ✅ Szybsze wczytywanie w IDE
- ✅ Możliwość równoległej pracy
- ✅ Lepszy podział odpowiedzialności
- ✅ Łatwiejsze testowanie jednostkowe

### 4. Backward Compatibility

Stary kod nadal będzie działać dzięki re-eksportom w `__init__.py`:

```python
# datasources/models/__init__.py
from .member_models import Member, MemberRole
from .activity_models import Activity
# ... itd

# datasources/queries/__init__.py  
from .member_queries import MemberQueries
from .role_queries import RoleQueries
# ... itd
```

### 5. Etapy Implementacji

1. **Etap 1**: Stworzenie struktury folderów
2. **Etap 2**: Migracja models.py 
3. **Etap 3**: Migracja queries.py
4. **Etap 4**: Testowanie i weryfikacja
5. **Etap 5**: Usunięcie starych plików

## Status: READY TO IMPLEMENT ✅