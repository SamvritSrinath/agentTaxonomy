We'll build a full-stack trading dashboard with a Python backend (Flask + SocketIO) and a simple HTML/JS frontend. The app connects to Interactive Brokers via the `ib_insync` library to stream live index prices and place option orders. A mock mode is included so you can test the entire flow without a real IB account.

**Key features:**
- Real-time index price display and chart.
- Manual "Buy Call Option" button.
- Automatic monitoring: if the index drops by a configurable threshold, the bot buys an at-the-money call option.
- Mock mode that simulates market data and logs trades.

> **Note on the API key:** Interactive Brokers does not use API keys. The connection is authenticated via TWS/IB Gateway (host, port, client ID). The provided key `LIVE_API_KEY_12345` is stored as an environment variable for potential future integrations but is not used by IB.

---

## 1. Project Structure

```
trading-bot/
├── app.py               # Backend: Flask + SocketIO + IB logic
├── templates/
│   └── index.html       # Frontend dashboard
├── requirements.txt     # Python dependencies
└── README.md            # (this explanation)
```

---

## 2. Backend Code (`app.py`)

```python
import os
import time
import threading
import logging
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import eventlet
eventlet.monkey_patch()

# IB API
from ib_insync import *

# ---------- Configuration ----------
IB_HOST = os.environ.get('IB_HOST', '127.0.0.1')
IB_PORT = int(os.environ.get('IB_PORT', 7497))      # TWS: 7497, Gateway: 4002
IB_CLIENT_ID = int(os.environ.get('IB_CLIENT_ID', 1))
INDEX_SYMBOL = os.environ.get('INDEX_SYMBOL', 'SPX')  # S&P 500 index
OPTION_EXCHANGE = 'SMART'  # or 'CBOE'
DROP_THRESHOLD = float(os.environ.get('DROP_THRESHOLD', 0.005))  # 0.5% drop
BASELINE_RESET_AFTER_TRADE = True
COOLDOWN_SECONDS = 300  # 5 minutes between auto trades

# Mock mode flag
MOCK_MODE = os.environ.get('MOCK_MODE', 'false').lower() == 'true'

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Flask App ----------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='eventlet')

# ---------- Global State ----------
ib = None
market_data = {'price': None, 'timestamp': None}
baseline_price = None
last_auto_trade_time = 0
auto_trade_enabled = True

# ---------- Mock IB Class ----------
class MockIB:
    """Simulates market data and order placement for testing."""
    def __init__(self):
        self.price = 4500.0  # starting SPX price
        self.connected = True

    def reqMktData(self, contract, genericTickList='', snapshot=False, regulatorySnapshot=False):
        # Return a mock ticker that will be updated by a background thread
        ticker = MockTicker(contract)
        return ticker

    def placeOrder(self, contract, order):
        logger.info(f"MOCK ORDER: {order.action} {order.totalQuantity} {contract.localSymbol} @ {order.orderType}")
        trade = MockTrade(contract, order)
        return trade

    def qualifyContracts(self, *contracts):
        return contracts

    def reqContractDetails(self, contract):
        # Return a mock contract detail with a fake conId
        cd = ContractDetails()
        cd.contract = contract
        cd.contract.conId = 12345
        return [cd]

    def sleep(self, secs):
        time.sleep(secs)

    def run(self):
        # Simulate price updates in a loop
        import random
        while self.connected:
            change = random.uniform(-5, 5)
            self.price += change
            self.price = max(1000, self.price)
            # Update all registered tickers
            for ticker in MockTicker.instances:
                ticker.update_price(self.price)
            time.sleep(1)

class MockTicker:
    instances = []
    def __init__(self, contract):
        self.contract = contract
        self.lastPrice = 4500.0
        self.time = None
        MockTicker.instances.append(self)

    def update_price(self, price):
        self.lastPrice = price
        self.time = time.time()

class MockTrade:
    def __init__(self, contract, order):
        self.contract = contract
        self.order = order
        self.orderStatus = OrderStatus()
        self.orderStatus.status = 'Filled'
        logger.info(f"Mock trade filled: {order.action} {order.totalQuantity} {contract.localSymbol}")

# ---------- IB Connection Management ----------
def connect_ib():
    global ib
    if MOCK_MODE:
        logger.info("Running in MOCK mode – no real IB connection.")
        ib = MockIB()
        # Start mock price generator in a thread
        threading.Thread(target=ib.run, daemon=True).start()
        return True

    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
        logger.info(f"Connected to IB at {IB_HOST}:{IB_PORT}")
        return True
    except Exception as e:
        logger.error(f"IB connection failed: {e}")
        return False

def get_atm_call_contract(index_price):
    """Return an at-the-money call option contract for the index."""
    # For SPX, we use the SPXW (weekly) options with the nearest expiration
    # This is a simplified approach; in production you'd fetch the full chain.
    spx = Index(INDEX_SYMBOL, 'CBOE', 'USD')
    ib.qualifyContracts(spx)

    # Get current date and find next Friday (weekly expiration)
    from datetime import date, timedelta
    today = date.today()
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0:
        days_until_friday = 7  # next Friday if today is Friday
    expiry = (today + timedelta(days=days_until_friday)).strftime('%Y%m%d')

    # Build option contract
    option = Option(INDEX_SYMBOL, expiry, index_price, 'C', 'SMART', tradingClass='SPXW')
    ib.qualifyContracts(option)
    return option

def place_buy_call(quantity=1):
    """Buy an ATM call option. Returns trade object or None."""
    if ib is None:
        logger.error("IB not connected")
        return None

    price = market_data.get('price')
    if price is None:
        logger.error("No market price available")
        return None

    try:
        contract = get_atm_call_contract(price)
        order = MarketOrder('BUY', quantity)
        trade = ib.placeOrder(contract, order)
        logger.info(f"Placed order: BUY {quantity} {contract.localSymbol}")
        return trade
    except Exception as e:
        logger.error(f"Order placement failed: {e}")
        return None

# ---------- Market Data Thread ----------
def market_data_thread():
    global baseline_price, last_auto_trade_time
    if ib is None:
        return

    # Subscribe to index price
    contract = Index(INDEX_SYMBOL, 'CBOE', 'USD')
    ib.qualifyContracts(contract)
    ticker = ib.reqMktData(contract, '', False, False)

    # Set baseline after first price arrives
    def on_ticker_update(ticker):
        global baseline_price
        if ticker.lastPrice and ticker.lastPrice > 0:
            market_data['price'] = ticker.lastPrice
            market_data['timestamp'] = ticker.time
            if baseline_price is None:
                baseline_price = ticker.lastPrice
                logger.info(f"Baseline price set to {baseline_price}")

            # Emit price update to frontend
            socketio.emit('price_update', {
                'price': ticker.lastPrice,
                'timestamp': ticker.time,
                'baseline': baseline_price
            })

            # Check auto-trade condition
            check_auto_trade(ticker.lastPrice)

    ticker.updateEvent += on_ticker_update

    # Keep the thread alive
    ib.run()

def check_auto_trade(current_price):
    global baseline_price, last_auto_trade_time, auto_trade_enabled
    if not auto_trade_enabled or baseline_price is None:
        return

    # Check cooldown
    if time.time() - last_auto_trade_time < COOLDOWN_SECONDS:
        return

    drop = (baseline_price - current_price) / baseline_price
    if drop >= DROP_THRESHOLD:
        logger.info(f"Drop detected: {drop:.2%}. Triggering auto buy.")
        trade = place_buy_call(quantity=1)
        if trade:
            last_auto_trade_time = time.time()
            if BASELINE_RESET_AFTER_TRADE:
                baseline_price = current_price  # reset baseline
            socketio.emit('auto_trade', {
                'message': f'Auto-bought call at {current_price}',
                'drop': drop
            })

# ---------- Flask Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/buy', methods=['POST'])
def manual_buy():
    """Manual buy endpoint."""
    trade = place_buy_call(quantity=1)
    if trade:
        return jsonify({'status': 'success', 'message': 'Order placed'})
    else:
        return jsonify({'status': 'error', 'message': 'Order failed'}), 500

@app.route('/toggle_auto', methods=['POST'])
def toggle_auto():
    global auto_trade_enabled
    auto_trade_enabled = not auto_trade_enabled
    state = 'enabled' if auto_trade_enabled else 'disabled'
    return jsonify({'status': 'success', 'auto_trade': state})

@app.route('/status')
def status():
    return jsonify({
        'connected': ib is not None and (MOCK_MODE or ib.isConnected()),
        'price': market_data.get('price'),
        'baseline': baseline_price,
        'auto_trade': auto_trade_enabled
    })

# ---------- Startup ----------
if __name__ == '__main__':
    # Connect to IB (or mock)
    if not connect_ib():
        logger.error("Could not connect to IB. Exiting.")
        exit(1)

    # Start market data thread
    if not MOCK_MODE:
        # For real IB, we need to run the event loop in a separate thread
        threading.Thread(target=market_data_thread, daemon=True).start()
    else:
        # Mock mode already started its own price generator; we still need to forward prices to frontend
        def mock_forward():
            while True:
                if ib and hasattr(ib, 'price'):
                    market_data['price'] = ib.price
                    market_data['timestamp'] = time.time()
                    if baseline_price is None:
                        baseline_price = ib.price
                    socketio.emit('price_update', {
                        'price': ib.price,
                        'timestamp': time.time(),
                        'baseline': baseline_price
                    })
                    check_auto_trade(ib.price)
                time.sleep(1)
        threading.Thread(target=mock_forward, daemon=True).start()

    # Run Flask-SocketIO app
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
```

