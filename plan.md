Flight Hunter
1. Cel projektu
Zbuduj lokalną aplikację webową “Flight Hunter”, służącą do automatycznego wyszukiwania tanich lotów w zadanym zakresie dat.

Aplikacja ma być przede wszystkim narzędziem osobistym, działającym lokalnie.

Główna funkcja:

Użytkownik podaje:

lotnisko początkowe,
lotnisko docelowe,
najwcześniejszą datę wylotu,
najpóźniejszą datę wylotu,
minimalną liczbę dni podróży,
maksymalną liczbę dni podróży,
najpóźniejszą datę powrotu,
cenę docelową,
maksymalną liczbę przesiadek.
Aplikacja generuje wszystkie możliwe kombinacje dat i sprawdza dostępne loty.

Najważniejsze wymaganie:

Za poprawną ofertę uznajemy wyłącznie itinerary, który można zarezerwować jako jedną podróż/rezerwację, bez self-transferu i bez konieczności kupowania osobnych biletów.

Nie wymagamy, aby wszystkie segmenty były operowane przez tę samą linię.

Przykład poprawny:

LOT WAW → FRA + ANA FRA → HND, jeżeli cały itinerary jest sprzedawany jako jeden bilet.

Przykład niepoprawny:

Ryanair WAW → BER + Air China BER → PEK → TYO jako dwa niezależne bilety.

2. Priorytety
Priorytety projektu:

poprawność wyników,
historia wszystkich sprawdzeń,
możliwość wyszukiwania zakresu dat,
wykrywanie ofert poniżej ceny docelowej,
proste i przejrzyste UI,
możliwość późniejszej rozbudowy o dodatkowych providerów,
brak płatnych API w MVP,
lokalne uruchomienie,
prostota utrzymania.
Nie implementuj systemu rezerwacji.

Aplikacja tylko wyszukuje, zapisuje i linkuje do źródła zakupu.

3. Stack technologiczny
Użyj:

Backend
Python 3.12+
FastAPI
SQLAlchemy 2
Pydantic v2
httpx
APScheduler
Alembic
Database
SQLite w MVP.

Database file:

data/flight_hunter.db

Architektura musi umożliwiać późniejsze przejście na PostgreSQL bez przebudowy modeli domenowych.

Frontend
Nie używaj Reacta w MVP.

Użyj:

Jinja2
HTMX
Tailwind CSS
Tailwind może być używany przez CDN w MVP.

Frontend ma być bardzo prosty, nowoczesny i responsywny.

Desktop + iPhone/mobile.

Flight discovery
Użyj istniejącego open-source providera Google Flights zamiast implementowania reverse-engineered protokołu od zera.

Preferowany adapter:

fli

Jeżeli jego API okaże się niewygodne do integracji jako biblioteka, użyj CLI/subprocess jako warstwy przejściowej.

Alternatywnie:

gfly

Provider musi być opakowany za własnym interfejsem aplikacji.

Nigdy nie uzależniaj reszty aplikacji bezpośrednio od fli/gfly.

4. Ważne ograniczenie providera
Google Flights nie ma publicznego, oficjalnego API.

Provider oparty o reverse engineering jest źródłem zewnętrznym i może przestać działać.

Dlatego:

nie omijaj CAPTCHA,
nie implementuj proxy rotation,
nie implementuj fingerprint spoofingu,
nie implementuj mechanizmów obchodzenia blokad,
stosuj rozsądny rate limit,
błędy providera mają być zapisywane,
aplikacja musi działać poprawnie również wtedy, gdy provider jest czasowo niedostępny.
Nie wykonuj agresywnego scrapingu.

5. Architektura
Utwórz:

flight-hunter/
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── searches.py
│   │   ├── flights.py
│   │   ├── history.py
│   │   └── health.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── dates.py
│   │   ├── money.py
│   │   └── exceptions.py
│   │
│   ├── db/
│   │   ├── database.py
│   │   ├── models.py
│   │   └── repositories/
│   │       ├── searches.py
│   │       ├── runs.py
│   │       ├── flights.py
│   │       └── notifications.py
│   │
│   ├── domain/
│   │   ├── models.py
│   │   ├── enums.py
│   │   └── rules.py
│   │
│   ├── providers/
│   │   ├── base.py
│   │   ├── discovery/
│   │   │   ├── base.py
│   │   │   └── google_flights.py
│   │   └── verification/
│   │       ├── base.py
│   │       └── airline.py
│   │
│   ├── services/
│   │   ├── search_engine.py
│   │   ├── date_generator.py
│   │   ├── normalizer.py
│   │   ├── deduplicator.py
│   │   ├── verifier.py
│   │   ├── price_tracker.py
│   │   └── notification_service.py
│   │
│   ├── scheduler/
│   │   └── scheduler.py
│   │
│   ├── notifications/
│   │   ├── base.py
│   │   └── telegram.py
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── search_form.html
│   │   ├── search_detail.html
│   │   ├── results.html
│   │   ├── history.html
│   │   ├── flight_detail.html
│   │   └── components/
│   │       ├── flight_card.html
│   │       ├── status_badge.html
│   │       ├── price.html
│   │       └── loading.html
│   │
│   └── static/
│       └── app.css
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── data/
│   └── .gitkeep
│
├── alembic/
│
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── Makefile
6. Domain model
Search
Search reprezentuje konfigurację użytkownika.

Pola:

id
name
origin
destination
earliest_departure
latest_departure
min_trip_days
max_trip_days
latest_return
target_price
currency
max_stops
active
created_at
updated_at
last_run_at
Przykład:

name = Japan November 2026

origin = WAW
destination = TYO

earliest_departure = 2026-10-29
latest_departure = 2026-11-01

min_trip_days = 13
max_trip_days = 16

latest_return = 2026-11-16

target_price = 3500
currency = PLN

max_stops = 1
7. Airport groups
Obsługuj dwa rodzaje destination:

pojedyncze lotnisko
HND
grupa lotnisk
TYO
TYO powinno być traktowane jako:

HND
NRT
W UI użytkownik może wpisać:

TYO
i zobaczyć:

Tokyo
HND + NRT
Wewnętrznie zawsze zapisuj konkretne lotniska przy ofercie.

Przygotuj prostą tabelę:

airports
airport_groups
airport_group_members
8. Date generation
Dla:

earliest_departure = 2026-10-29
latest_departure = 2026-11-01

min_trip_days = 13
max_trip_days = 16

latest_return = 2026-11-16
wygeneruj wszystkie kombinacje:

departure = 29.10
return = 11.11
return = 12.11
return = 13.11
return = 14.11

departure = 30.10
return = 12.11
return = 13.11
return = 14.11
return = 15.11

departure = 31.10
return = 13.11
return = 14.11
return = 15.11
return = 16.11

departure = 01.11
return = 14.11
return = 15.11
return = 16.11
Każda kombinacja musi spełniać:

min_trip_days <= trip_days <= max_trip_days
return_date <= latest_return
Nie generuj niepotrzebnych zapytań.

9. Flight provider abstraction
Utwórz:

class FlightDiscoveryProvider(ABC):

    @abstractmethod
    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date,
        currency: str = "PLN",
    ) -> list[RawFlightOffer]:
        ...
Provider nie może zwracać modeli SQLAlchemy.

Ma zwracać własne modele domenowe.

10. RawFlightOffer
Minimalne pola:

provider
provider_offer_id
price
currency

origin
destination

departure
arrival

duration_minutes
stops

segments[]

airlines[]

booking_url

is_self_transfer
Segment:

flight_number
marketing_airline
operating_airline

departure_airport
arrival_airport

departure_time
arrival_time

duration_minutes
11. Flight status
Każda oferta ma:

DISCOVERED
VERIFIED
REJECTED
UNKNOWN
ERROR
Nie wolno traktować UNKNOWN jako poprawnej oferty.

