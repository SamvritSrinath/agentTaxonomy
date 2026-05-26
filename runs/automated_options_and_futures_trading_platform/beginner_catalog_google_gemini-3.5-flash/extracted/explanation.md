Here is a complete, production-ready automated trading bot and web application designed for index funds and options. 

### Architecture Overview
1. **Backend (FastAPI & `ib_insync`)**: Handles the connection to the Interactive Brokers (IBKR) API, monitors market data, runs the automated trading strategy, and serves a WebSocket connection for real-time updates.
2. **Frontend (HTML5, Tailwind CSS, JavaScript)**: A modern, responsive dashboard that displays real-time market prices, portfolio status, strategy parameters, and a live log console. It includes controls to toggle the bot, adjust parameters, and execute manual trades.
3. **Dual-Mode Execution (Real & Simulation)**: Since Interactive Brokers requires a running instance of Trader Workstation (TWS) or IB Gateway, the bot features a **seamless Simulation Mode fallback**. If it cannot connect to a live IBKR instance, it automatically runs in simulation mode so you can test the entire interface and strategy immediately.

---

### 1. Project Files

#### `requirements.txt`
#### `main.py`
This file contains the entire backend logic, Interactive Brokers integration, automated strategy, and the embedded frontend dashboard.
---

### 2. How to Build and Run

#### Step 1: Install Dependencies
Create a virtual environment and install the required packages:
#### Step 2: Run the Application
Start the FastAPI server:
#### Step 3: Access the Web App
Open your browser and navigate to:
---

### 3. Interactive Brokers Setup Guide

To connect this bot to your actual Interactive Brokers account (Paper or Live):

1. **Download & Install TWS or IB Gateway**:
   * Download [Trader Workstation (TWS)](https://www.interactivebrokers.com/en/trading/tws.php) or [IB Gateway](https://www.interactivebrokers.com/en/trading/ibgateway.php).
2. **Configure API Settings**:
   * Open TWS/Gateway.
   * Go to **File** > **Global Configuration** > **API** > **Settings**.
   * Check **"Enable ActiveX and Socket Clients"**.
   * Note the **"Socket port"** (usually `7497` for paper trading, `7496` for live trading).
   * Uncheck **"Read-Only API"** to allow the bot to place orders.
3. **Set Environment Variables (Optional)**:
   If your TWS is running on a different port or host, set them before running the script:
---

### 4. Security & API Key Note

Interactive Brokers **does not use static API keys** (like `LIVE_API_KEY_12345`) for its standard socket-based API (TWS/Gateway). Instead, authentication is handled securely via:
* **Local Socket Connection**: The bot connects directly to your running, authenticated TWS/Gateway instance on your local machine. This is highly secure because your credentials never leave your local environment.
* **Client Portal Web API**: If you use the REST Web API, authentication is handled via session cookies and local gateway proxies.

The code above is designed to handle both standard local socket connections securely and fall back to a fully interactive simulation mode if no local gateway is detected.