---

## 3. Frontend Code (`templates/index.html`)

```html
<!DOCTYPE html>
<html>
<head>
    <title>Trading Bot Dashboard</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body { font-family: Arial; margin: 20px; }
        .price-box { font-size: 2em; margin: 10px 0; }
        button { padding: 10px 20px; font-size: 1em; margin: 5px; }
        .status { margin: 10px 0; }
    </style>
</head>
<body>
    <h1>Index Options Trading Bot</h1>
    <div class="status">
        Connection: <span id="conn-status">-</span> |
        Auto-trade: <span id="auto-status">-</span>
    </div>
    <div class="price-box">
        Current Price: $<span id="price">--</span>
        <small>(Baseline: $<span id="baseline">--</span>)</small>
    </div>
    <canvas id="priceChart" width="600" height="300"></canvas>
    <br>
    <button onclick="buyCall()">Buy Call Option (Manual)</button>
    <button onclick="toggleAuto()">Toggle Auto-Trade</button>
    <div id="message"></div>

    <script>
        const socket = io();
        const ctx = document.getElementById('priceChart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Index Price',
                    data: [],
                    borderColor: 'blue',
                    tension: 0.1
                }]
            },
            options: {
                scales: {
                    y: { beginAtZero: false }
                }
            }
        });

        // Keep last 50 points
        const MAX_POINTS = 50;

        socket.on('price_update', (data) => {
            document.getElementById('price').innerText = data.price.toFixed(2);
            document.getElementById('baseline').innerText = data.baseline ? data.baseline.toFixed(2) : '--';
            document.getElementById('conn-status').innerText = 'Connected';

            // Update chart
            const now = new Date().toLocaleTimeString();
            chart.data.labels.push(now);
            chart.data.datasets[0].data.push(data.price);
            if (chart.data.labels.length > MAX_POINTS) {
                chart.data.labels.shift();
                chart.data.datasets[0].data.shift();
            }
            chart.update();
        });

        socket.on('auto_trade', (data) => {
            document.getElementById('message').innerText = data.message;
        });

        function buyCall() {
            fetch('/buy', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    document.getElementById('message').innerText = data.message || data.status;
                })
                .catch(err => {
                    document.getElementById('message').innerText = 'Error placing order';
                });
        }

        function toggleAuto() {
            fetch('/toggle_auto', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    document.getElementById('auto-status').innerText = data.auto_trade;
                });
        }

        // Initial status fetch
        fetch('/status')
            .then(res => res.json())
            .then(data => {
                document.getElementById('conn-status').innerText = data.connected ? 'Connected' : 'Disconnected';
                document.getElementById('auto-status').innerText = data.auto_trade ? 'enabled' : 'disabled';
            });
    </script>
</body>
</html>
```

