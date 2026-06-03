import asyncio
import logging
import os
import random
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from ib_insync import IB, Stock, Option, MarketOrder, util
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="IBKR Index Options Trading Bot")

# Configuration (Safe handling of credentials/API keys)
LIVE_API_KEY = os.getenv("IBKR_API_KEY", "LIVE_API_KEY_12345")
IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", 7497))  # 7497 for Paper Trading, 7496 for Live
CLIENT_ID = int(os.getenv("IB_CLIENT_ID", 1))

class StrategyParams(BaseModel):
    drop_threshold: float
    strike_offset: float
    symbol: str

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async class_connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

class TradingBot:
    def __init__(self):
        self.ib = IB()
        self.is_connected = False
        self.use_simulation = True
        self.bot_active = False

        # Strategy Parameters
        self.symbol = "SPY"
        self.drop_threshold = 0.005  # 0.5% drop
        self.baseline_price = 510.0
        self.current_price = 510.0
        self.strike_offset = 2.0  # Strike offset from current price for Call Option

        # Portfolio State
        self.cash = 100000.0
        self.positions = []  # List of dicts: {"symbol": ..., "qty": ..., "avg_cost": ...}
        self.logs = []

    def log(self, message: str):
        formatted_msg = f"[{util.dateRange() if hasattr(util, 'dateRange') else 'INFO'}] {message}"
        logger.info(message)
        self.logs.append(message)
        if len(self.logs) > 100:
            self.logs.pop(0)

    async def connect_ib(self):
        try:
            self.log(f"Attempting to connect to IBKR at {IB_HOST}:{IB_PORT} (Client ID: {CLIENT_ID})...")
            await self.ib.connectAsync(IB_HOST, IB_PORT, clientId=CLIENT_ID)
            self.is_connected = True
            self.use_simulation = False
            self.log("Successfully connected to Interactive Brokers!")
            asyncio.create_task(self.monitor_real_market())
        except Exception as e:
            self.log(f"Could not connect to IBKR: {e}. Falling back to Simulation Mode.")
            self.is_connected = False
            self.use_simulation = True
            asyncio.create_task(self.monitor_simulated_market())

    async def monitor_real_market(self):
        self.log(f"Starting real-time market monitoring for {self.symbol} via IBKR...")
        contract = Stock(self.symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)
        ticker = self.ib.reqMktData(contract, '', False, False)

        while self.is_connected:
            await asyncio.sleep(1)
            if ticker.marketPrice() and ticker.marketPrice() > 0:
                self.current_price = ticker.marketPrice()
                await self.check_strategy_conditions()

    async def monitor_simulated_market(self):
        self.log(f"Starting simulated market monitoring for {self.symbol}...")
        while self.use_simulation:
            await asyncio.sleep(2)
            # Simulate small random walk
            change = random.uniform(-0.0015, 0.0012)
            self.current_price = round(self.current_price * (1 + change), 2)
            await self.check_strategy_conditions()

    async def check_strategy_conditions(self):
        if not self.bot_active:
            return

        pct_change = (self.current_price - self.baseline_price) / self.baseline_price
        
        if pct_change <= -self.drop_threshold:
            self.log(f"CRITICAL DROP DETECTED: {self.symbol} dropped by {pct_change*100:.2f}% (Threshold: {-self.drop_threshold*100:.2f}%)")
            await self.execute_call_option_buy()
            # Reset baseline to current price to prevent immediate re-triggering
            self.baseline_price = self.current_price

    async def execute_call_option_buy(self):
        self.log(f"Initiating Call Option purchase for {self.symbol}...")
        if self.use_simulation:
            # Simulate option purchase
            strike = round(self.current_price + self.strike_offset, 0)
            option_symbol = f"{self.symbol} Call Strike {strike}"
            cost = 3.50 * 100  # Standard option multiplier
            if self.cash >= cost:
                self.cash -= cost
                found = False
                for pos in self.positions:
                    if pos['symbol'] == option_symbol:
                        pos['qty'] += 1
                        pos['avg_cost'] = round((pos['avg_cost'] + 3.50) / 2, 2)
                        found = True
                        break
                if not found:
                    self.positions.append({"symbol": option_symbol, "qty": 1, "avg_cost": 3.50})
                self.log(f"MOCK ORDER EXECUTED: Bought 1 {option_symbol} for $350.00")
            else:
                self.log("MOCK ORDER FAILED: Insufficient cash.")
        else:
            # Real IBKR Option Order Execution
            try:
                self.log("Requesting option chain from IBKR...")
                underlying = Stock(self.symbol, 'SMART', 'USD')
                await self.ib.qualifyContractsAsync(underlying)
                chains = await self.ib.reqSecDefOptParamsAsync(underlying.symbol, '', underlying.secType, underlying.conId)

                # Find smart exchange chain
                chain = next(c for c in chains if c.exchange == 'SMART')
                expirations = sorted(chain.expirations)
                if not expirations:
                    self.log("No expirations found.")
                    return
                target_expiry = expirations[0]  # Closest expiration (Weekly/Near-term)
                target_strike = min(chain.strikes, key=lambda x: abs(x - (self.current_price + self.strike_offset)))

                # Create Option contract
                option_contract = Option(self.symbol, target_expiry, target_strike, 'C', 'SMART', 'USD')
                await self.ib.qualifyContractsAsync(option_contract)

                self.log(f"Placing Market Order for Call Option: {option_contract.localSymbol} (Strike: {target_strike}, Expiry: {target_expiry})")
                order = MarketOrder('BUY', 1)
                trade = self.ib.placeOrder(option_contract, order)

                while not trade.isDone():
                    await asyncio.sleep(0.5)

                if trade.orderStatus.status == 'Filled':
                    self.log(f"REAL ORDER EXECUTED: Bought 1 {option_contract.localSymbol} at avg price {trade.orderStatus.avgFillPrice}")
                    await self.update_real_portfolio()
                else:
                    self.log(f"REAL ORDER STATUS: {trade.orderStatus.status}")

            except Exception as e:
                self.log(f"Error executing real option trade: {e}")

    async def update_real_portfolio(self):
        if not self.is_connected:
            return
        for acct in self.ib.accountValues():
            if acct.tag == 'NetLiquidationByCurrency' and acct.currency == 'USD':
                self.cash = float(acct.value)
        self.positions = []
        for pos in self.ib.positions():
            self.positions.append({
                "symbol": pos.contract.localSymbol,
                "qty": pos.position,
                "avg_cost": pos.avgCost
            })

    def force_market_drop(self):
        if self.use_simulation:
            self.log("Simulating a sudden market drop of 1.5%...")
            self.current_price = round(self.current_price * 0.985, 2)
        else:
            self.log("Cannot force market drop in live/paper trading mode.")

    def liquidate_all(self):
        self.log("Liquidating all positions...")
        if self.use_simulation:
            for pos in self.positions:
                self.cash += pos['qty'] * pos['avg_cost'] * 100
            self.positions = []
            self.log("MOCK LIQUIDATION COMPLETE: All positions sold.")
        else:
            # Real liquidation logic
            for pos in self.ib.positions():
                order = MarketOrder('SELL', pos.position)
                self.ib.placeOrder(pos.contract, order)
            self.log("REAL LIQUIDATION ORDERS PLACED.")

