# Flight Hunter - Plan implementacji

## Cel MVP

Zbudować lokalną aplikację do wyszukiwania tanich lotów, która:

- generuje kombinacje dat,
- wyszukuje loty przez adapter Google Flights/fli,
- zapisuje wszystkie uruchomienia i wyniki,
- deduplikuje identyczne itinerary,
- śledzi historię cen,
- pokazuje postęp wyszukiwania przez HTMX,
- nie wysyła alertów dla niezweryfikowanych ofert,
- umożliwia późniejszą rozbudowę o weryfikację linii lotniczych.

Najważniejsza reguła:

> Oferta może być uznana za poprawną i alertowalną wyłącznie wtedy, gdy ma status `VERIFIED` oraz `SINGLE_TICKET`.

---

## Aktualny stan

### Działa

- FastAPI i podstawowy interfejs Jinja2.
- Generowanie kombinacji dat.
- Adapter discovery dla `fli`.
- Rate limiting providera.
- Deduplikacja ofert w ramach jednego runu.
- Asynchroniczne uruchamianie wyszukiwania.
- Progress polling przez HTMX.
- Podstawowy Telegram provider.
- Podstawowa ochrona przed duplikowaniem alertów.
- Konfiguracja harmonogramu `manual`/`daily`.
- Testy jednostkowe dat i reguł.
- Ruff, kompilacja i obecne testy przechodzą.

### Nadal brakuje

- Faktycznego wywołania verifiera.
- Obsługi `MAX_OFFERS_TO_VERIFY`.
- Trwałej deduplikacji między runami.
- Działającej historii cen tego samego itinerary.
- Migracji Alembic.
- Uruchamiania schedulera w lifespanie aplikacji.
- Tabel lotnisk i grup lotnisk.
- Struktur błędów providera.
- Pełnych routerów API.
- Testów integracyjnych całego pipeline’u.

---

# Etap 1: Ustabilizowanie pipeline'u wyszukiwania

## Zadania

- [ ] Utrzymać `app/services/search_engine.py` jako jedyne miejsce wykonujące search.
- [ ] Usunąć pozostałą logikę biznesową z `app/main.py`.
- [ ] Zachować uruchamianie przez `enqueue_run()`.
- [ ] Dodać jawny lifecycle runu:
  - [ ] `running`
  - [ ] `completed`
  - [ ] `failed`
- [ ] Zapisywać `started_at` i `finished_at`.
- [ ] Zapisywać `current_query`.
- [ ] Kontynuować run po błędzie pojedynczej kombinacji.
- [ ] Zapisywać błędy providera bez przerywania całego wyszukiwania.
- [ ] Aktualizować `combinations_checked` po każdej próbie.
- [ ] Aktualizować `offers_found` po discovery.
- [ ] Aktualizować `offers_verified` po verification.

## Docelowy przepływ

```text
create search
    |
enqueue run
    |
generate date combinations
    |
discovery
    |
normalize
    |
deduplicate
    |
persist or update itinerary
    |
select cheapest candidates
    |
verify up to MAX_OFFERS_TO_VERIFY
    |
update verification status
    |
record price history
    |
check alert rules
    |
send notification
    |
complete run
```

## Kryterium ukończenia

- UI i scheduler korzystają z tego samego pipeline'u.
- Jeden błąd providera nie kończy runu.
- Każdy run ma poprawne statystyki i status.

---

# Etap 2: Verification service

## Zadania

- [ ] Zaimplementować `app/services/verifier.py`.
- [ ] Dodać wybór najtańszych ofert do weryfikacji.
- [ ] Ograniczyć liczbę weryfikowanych ofert przez `settings.max_offers_to_verify`.
- [ ] Dodać registry verifierów.
- [ ] Wybrać verifiera na podstawie linii marketingowej.
- [ ] Obsłużyć brak verifiera jako `UNKNOWN`.
- [ ] Obsłużyć błąd verifiera jako `ERROR`.
- [ ] Zapisać `ticket_type`.
- [ ] Zapisać `verification_status`.
- [ ] Zapisać `booking_source`.
- [ ] Aktualizować `booking_url`, jeżeli verifier dostarczy lepszy link.
- [ ] Nie traktować `UNKNOWN` jako sukcesu.
- [ ] Nie uznawać wszystkich segmentów tej samej linii za warunek poprawności.

## Statusy

```text
DISCOVERED
VERIFIED
REJECTED
UNKNOWN
ERROR
```

## Typy biletów

```text
SINGLE_TICKET
SELF_TRANSFER
UNKNOWN
```

## Kryterium ukończenia

- Verification jest wywoływane po discovery.
- Maksymalnie `MAX_OFFERS_TO_VERIFY` ofert jest weryfikowanych.
- Brak danych weryfikacyjnych kończy się statusem `UNKNOWN`.
- Nie ma fałszywego `VERIFIED`.

---

# Etap 3: Reguły alertów

## Zadania

