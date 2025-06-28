# Dokument Wymagań Produktowych - Refaktoryzacja Bota zaGadka

## Przegląd
Kompletna refaktoryzacja bota Discord zaGadka w celu poprawy jakości kodu, łatwości utrzymania i niezawodności.

## Obecny Stan
- Bot działa, ale ma dług techniczny
- Mieszane wzorce architektury (klasy narzędziowe vs serwisy)
- Niektóre komendy mają błędy (ranking, statystyki)
- System powiadomień o bumpach wymaga naprawy
- Organizacja kodu mogłaby być lepsza

## Cele
1. **Dokończenie Migracji do Architektury Serwisowej**
   - Migracja wszystkich klas narzędziowych do serwisów opartych na Protocol
   - Implementacja właściwego wstrzykiwania zależności
   - Użycie wzorca Unit of Work dla transakcji bazodanowych

2. **Naprawa Wszystkich Błędów w Komendach**
   - Naprawa komend ranking/stats (problemy z serwisem aktywności)
   - Naprawa komend team (brak odpowiedzi)
   - Zapewnienie, że wszystkie komendy działają poprawnie

3. **Ulepszenie Systemu Bumpów**
   - Naprawa wiadomości powiadomień po bumpach
   - Właściwa obsługa cooldownów
   - Wyświetlanie właściwych emoji z konfiguracji

4. **Organizacja Kodu**
   - Podział dużych plików na mniejsze moduły
   - Grupowanie powiązanej funkcjonalności
   - Poprawa konwencji nazewnictwa

5. **Testowanie i Dokumentacja**
   - Dokładne testowanie wszystkich komend
   - Dokumentowanie skomplikowanych systemów
   - Dodanie testów integracyjnych

## Wymagania Techniczne

### Architektura
- Użycie interfejsów Protocol dla wszystkich serwisów
- Implementacja wstrzykiwania zależności
- Użycie asynchronicznych menedżerów kontekstu dla sesji bazodanowych
- Przestrzeganie zasad SOLID

### Baza Danych
- Użycie wzorca repozytorium dla wszystkich operacji bazodanowych
- Implementacja właściwej obsługi błędów
- Użycie transakcji dla spójności danych

### Komendy
- Wszystkie komendy muszą obsługiwać błędy elegancko
- Dostarczanie przyjaznych użytkownikowi komunikatów o błędach
- Wsparcie zarówno dla komend slash jak i tekstowych

### Wydajność
- Optymalizacja zapytań do bazy danych
- Użycie cache'owania gdzie to odpowiednie
- Właściwa obsługa limitów rate

## Kryteria Sukcesu
- [ ] Wszystkie komendy działają bez błędów
- [ ] Powiadomienia o bumpach pojawiają się po udanych bumpach
- [ ] Architektura serwisowa jest spójna w całym projekcie
- [ ] Kod jest dobrze zorganizowany i łatwy w utrzymaniu
- [ ] Wszystkie testy przechodzą

## Obecne Problemy do Naprawy
1. Serwis aktywności nie działa w komendach ranking/stats
2. Handlery bumpów nie wysyłają wiadomości gratulacyjnych
3. Komendy team nie odpowiadają
4. Brakuje niektórych polskich aliasów
5. Obsługa błędów wymaga poprawy

## Kolejność Priorytetów
1. Naprawienie krytycznych błędów w komendach (Wysoki)
2. Dokończenie migracji architektury serwisowej (Średni)
3. Poprawa organizacji kodu (Średni)
4. Dodanie brakujących funkcji (Niski)
5. Dokumentacja i testy (Niski)

## Zadania do Wykonania

### 🔴 Pilne (Dziś)
1. Naprawić błąd w komendzie ranking/stats
2. Naprawić brak wiadomości po bumpie
3. Sprawdzić dlaczego team commands nie działają

### 🟡 Ważne (Ten tydzień)
1. Dokończyć migrację do architektury serwisowej
2. Podzielić duże pliki na mniejsze moduły
3. Dodać brakujące polskie aliasy do komend

### 🟢 Dodatkowe (Później)
1. Dodać więcej testów integracyjnych
2. Napisać dokumentację dla skomplikowanych systemów
3. Zoptymalizować zapytania do bazy danych