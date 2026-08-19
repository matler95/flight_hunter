# Flight Hunter

Local, single-user flight discovery and price tracking. The MVP ships with a deterministic mock provider so it is fully usable and testable without internet access. Discovered offers and verified single-ticket offers are visibly distinct.

## Install

```sh
uv sync
cp .env.example .env
make migrate
make dev
```

Open http://127.0.0.1:8000. Create a search, for example `WAW` to `TYO`; airport group `TYO` resolves to a concrete Tokyo arrival airport in the mock provider.

## Commands

```sh
make test
make lint
make format
```

## Provider and verification

The default provider is `MockFlightProvider`. `GoogleFlightsProvider` is deliberately only an adapter boundary until a reviewed `fli`/`gfly` integration is configured. It does not scrape, bypass CAPTCHA, rotate proxies, or fabricate availability. Airline verification returns `UNKNOWN` unless it can reliably confirm a single protected ticket.

## Telegram

Create a bot with BotFather, message it once, then put `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`. Tokens are never stored in the database. The notification adapter is reserved for verified, single-ticket, below-target offers.