- [ ] Wywoływać `notify_if_eligible()` dopiero po verification.
- [ ] Sprawdzać wszystkie warunki:
  - [ ] cena <= target price,
  - [ ] `ticket_type == SINGLE_TICKET`,
  - [ ] `verification_status == VERIFIED`,
  - [ ] liczba przesiadek <= `max_stops`.
- [ ] Nie wysyłać alertu dla `UNKNOWN`.
- [ ] Nie wysyłać alertu dla `SELF_TRANSFER`.
- [ ] Nie zapisywać notyfikacji przed udaną wysyłką.
- [ ] Obsłużyć błąd Telegrama bez oznaczania alertu jako wysłanego.
- [ ] Zachować unikalność:
  - [ ] `flight_offer_id`
  - [ ] `notification_type`
  - [ ] `price`

## Kryterium ukończenia

Tylko zweryfikowana oferta single-ticket może wygenerować alert.

---

# Etap 4: Trwała deduplikacja i historia cen

## Zadania

- [ ] Rozszerzyć `itinerary_key()`.
- [ ] Uwzględnić w identity:
  - [ ] origin,
  - [ ] destination,
  - [ ] departure timestamp,
  - [ ] arrival timestamp,
  - [ ] segmenty,
  - [ ] flight numbers,
  - [ ] marketing airlines,
  - [ ] operating airlines,
  - [ ] lotniska segmentów.
- [ ] Nie uwzględniać ceny w identity.
- [ ] Dodać lookup istniejącego itinerary po `identity_key`.
- [ ] Aktualizować istniejący `FlightOffer`.
- [ ] Dodawać nowy rekord `PriceHistory` przy każdym sprawdzeniu.
- [ ] Aktualizować `last_seen_at`.
- [ ] Zachować `first_seen_at`.
- [ ] Nie tworzyć nowego `FlightOffer` przy każdej zmianie ceny.
- [ ] Zachować relację do aktualnego `SearchRun`.

## Kryterium ukończenia

Ten sam lot znaleziony w kilku runach ma:

- jeden rekord itinerary,
- wiele rekordów historii ceny,
- poprawne informacje o pierwszym i ostatnim wykryciu.

---

# Etap 5: Model danych i Alembic

## Zadania

- [ ] Dodać `alembic.ini`.
- [ ] Dodać `alembic/env.py`.
- [ ] Utworzyć katalog rewizji.
- [ ] Przygotować pierwszą migrację.
- [ ] Usunąć `Base.metadata.create_all()` z lifespanu.
- [ ] Zmienić `make migrate` na `alembic upgrade head`.
- [ ] Dodać `updated_at` do `Search`.
- [ ] Dodać `last_seen_at` do `FlightOffer`.
- [ ] Dodać `booking_source`.
- [ ] Dodać zagregowane marketing airlines.
- [ ] Dodać zagregowane operating airlines.
- [ ] Dodać strukturalne błędy providera.
- [ ] Dodać indeks dla `identity_key`.
- [ ] Dodać indeksy dla historii cen i runów.

## Tabele lotnisk

- [ ] Dodać `airports`.
- [ ] Dodać `airport_groups`.
- [ ] Dodać `airport_group_members`.
- [ ] Dodać grupę `TYO`:
  - [ ] `HND`
  - [ ] `NRT`
- [ ] Rozwiązywać grupę na konkretne lotniska przed zapisem ofert.
- [ ] Zapisywać konkretny airport w `FlightOffer`.

## Kryterium ukończenia

Nowa instalacja działa wyłącznie przez migracje i tworzy kompletny schemat SQLite.

---

# Etap 6: Provider i normalizacja

## Zadania

- [ ] Utworzyć wspólny normalizer ofert.
- [ ] Normalizować kody IATA do uppercase.
- [ ] Normalizować walutę.
- [ ] Walidować kompletność segmentów.
- [ ] Walidować daty i czasy.
- [ ] Rozdzielać segmenty outbound/return.
- [ ] Zapisywać konkretne lotniska.
- [ ] Zachować marketing airline i operating airline.
- [ ] Zachować informację o self-transferze.
- [ ] Dodać mock discovery provider.
- [ ] Dodać fixture z:
  - [ ] poprawnym itinerary,
  - [ ] self-transfer,
  - [ ] wieloma liniami na jednym bilecie,
  - [ ] błędem providera.
- [ ] Ustrukturyzować błędy:
  - [ ] provider,
  - [ ] query,
  - [ ] timestamp,
  - [ ] HTTP status,
  - [ ] error type,
  - [ ] error message.
- [ ] Nie zapisywać cookies, tokenów ani danych wrażliwych.

## Kryterium ukończenia

Pipeline można testować bez połączenia z Google Flights.

---

# Etap 7: Scheduler

## Zadania

- [ ] Uruchamiać scheduler w lifespanie.
- [ ] Zatrzymywać scheduler przy zamykaniu aplikacji.
- [ ] Rejestrować aktywne wyszukiwania `daily`.
- [ ] Usuwać joby nieaktywne lub usunięte.
- [ ] Ustawić `max_instances=1`.
- [ ] Ustawić `coalesce=True`.
- [ ] Nie uruchamiać drugiego runu tego samego searcha.
- [ ] Zachować obsługę ręcznego uruchamiania.
- [ ] Dodać konfigurację godziny uruchomienia.