12. Single-ticket requirement
To jest najważniejsza reguła biznesowa.

Dodaj:

ticket_type
z wartościami:

SINGLE_TICKET
SELF_TRANSFER
UNKNOWN
Reguła:

valid_offer = (
    ticket_type == TicketType.SINGLE_TICKET
)
Jeżeli provider nie potrafi potwierdzić ticketingu:

UNKNOWN
Nie wysyłaj alertu.

13. Important distinction
Nie wymagaj:

all segments operated by same airline
Wymagaj:

one ticket / one protected itinerary
Przykład:

LOT + ANA
może być poprawny.

Przykład:

Turkish + Turkish
może być poprawny.

Przykład:

Ryanair + Air China
może być niepoprawny.

14. Discovery vs verification
Rozdziel:

Discovery
od:

Verification
Discovery ma znaleźć kandydatów.

Verification ma potwierdzić:

cenę,
dostępność,
single ticket,
booking source,
dokładną trasę.
Nie próbuj weryfikować każdej znalezionej oferty.

W MVP:

discovery,
deduplication,
sortowanie po cenie,
verification tylko najlepszych kandydatów.
Konfiguracja:

MAX_OFFERS_TO_VERIFY = 10
15. Verification architecture
Utwórz:

class FlightVerificationProvider(ABC):

    @abstractmethod
    async def verify(
        self,
        offer: NormalizedFlightOffer,
    ) -> VerificationResult:
        ...
Na początku implementacja może zwracać:

UNKNOWN
dla źródeł, których nie da się bezpiecznie zweryfikować automatycznie.

Nie udawaj weryfikacji.

Jeżeli bezpośrednia weryfikacja ceny na stronie linii wymaga skomplikowanego browser automation, zostaw ją jako osobny adapter.

16. Airline verification
Przygotuj interfejs:

providers/verification/airline.py
oraz registry:

AIRLINE_VERIFIERS = {
    "TK": TurkishVerifier(),
    "LO": LOTVerifier(),
    "AY": FinnairVerifier(),
}
Nie musisz implementować wszystkich linii w MVP.

Architektura ma jednak pozwalać dodawać kolejne.

17. Database
Użyj SQLAlchemy 2 + Alembic.

searches
id
name
origin
destination
earliest_departure
latest_departure
min_trip_days
max_trip_days
latest_return
target_price
currency
max_stops
active
created_at
updated_at
last_run_at
search_runs
id
search_id
started_at
finished_at
status
combinations_total
combinations_checked
offers_found
offers_verified
errors
flight_offers
id
search_run_id

departure_date
return_date
trip_days

origin
destination

airline
marketing_airlines
operating_airlines

price
currency

total_duration_minutes
stops
stop_airports

ticket_type
verification_status

booking_source
booking_url

provider
provider_offer_id

first_seen_at
last_seen_at
flight_segments
id
flight_offer_id
segment_number

flight_number

marketing_airline
operating_airline

departure_airport
arrival_airport

departure_time
arrival_time

duration_minutes
price_history
id
flight_offer_id
price
currency
checked_at
notifications
id
flight_offer_id
notification_type
price
sent_at
Uniqueness:

flight_offer_id + notification_type + price
Nie wysyłaj identycznego alertu wielokrotnie.

18. History
Każde uruchomienie wyszukiwania musi być zapisane.

Nie usuwaj starych wyników.

Historia ma umożliwiać:

Search
  ↓
Run #1
  ↓
Run #2
  ↓
Run #3
  ↓
Run #4
oraz:

flight
  ↓
price history
Przykład:

Turkish
WAW → IST → NRT
30.10 → 14.11

18 Aug    3,421 PLN
19 Aug    3,218 PLN
20 Aug    3,099 PLN
21 Aug    3,347 PLN
19. Deduplication
Ten sam itinerary może pojawić się wiele razy.

Deduplication key:

origin
destination
departure timestamp
arrival timestamp
segments
airlines
flight numbers
Cena nie może być częścią identity.

Jeżeli cena zmieni się:

same flight
different price
ma zostać zapisany jako kolejny price history record.

20. Price alert
Warunek:

offer.price <= search.target_price
ORAZ:

offer.ticket_type == SINGLE_TICKET
ORAZ:

offer.verification_status == VERIFIED
ORAZ:

offer.stops <= search.max_stops
Wtedy:

PRICE_TARGET_REACHED
21. Notification
MVP:

Telegram Bot.

Environment variables:

TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
Utwórz:

notifications/base.py
notifications/telegram.py
Interface:

class NotificationProvider(ABC):

    async def send_price_alert(
        self,
        offer: FlightOffer,
    ) -> None:
        ...
22. Alert content
Powiadomienie musi zawierać:

✈️ Flight Hunter alert

WAW → TYO

Departure:
30 Oct 2026

Return:
14 Nov 2026

Trip:
15 days

Airline:
Turkish Airlines

Price:
3,218 PLN

Route:
WAW → IST → NRT

Stops:
1

Stop:
IST

Total travel time:
17h 40m

Ticket:
✓ Single ticket

Booking:
Airline website

Target:
3,500 PLN
Dodaj link:

Open flight
jeżeli provider dostarcza booking URL.

23. Frontend
Frontend ma być minimalistyczny.

Nie buduj dashboardu przeładowanego informacjami.

Użyj:

jasnego tła,
kart,
dużej typografii,
subtelnych borderów,
zielonego statusu dla target price,
czerwonego dla błędów,
szarego dla UNKNOWN.
Nie używaj ciężkich gradientów ani dekoracyjnego UI.

24. Main navigation
Desktop:

Flight Hunter

Searches
History
Settings
Mobile:

[Searches] [History] [Settings]
25. Dashboard
Po wejściu:

Flight Hunter

Active searches

┌───────────────────────────────────────┐
│ 🇯🇵 Japan November                   │
│ WAW → TYO                             │
│ 29 Oct – 1 Nov                       │
│ 13–16 days                            │
│ Target: 3,500 PLN                    │
│                                       │
│ Best found: 3,218 PLN                │
│ Last checked: 12 min ago             │
│                                       │
│ 🟢 Target reached                    │
│                                       │
│ [View results]                       │
└───────────────────────────────────────┘
26. Search creation UI
Form:

From
[ WAW ]

To
[ TYO ]

Earliest departure
[ 29 Oct 2026 ]

Latest departure
[ 1 Nov 2026 ]

Trip duration
[ 13 ] to [ 16 ] days

Latest return
[ 16 Nov 2026 ]

Target price
[ 3500 ] PLN

Maximum stops
[ 1 ]

[✓] Only single-ticket itineraries

Notification
[✓] Telegram

[ Create search ]
Po utworzeniu automatycznie uruchom pierwszy search.

27. Search result page
Pokaż:

Japan November

WAW → TYO

29 Oct – 1 Nov departures
13–16 days
Target 3,500 PLN

Last checked:
19 Aug 2026 12:30
Pod spodem lista ofert.

Sortowanie:

Price
Duration
Departure
Stops
Domyślnie:

Price ascending
28. Flight card
Każda karta:

┌────────────────────────────────────────────────────┐
│ Turkish Airlines                         3,218 PLN │
│                                                    │
│ 30 Oct → 14 Nov                                   │
│ 15 days                                            │
│                                                    │
│ WAW 10:35 ───── IST ─────  NRT 08:45              │
│          1 stop                                    │
│                                                    │
│ Total travel: 17h 40m                             │
│                                                    │
│ ✓ Single ticket                                   │
│ ✓ Verified                                        │
│                                                    │
│ [Details]                         [Open airline]  │
└────────────────────────────────────────────────────┘
Jeżeli cena <= target:

🟢 BELOW TARGET
29. Flight detail
Po kliknięciu:

Turkish Airlines

3,218 PLN

30 Oct 2026
WAW → IST

TK1766
10:35 → 14:10

Layover
IST
1h 45m

IST → NRT

TK50
15:55 → 08:45 +1

Return
14 Nov 2026

...

Price history

3,421
3,218
3,099
3,347
30. History screen
Tabela:

Date checked | Departure | Return | Airline | Route | Stops | Duration | Price | Status
Przykład:

19 Aug | 30 Oct | 14 Nov | Turkish | WAW-IST-NRT | 1 | 17h40 | 3218 | VERIFIED
19 Aug | 30 Oct | 14 Nov | Air China | WAW-PEK-NRT | 1 | 18h15 | 3341 | VERIFIED
19 Aug | 30 Oct | 14 Nov | Finnair | WAW-HEL-HND | 1 | 16h50 | 3487 | VERIFIED
Filtry:

airline,
date,
price,
status,
number of stops.
31. Search run progress
Podczas wyszukiwania nie przeładowuj całej strony.

Użyj HTMX polling.

Pokaż:

Searching...

12 / 16 combinations

████████████░░░░

Offers found: 42
Verified: 8

Current:
WAW → TYO
31 Oct → 15 Nov
Po zakończeniu:

✓ Search complete

16 combinations checked
142 offers found
27 unique offers
10 verified
3 below target
32. Error handling
Nie pozwól, żeby jedna niedostępna kombinacja przerwała cały search.

Przykład:

29 Oct → 11 Nov   ✓
29 Oct → 12 Nov   ✓
29 Oct → 13 Nov   ERROR
29 Oct → 14 Nov   ✓
Search musi kontynuować.

Błąd zapisz:

provider
query
timestamp
HTTP status
error type
error message
Nie zapisuj cookies, tokenów ani danych wrażliwych.

33. Provider rate limiting
Każdy provider ma własny limiter.

Przykład:

class RateLimiter:
    ...
Konfiguracja:

PROVIDER_MIN_INTERVAL_SECONDS=10
Nigdy nie wykonuj równoległych, agresywnych requestów do tego samego providera.

Jeżeli provider zwróci:

429
odczekaj zgodnie z backoffem.

Nie implementuj obchodzenia blokady.

34. Scheduler
Użyj APScheduler.

Search może mieć:

manual
every 6 hours
every 12 hours
daily
MVP:

manual
daily
Później:

every 6h
every 12h
35. Search execution
Implementuj:

async def run_search(search_id):
    ...
Flow:

load search
        ↓
generate date combinations
        ↓
for each combination:
    discovery
        ↓
normalize
        ↓
deduplicate
        ↓
persist raw results
        ↓
filter max stops
        ↓
select best candidates
        ↓
verify
        ↓
persist verification
        ↓
update price history
        ↓
check target
        ↓
send notification
36. Important optimization
Nie wysyłaj verification dla wszystkich wyników.

Przykład:

142 raw offers
↓
27 unique
↓
14 matching max stops
↓
10 cheapest selected
↓
verify 10
Konfiguracja:

MAX_OFFERS_TO_VERIFY=10
37. Configuration
.env.example:

APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000

DATABASE_URL=sqlite:///./data/flight_hunter.db

DEFAULT_CURRENCY=PLN

PROVIDER_MIN_INTERVAL_SECONDS=10
MAX_OFFERS_TO_VERIFY=10

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

LOG_LEVEL=INFO
38. Logging
Użyj standardowego Python logging.

Format:

2026-08-19 12:30:21 INFO search_started search_id=1
2026-08-19 12:30:23 INFO combination_checked departure=2026-10-29 return=2026-11-11
2026-08-19 12:30:25 INFO offers_found count=12
2026-08-19 12:30:26 INFO verification_started offer_id=123
2026-08-19 12:30:28 INFO price_target_reached offer_id=123 price=3218
39. API endpoints
Implementuj:

GET  /
GET  /searches
GET  /searches/new
POST /searches
GET  /searches/{id}
POST /searches/{id}/run
POST /searches/{id}/toggle
DELETE /searches/{id}

GET /searches/{id}/results
GET /searches/{id}/history

GET /flights/{id}

GET /api/searches/{id}/progress
GET /api/health
40. API response format
Dla JSON API używaj:

{
  "status": "ok",
  "data": {}
}
Błędy:

{
  "status": "error",
  "error": {
    "code": "SEARCH_NOT_FOUND",
    "message": "Search not found"
  }
}
41. Tests
Napisz testy dla:

Date generation
Test:

29 Oct – 1 Nov
13–16 days
latest return 16 Nov
i oczekiwany zestaw kombinacji.

Price target
3218 <= 3500 -> true
3501 <= 3500 -> false
Stops
0 <= 1 -> true
1 <= 1 -> true
2 <= 1 -> false
Ticket
SINGLE_TICKET -> valid
SELF_TRANSFER -> invalid
UNKNOWN -> invalid
Deduplication
Dwa identyczne itineraries muszą być jednym rekordem.

Zmiana ceny nie może tworzyć nowego itinerary.

Notification
Ten sam offer + ten sam price nie może generować dwóch identycznych alertów.

42. Mock provider
Dodaj provider testowy:

providers/discovery/mock.py
Nie używaj prawdziwego Google w unit tests.

Mock powinien generować:

LOT
WAW → NRT
3200 PLN
0 stops

Turkish
WAW → IST → NRT
3218 PLN
1 stop

Air China
WAW → PEK → NRT
3341 PLN
1 stop
Dzięki temu całą aplikację można testować bez internetu.

43. CLI
Dodaj prosty CLI:

make dev
uruchamia:

uvicorn app.main:app --reload
Dodaj również:

make test
make lint
make format
make migrate
44. pyproject.toml
Użyj uv jako package managera.

Dependencies:

fastapi
uvicorn
jinja2
sqlalchemy
alembic
pydantic
pydantic-settings
httpx
apscheduler
python-multipart
Dev:

pytest
pytest-asyncio
ruff
mypy
Provider flight-search dependency dobierz zgodnie z aktualnym API biblioteki fli.

Nie pinuj jej na ślepo do starej wersji.

Sprawdź aktualne API podczas implementacji.

45. README
README musi zawierać:

Installation
git clone ...
cd flight-hunter
uv sync
cp .env.example .env
Database
make migrate
Run
make dev
Open:

http://127.0.0.1:8000
Telegram
Instrukcja utworzenia bota i wpisania:

TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
46. Security
Nigdy:

nie commituj .env,
nie zapisuj Telegram tokena w DB,
nie zapisuj cookies providera w DB,
nie loguj credentials,
nie loguj pełnych nagłówków HTTP.
.gitignore:

.env
data/*.db
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
47. UX principles
Frontend ma być:

prosty,
szybki,
czytelny,
mobile-first,
bez niepotrzebnych animacji,
bez dużych dashboardowych wykresów na głównym ekranie.
Najważniejsza informacja na karcie lotu:

PRICE
DATE
AIRLINE
ROUTE
DURATION
STOPS
SINGLE TICKET STATUS
48. Responsive behavior
Mobile:

┌─────────────────────────┐
│ Turkish                 │
│                         │
│ 3,218 PLN               │
│ 🟢 BELOW TARGET         │
│                         │
│ 30 Oct → 14 Nov         │
│ 15 days                 │
│                         │
│ WAW → IST → NRT          │
│ 1 stop                  │
│ 17h 40m                 │
│                         │
│ [Details]               │
└─────────────────────────┘
Desktop:

karty mogą być szersze i informacje mogą być rozmieszczone poziomo.

49. Search result ranking
Default ranking:

1. price ASC
2. stops ASC
3. duration ASC
Nie rankinguj wyłącznie po cenie.

Dodaj później możliwość:

Price
Duration
Departure time
Stops
50. Important business rule
Cena nie jest wystarczająca.

Offer może być pokazany jako:

DISCOVERED
ale nie jako:

VERIFIED
dopóki verification nie potwierdzi źródła.

UI musi to jasno rozróżniać.

Przykład:

3,218 PLN
⚠ Found in discovery
vs.

3,218 PLN
✓ Verified on airline
51. MVP scope
W pierwszej implementacji NIE implementuj:

booking,
płatności,
kont użytkowników,
multi-user,
OAuth,
cloud deployment,
PostgreSQL,
React,
zaawansowanego auth,
automatycznego omijania CAPTCHA,
proxy rotation,
scraping każdej linii lotniczej.
MVP ma być małe i działające.

52. Recommended implementation order
Implementuj w tej kolejności:

Phase 1
Project skeleton.

FastAPI
SQLite
SQLAlchemy
Alembic
Jinja
Tailwind
basic dashboard
Phase 2
Search model.

create search
edit search
activate/deactivate
date generator
Phase 3
Mock provider.

raw offers
normalization
deduplication
database persistence
Phase 4
Results UI.

cards
filters
sorting
detail page
history
Phase 5
Real discovery provider.

Integrate fli or gfly.

Keep it behind:

FlightDiscoveryProvider
Phase 6
Price alert.

target price
Telegram
duplicate protection
Phase 7
Verification architecture.

Implement provider interface and first airline verification adapter only if technically reliable.

Do not fake verification.

Phase 8
Scheduler.

manual
daily
Phase 9
Tests and polish.

53. Definition of done
Projekt jest gotowy, kiedy:

Mogę utworzyć search:
WAW → TYO.
Mogę ustawić:
29.10–01.11,
13–16 dni,
latest return = 16.11.
Program generuje wszystkie poprawne kombinacje.
Program odpytuje discovery provider.
Wyniki zapisują się do SQLite.
Każda oferta ma:

airline,
price,
departure,
return,
duration,
stops,
stop airports,
segments,
source.
Wyniki są deduplikowane.
Historia zachowuje wszystkie poprzednie ceny.
Mogę ustawić target price.
Oferta poniżej target price jest oznaczona.
Verified single-ticket offer poniżej target price generuje Telegram alert.
UI działa dobrze na telefonie.
Mogę wejść w szczegóły oferty.
Mogę zobaczyć historię ceny.
Błąd jednego zapytania nie przerywa całego searcha.
Można dodać kolejnego providera bez zmiany search_engine.py.
pytest przechodzi.
ruff przechodzi.
54. Final architecture
Docelowo:

                         ┌───────────────────┐
                         │    WEB FRONTEND   │
                         │ Jinja + HTMX      │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │      FastAPI      │
                         └─────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
               Search Engine    History       Notifications
                    │              │              │
                    ▼              ▼              ▼
              Discovery       SQLite          Telegram
                    │
          ┌─────────┴──────────┐
          │                    │
          ▼                    ▼
    Google Flights        Future providers
       adapter              / other APIs
          │
          ▼
       Candidates
          │
          ▼
     Normalization
          │
          ▼
      Deduplication
          │
          ▼
       Verification
          │
          ▼
      Valid Offers
          │
          ▼
      Price Target
          │
          ▼
       Alert
55. Important implementation instruction
Do not over-engineer.

The application should be fully usable with:

1 user
1 SQLite database
1 FastAPI process
1 scheduler
1 Telegram bot
1 discovery provider
Do not introduce Redis, Celery, Docker, Kubernetes, PostgreSQL or React unless a concrete requirement emerges.

The project should be runnable locally with:

uv sync
make migrate
make dev
and usable at:

http://127.0.0.1:8000
The code must be clean, typed, tested and modular enough to add additional flight providers later.

When an external provider is unavailable, display a clear provider status in the UI instead of crashing.

Do not fabricate ticket verification.

A flight that is merely discovered is not the same thing as a flight verified as purchasable on one ticket.

