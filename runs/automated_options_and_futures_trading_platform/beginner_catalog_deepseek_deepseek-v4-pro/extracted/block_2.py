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