## Kryterium ukończenia

Aktywne wyszukiwanie z harmonogramem `daily` wykonuje się raz dziennie.

---

# Etap 8: API

## Zadania

- [ ] Przenieść endpointy z `main.py` do routerów.
- [ ] Uzupełnić `app/api/searches.py`.
- [ ] Uzupełnić `app/api/flights.py`.
- [ ] Uzupełnić `app/api/history.py`.
- [ ] Uzupełnić `app/api/health.py`.
- [ ] Dołączyć routery przez `app.include_router()`.
- [ ] Dodać endpoint tworzenia searcha.
- [ ] Dodać endpoint listowania searchów.
- [ ] Dodać endpoint aktywacji/dezaktywacji.
- [ ] Dodać endpoint uruchamiania runu.
- [ ] Dodać endpoint postępu.
- [ ] Dodać endpoint wyników.
- [ ] Dodać endpoint szczegółów lotu.
- [ ] Dodać endpoint historii.
- [ ] Ujednolicić format odpowiedzi:
  - [ ] `{status, data}`
  - [ ] `{status, error}`

## Kryterium ukończenia

Logika HTTP jest oddzielona od logiki domenowej i search engine.

---

# Etap 9: Frontend

## Zadania

- [ ] Zachować prosty layout Jinja2 + HTMX.
- [ ] Dokończyć kartę lotu.
- [ ] Dodać komponent statusu.
- [ ] Dodać osobny status dla:
  - [ ] verified,
  - [ ] unknown,
  - [ ] rejected,
  - [ ] error.
- [ ] Pokazywać `BELOW TARGET` tylko dla ofert spełniających regułę alertu.
- [ ] Dodać szczegóły wszystkich segmentów.
- [ ] Dodać link do booking source.
- [ ] Dodać sortowanie:
  - [ ] cena,
  - [ ] czas podróży,
  - [ ] data wylotu,
  - [ ] liczba przesiadek.
- [ ] Dodać filtry historii:
  - [ ] linia,
  - [ ] data,
  - [ ] cena,
  - [ ] status,
  - [ ] liczba przesiadek.
- [ ] Dodać informację o błędach runu.
- [ ] Dodać widok historii runów.
- [ ] Dodać widok ustawień.
- [ ] Sprawdzić widok desktop i mobile.

## Kryterium ukończenia

Użytkownik może utworzyć search, obserwować postęp, zobaczyć wyniki i przejść do historii bez ręcznego odświeżania.

---

# Etap 10: Testy

## Testy jednostkowe

- [ ] Generowanie kombinacji dat.
- [ ] Reguły `is_alertable`.
- [ ] Reguła single-ticket.
- [ ] Budowanie identity key.
- [ ] Deduplikacja.
- [ ] Normalizacja ofert.
- [ ] Formatowanie cen i czasu.

## Testy integracyjne

- [ ] Pełny run z mock providerem.
- [ ] Kontynuacja po błędzie jednej kombinacji.
- [ ] Zapis SearchRun.
- [ ] Zapis FlightOffer.
- [ ] Zapis segmentów.
- [ ] Zapis PriceHistory.
- [ ] Aktualizacja istniejącego itinerary.
- [ ] Weryfikacja maksymalnie N ofert.
- [ ] Aktualizacja statusów.
- [ ] Polling postępu.
- [ ] Scheduler.
- [ ] Migracje.

## Testy powiadomień

- [ ] `UNKNOWN` nie wysyła alertu.
- [ ] `SELF_TRANSFER` nie wysyła alertu.
- [ ] Cena powyżej targetu nie wysyła alertu.
- [ ] Zbyt duża liczba przesiadek nie wysyła alertu.
- [ ] `VERIFIED + SINGLE_TICKET` wysyła alert.
- [ ] Ten sam alert nie jest wysyłany dwa razy.
- [ ] Błąd Telegrama nie tworzy rekordu wysłanej notyfikacji.

---

# Definition of Done

Projekt można uznać za gotowy do MVP, gdy:

- [ ] `make test` przechodzi.
- [ ] `make lint` przechodzi.
- [ ] `make migrate` działa na pustej bazie.
- [ ] Search można uruchomić ręcznie.
- [ ] Search można uruchomić ponownie bez duplikowania itinerary.
- [ ] Historia cen jest zachowywana.
- [ ] Błąd providera nie kończy całego runu.
- [ ] Postęp jest widoczny przez HTMX.
- [ ] Scheduler daily działa.
- [ ] `UNKNOWN` nigdy nie powoduje alertu.
- [ ] `SELF_TRANSFER` nigdy nie powoduje alertu.
- [ ] Alert może powstać tylko dla `VERIFIED + SINGLE_TICKET`.
- [ ] Telegram nie zapisuje tokenów w bazie.
- [ ] Aplikacja działa bez płatnego API.
- [ ] Mock provider pozwala uruchomić testy bez Google Flights.
