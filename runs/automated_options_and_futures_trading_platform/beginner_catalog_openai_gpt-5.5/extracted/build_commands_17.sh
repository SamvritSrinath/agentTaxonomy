cd ibkr-paper-monitor/backend

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# Optional: use demo mode if IBKR is not running
# export APP_DEMO_MODE=true

# Paper TWS default:
export APP_IB_HOST=127.0.0.1
export APP_IB_PORT=7497
export APP_IB_READONLY=true
export APP_IB_DELAYED_DATA=true

pytest

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
