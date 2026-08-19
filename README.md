# Flight Hunter

Local, single-user flight discovery and price tracking using the open-source [`flights` / fli](https://github.com/punitarani/fli) package. It performs low-volume Google Flights searches locally; no paid API, proxy rotation, browser automation, CAPTCHA bypass, or credentials are used.

## Install

```sh
uv sync
cp .env.example .env
make migrate
make dev
```

Open http://127.0.0.1:8000. Create a search such as `WAW` to `TYO`; the application resolves `TYO` to `HND` and `NRT`, then stores the concrete arrival airport returned by Google Flights.

## Commands

```sh
make test
make lint
make format
```

## Provider safety

The application serializes provider requests and waits `PROVIDER_MIN_INTERVAL_SECONDS` between them. A provider failure is recorded against the search run and does not stop the remaining date combinations. Fli is an unofficial, reverse-engineered Google Flights client, so availability can change.

## Verification and alerts

Discovery is intentionally not verification. Offers are shown as `UNKNOWN` until a reliable adapter establishes that the complete itinerary is a single protected ticket. Telegram alerts are consequently disabled until that verifier is implemented; the app must never send an alert based only on a discovered price.

## Telegram configuration

When verification support is enabled, add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to `.env`. Tokens are never stored in SQLite.