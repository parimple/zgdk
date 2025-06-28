# Current Task: task-001

## Naprawić błąd w komendzie ranking/stats

### Problem
Komenda `/ranking` i `/top` zwracają błąd: "Wystąpił błąd podczas pobierania rankingu"

### Analiza
1. Activity service prawdopodobnie nie jest poprawnie wstrzykiwany
2. Service manager może nie mieć zarejestrowanego ActivityTrackingService
3. Możliwy problem z implementacją get_leaderboard

### Plan działania
1. Sprawdzić czy ActivityTrackingService jest zarejestrowany w service_manager
2. Debugować gdzie dokładnie występuje błąd
3. Naprawić implementację
4. Przetestować komendę