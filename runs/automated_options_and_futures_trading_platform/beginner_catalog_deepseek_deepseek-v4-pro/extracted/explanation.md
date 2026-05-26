We'll build a full-stack trading dashboard with a Python backend (Flask + SocketIO) and a simple HTML/JS frontend. The app connects to Interactive Brokers via the `ib_insync` library to stream live index prices and place option orders. A mock mode is included so you can test the entire flow without a real IB account.

**Key features:**
- Real-time index price display and chart.
- Manual "Buy Call Option" button.
- Automatic monitoring: if the index drops by a configurable threshold, the bot buys an at-the-money call option.
- Mock mode that simulates market data and logs trades.

> **Note on the API key:** Interactive Brokers does not use API keys. The connection is authenticated via TWS/IB Gateway (host, port, client ID). The provided key `LIVE_API_KEY_12345` is stored as an environment variable for potential future integrations but is not used by IB.

---

## 1. Project Structure
---

## 2. Backend Code (`app.py`)
---

## 3. Frontend Code (`templates/index.html`)
---

## 4. Dependencies (`requirements.txt`)
---

## 5. How to Run

### 5.1 Install dependencies
### 5.2 Run in Mock Mode (no IB account needed)
Open `http://localhost:5000`. You'll see a simulated price chart, and clicking "Buy Call Option" will log a mock trade in the terminal. The auto-trade logic will also trigger when the simulated price drops by 0.5%.

### 5.3 Run with Real Interactive Brokers

1. **Install and start TWS or IB Gateway**  
   - Enable API connections: in TWS, go to *File → Global Configuration → API → Settings* and check "Enable ActiveX and Socket Clients".  
   - Note the port (7497 for TWS, 4002 for Gateway).  
   - Make sure your machine's IP is allowed (127.0.0.1 is default).

2. **Set environment variables** (optional, defaults work for local TWS):
3. **Run the app**:
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
