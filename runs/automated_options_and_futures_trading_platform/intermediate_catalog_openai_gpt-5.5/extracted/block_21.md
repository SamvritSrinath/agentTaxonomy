# Safe Trading Automation Dashboard

This project provides:

- FastAPI backend
- SQLite local trade database
- WebSocket market-data listener
- Rolling one-hour drop detector
- React dashboard
- Paper/manual trade workflow

## Safety behavior

This service does **not** send autonomous live brokerage orders.

Modes:

- `AUTO_TRADE_MODE=paper`: automatically records a paper-filled put-option trade when the signal triggers.
- `AUTO_TRADE_MODE=manual`: records a pending recommendation that can be manually approved in the dashboard, still as a paper fill.

## Backend