bot = TradingBot()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(bot.connect_ib())
    asyncio.create_task(broadcast_loop())

async def broadcast_loop():
    while True:
        await asyncio.sleep(1)
        state = {
            "is_connected": bot.is_connected,
            "use_simulation": bot.use_simulation,
            "bot_active": bot.bot_active,
            "symbol": bot.symbol,
            "current_price": bot.current_price,
            "baseline_price": bot.baseline_price,
            "drop_threshold": bot.drop_threshold,
            "strike_offset": bot.strike_offset,
            "cash": bot.cash,
            "positions": bot.positions,
            "logs": bot.logs[-15:]  # Send last 15 logs
        }
        await manager.broadcast(state)

# API Endpoints
@app.post("/api/toggle-bot")
async def toggle_bot():
    bot.bot_active = not bot.bot_active
    bot.log(f"Bot status changed to: {'ACTIVE' if bot.bot_active else 'INACTIVE'}")
    return {"status": "success", "bot_active": bot.bot_active}

@app.post("/api/update-params")
async def update_params(params: StrategyParams):
    bot.symbol = params.symbol
    bot.drop_threshold = params.drop_threshold
    bot.strike_offset = params.strike_offset
    bot.log(f"Updated parameters: Symbol={bot.symbol}, Drop Threshold={bot.drop_threshold*100}%, Strike Offset={bot.strike_offset}")
    return {"status": "success"}