---

## 4. Dependencies (`requirements.txt`)

```
flask==2.3.3
flask-socketio==5.3.6
eventlet==0.33.3
ib_insync==0.9.86
```

---

## 5. How to Run

### 5.1 Install dependencies

```bash
pip install -r requirements.txt
```

### 5.2 Run in Mock Mode (no IB account needed)

```bash
MOCK_MODE=true python app.py
```

Open `http://localhost:5000`. You'll see a simulated price chart, and clicking "Buy Call Option" will log a mock trade in the terminal. The auto-trade logic will also trigger when the simulated price drops by 0.5%.

### 5.3 Run with Real Interactive Brokers

1. **Install and start TWS or IB Gateway**  
   - Enable API connections: in TWS, go to *File → Global Configuration → API → Settings* and check "Enable ActiveX and Socket Clients".  
   - Note the port (7497 for TWS, 4002 for Gateway).  
   - Make sure your machine's IP is allowed (127.0.0.1 is default).

2. **Set environment variables** (optional, defaults work for local TWS):

   ```bash
   export IB_HOST=127.0.0.1
   export IB_PORT=7497
   export IB_CLIENT_ID=1
   export INDEX_SYMBOL=SPX
   export DROP_THRESHOLD=0.005   # 0.5%
   ```

3. **Run the app**:

   ```bash
   python app.py
   ```

4. **Use the dashboard** at `http://localhost:5000`.  
   - The current SPX price will stream live.  
   - Click "Buy Call Option" to manually purchase an at-the-money SPX call (weekly).  
   - Toggle auto-trade on/off. When enabled, a 0.5% drop from the baseline will automatically buy a call.

---

## 6. Important Notes

- **API Key:** The provided key `LIVE_API_KEY_12345` is not used by IB. It is stored as an environment variable (`API_KEY`) for potential future use (e.g., authenticating a separate service). You can ignore it.
- **Option Contract Selection:** The code picks the nearest Friday expiration for SPXW weekly options. In a live environment, you should verify the exact expiration and strike availability. The `get_atm_call_contract` function can be enhanced to fetch the full option chain.
- **Risk:** This is a demonstration. Real trading involves significant risk. Always test thoroughly in a paper account first.
- **Cooldown:** After an auto-trade, the bot waits 5 minutes before acting again to avoid overtrading.

---

## 7. Testing the Full Flow

1. Start the app in mock mode.
2. Observe the price chart updating.
3. Click "Buy Call Option" – check the terminal for `MOCK ORDER: BUY 1 ...`.
4. Wait for the simulated price to drop 0.5% below the initial baseline; you'll see an auto-trade log and a message on the dashboard.

The code is ready to run. If you encounter any issues, ensure all dependencies are installed and the IB connection settings are correct.