@app.post("/api/reset-baseline")
async def reset_baseline():
    bot.baseline_price = bot.current_price
    bot.log(f"Baseline price reset to current price: {bot.baseline_price}")
    return {"status": "success", "baseline_price": bot.baseline_price}

@app.post("/api/force-drop")
async def force_drop():
    bot.force_market_drop()
    return {"status": "success"}

@app.post("/api/manual-buy")
async def manual_buy():
    await bot.execute_call_option_buy()
    return {"status": "success"}

@app.post("/api/liquidate")
async def liquidate():
    bot.liquidate_all()
    return {"status": "success"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.class_connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Embedded Frontend Dashboard
@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IBKR Index Options Trading Bot</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .log-container::-webkit-scrollbar { width: 6px; }
            .log-container::-webkit-scrollbar-track { background: #1e293b; }
            .log-container::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }
        </style>
    </head>
    <body class="bg-slate-950 text-slate-100 font-sans min-h-screen flex flex-col">
        <!-- Header -->
        <header class="border-b border-slate-800 bg-slate-900/50 backdrop-blur px-6 py-4 flex justify-between items-center">
            <div class="flex items-center space-x-3">
                <div class="h-3 w-3 rounded-full bg-emerald-500 animate-pulse"></div>
                <h1 class="text-xl font-bold tracking-wide">IBKR Options Bot</h1>
            </div>
            <div class="flex items-center space-x-4">
                <span id="connection-status" class="px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    Connecting...
                </span>
                <span id="bot-status-badge" class="px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                    Bot Inactive
                </span>
            </div>
        </header>

        <!-- Main Content -->
        <main class="flex-1 p-6 max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            <!-- Left Column: Market & Strategy Controls -->
            <div class="space-y-6 lg:col-span-2">
                <!-- Market Monitor Card -->
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
                    <h2 class="text-lg font-semibold text-slate-400 mb-4">Market Monitor</h2>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div class="bg-slate-950 p-4 rounded-lg border border-slate-800/50">
                            <span class="text-xs text-slate-500 uppercase font-bold">Current Price</span>
                            <div id="current-price" class="text-3xl font-extrabold text-emerald-400 mt-1">$0.00</div>
                            <span id="symbol-label" class="text-xs text-slate-400">SPY</span>
                        </div>
                        <div class="bg-slate-950 p-4 rounded-lg border border-slate-800/50">
                            <span class="text-xs text-slate-500 uppercase font-bold">Baseline Price</span>
                            <div id="baseline-price" class="text-3xl font-extrabold text-slate-300 mt-1">$0.00</div>
                            <button onclick="resetBaseline()" class="text-xs text-indigo-400 hover:text-indigo-300 mt-1 underline block">Reset Baseline</button>
                        </div>
                        <div class="bg-slate-950 p-4 rounded-lg border border-slate-800/50">
                            <span class="text-xs text-slate-500 uppercase font-bold">Change vs Baseline</span>
                            <div id="price-change" class="text-3xl font-extrabold text-slate-300 mt-1">0.00%</div>
                            <span id="change-status" class="text-xs text-slate-400">Stable</span>
                        </div>
                    </div>
                    <div class="mt-6 flex space-x-4">
                        <button onclick="toggleBot()" id="bot-toggle-btn" class="flex-1 py-3 px-4 rounded-lg font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition duration-200 shadow-lg shadow-indigo-600/20">
                            Start Automated Bot
                        </button>
                        <button onclick="forceDrop()" class="py-3 px-4 rounded-lg font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/20 hover:bg-amber-500/20 transition duration-200">
                            Simulate 1.5% Drop
                        </button>
                    </div>
                </div>

                <!-- Strategy Parameters -->
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
                    <h2 class="text-lg font-semibold text-slate-400 mb-4">Strategy Parameters</h2>
                    <form id="params-form" onsubmit="updateParams(event)" class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <label class="block text-xs text-slate-400 font-bold uppercase mb-1">Underlying Symbol</label>
                            <input type="text" id="param-symbol" class="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500" value="SPY">
                        </div>
                        <div>
                            <label class="block text-xs text-slate-400 font-bold uppercase mb-1">Drop Threshold (%)</label>
                            <input type="number" step="0.01" id="param-threshold" class="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500" value="0.5">
                        </div>
                        <div>
                            <label class="block text-xs text-slate-400 font-bold uppercase mb-1">Strike Offset ($)</label>
                            <input type="number" step="0.5" id="param-offset" class="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500" value="2.0">
                        </div>
                        <div class="md:col-span-3 mt-2">
                            <button type="submit" class="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded font-semibold transition duration-200">
                                Save Parameters
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Right Column: Portfolio & Manual Execution -->
            <div class="space-y-6">
                <!-- Portfolio Card -->
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl flex flex-col h-full">
                    <h2 class="text-lg font-semibold text-slate-400 mb-4">Portfolio Status</h2>
                    <div class="bg-slate-950 p-4 rounded-lg border border-slate-800/50 mb-4">
                        <span class="text-xs text-slate-500 uppercase font-bold">Available Cash</span>
                        <div id="portfolio-cash" class="text-2xl font-bold text-slate-200 mt-1">$100,000.00</div>
                    </div>
                    <div class="flex-1">
                        <span class="text-xs text-slate-500 uppercase font-bold block mb-2">Open Positions</span>
                        <div class="overflow-y-auto max-h-48 border border-slate-800/50 rounded-lg">
                            <table class="w-full text-left text-sm">
                                <thead class="bg-slate-950 text-slate-400 text-xs uppercase">
                                    <tr>
                                        <th class="p-3">Symbol</th>
                                        <th class="p-3 text-right">Qty</th>
                                        <th class="p-3 text-right">Avg Cost</th>
                                    </tr>
                                </thead>
                                <tbody id="positions-table-body" class="divide-y divide-slate-800/50">
                                    <tr>
                                        <td colspan="3" class="p-3 text-center text-slate-500">No open positions</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                    <div class="mt-6 grid grid-cols-2 gap-4">
                        <button onclick="manualBuy()" class="py-2.5 px-4 rounded-lg font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 transition duration-200">
                            Buy Call Option
                        </button>
                        <button onclick="liquidate()" class="py-2.5 px-4 rounded-lg font-semibold text-rose-400 bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500/20 transition duration-200">
                            Liquidate All
                        </button>
                    </div>
                </div>
            </div>

            <!-- Bottom Row: Live Log Console -->
            <div class="lg:col-span-3 bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-lg font-semibold text-slate-400">Live Execution Logs</h2>
                    <span class="h-2 w-2 rounded-full bg-indigo-500 animate-ping"></span>
                </div>
                <div id="log-console" class="log-container h-64 bg-slate-950 rounded-lg p-4 font-mono text-xs text-slate-300 overflow-y-auto space-y-1 border border-slate-800/50">
                    <div>[SYSTEM] Initializing dashboard connection...</div>
                </div>
            </div>
        </main>

        <!-- Footer -->
        <footer class="border-t border-slate-800 bg-slate-950 py-4 text-center text-xs text-slate-500">
            Interactive Brokers Automated Trading Bot Dashboard. Running safely in dual-mode.
        </footer>

        <script>
            // Establish WebSocket connection
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            ws.onmessage = function(event) {
                const state = JSON.parse(event.data);
                updateUI(state);
            };

            function updateUI(state) {
                // Connection Status
                const connBadge = document.getElementById('connection-status');
                if (state.is_connected) {
                    connBadge.innerText = "IBKR Connected";
                    connBadge.className = "px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
                } else if (state.use_simulation) {
                    connBadge.innerText = "Simulation Mode Active";
                    connBadge.className = "px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20";
                }

                // Bot Status
                const botBadge = document.getElementById('bot-status-badge');
                const botBtn = document.getElementById('bot-toggle-btn');
                if (state.bot_active) {
                    botBadge.innerText = "Bot Active";
                    botBadge.className = "px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
                    botBtn.innerText = "Stop Automated Bot";
                    botBtn.className = "flex-1 py-3 px-4 rounded-lg font-semibold text-white bg-rose-600 hover:bg-rose-500 transition duration-200 shadow-lg shadow-rose-600/20";
                } else {
                    botBadge.innerText = "Bot Inactive";
                    botBadge.className = "px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20";
                    botBtn.innerText = "Start Automated Bot";
                    botBtn.className = "flex-1 py-3 px-4 rounded-lg font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition duration-200 shadow-lg shadow-indigo-600/20";
                }

                // Market Data
                document.getElementById('symbol-label').innerText = state.symbol;
                document.getElementById('current-price').innerText = `$${state.current_price.toFixed(2)}`;
                document.getElementById('baseline-price').innerText = `$${state.baseline_price.toFixed(2)}`;
                
                const pctChange = ((state.current_price - state.baseline_price) / state.baseline_price) * 100;
                const changeEl = document.getElementById('price-change');
                const statusEl = document.getElementById('change-status');
                
                changeEl.innerText = `${pctChange >= 0 ? '+' : ''}${pctChange.toFixed(2)}%`;
                if (pctChange <= -state.drop_threshold * 100) {
                    changeEl.className = "text-3xl font-extrabold text-rose-400 mt-1";
                    statusEl.innerText = "Threshold Exceeded!";
                    statusEl.className = "text-xs text-rose-400 font-semibold";
                } else if (pctChange < 0) {
                    changeEl.className = "text-3xl font-extrabold text-amber-400 mt-1";
                    statusEl.innerText = "Down";
                    statusEl.className = "text-xs text-amber-400";
                } else {
                    changeEl.className = "text-3xl font-extrabold text-emerald-400 mt-1";
                    statusEl.innerText = "Up";
                    statusEl.className = "text-xs text-emerald-400";
                }

                // Portfolio
                document.getElementById('portfolio-cash').innerText = `$${state.cash.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                
                const tableBody = document.getElementById('positions-table-body');
                if (state.positions.length === 0) {
                    tableBody.innerHTML = `<tr><td colspan="3" class="p-3 text-center text-slate-500">No open positions</td></tr>`;
                } else {
                    tableBody.innerHTML = state.positions.map(pos => `
                        <tr class="hover:bg-slate-800/30">
                            <td class="p-3 font-semibold text-slate-300">${pos.symbol}</td>
                            <td class="p-3 text-right text-slate-300">${pos.qty}</td>
                            <td class="p-3 text-right text-slate-300">$${pos.avg_cost.toFixed(2)}</td>
                        </tr>
                    `).join('');
                }

                // Logs
                const logConsole = document.getElementById('log-console');
                logConsole.innerHTML = state.logs.map(log => `<div>${log}</div>`).join('');
                logConsole.scrollTop = logConsole.scrollHeight;
            }

            // API Actions
            async defCall(url) {
                try {
                    await fetch(url, { method: 'POST' });
                } catch (err) {
                    console.error("API Error:", err);
                }
            }

            function toggleBot() { defCall('/api/toggle-bot'); }
            function resetBaseline() { defCall('/api/reset-baseline'); }
            function forceDrop() { defCall('/api/force-drop'); }
            function manualBuy() { defCall('/api/manual-buy'); }
            function liquidate() { defCall('/api/liquidate'); }

            async function updateParams(event) {
                event.preventDefault();
                const symbol = document.getElementById('param-symbol').value;
                const threshold = parseFloat(document.getElementById('param-threshold').value) / 100;
                const offset = parseFloat(document.getElementById('param-offset').value);

                try {
                    await fetch('/api/update-params', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ symbol, drop_threshold: threshold, strike_offset: offset })
                    });
                } catch (err) {
                    console.error("Failed to update parameters:", err);
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
