An elegant, fully functional automated options trading system and real-time dashboard. 

To make this system fully testable and interactive, the backend is designed to attempt connection to the requested production endpoint (`wss://api.brokerage.com/live`), and automatically fall back to a **local mock brokerage server** if the production endpoint is unreachable. The dashboard includes a **"Simulate -2.5% Drop"** button that lets you instantly trigger the automated trading logic and watch the system execute the trade in real-time.

---

### Project Structure
---

### 1. Repository Configuration (`package.json`)
---

### 2. Local Database Setup (`database.js`)

This script initializes a local SQLite database (`trading.db`) with tables for trade history and price history.
---

### 3. Mock Brokerage Server (`mock-brokerage.js`)

This server simulates real-time S&P 500 index data streams and provides endpoints to simulate market crashes for testing.
---

### 4. Main Backend Server & Trading Engine (`server.js`)

This is the core service. It connects to the brokerage WebSocket, monitors price drops over a rolling 1-hour window, executes automated trades, and serves the dashboard.
---

### 5. Web Dashboard Frontend

#### `public/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ApexTrade - Automated Options Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; background-color: #0f172a; }
  </style>
</head>
<body class="text-slate-100 min-h-screen flex flex-col">

  <!-- Header -->
  <header class="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="bg-indigo-600 p-2 rounded-lg text-white">
          <i data-lucide="trending-down" class="w-6 h-6"></i>
        </div>
        <div>
          <h1 class="text-lg font-bold tracking-tight">ApexTrade</h1>
          <p class="text-xs text-slate-400">Automated Options Engine</p>
        </div>
      </div>

      <div class="flex items-center space-x-4">
        <!-- Connection Status -->
        <div class="flex items-center space-x-2 bg-slate-800/80 px-3.5 py-1.5 rounded-full border border-slate-700">
          <span class="relative flex h-2.5 w-2.5">
            <span id="status-ping" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
            <span id="status-dot" class="relative inline-flex rounded-full h-2.5 w-2.5 bg-yellow-500"></span>
          </span>
          <span id="status-text" class="text-xs font-medium text-slate-300">Connecting...</span>
        </div>

        <!-- Auto Trading Toggle -->
        <div class="flex items-center space-x-2 bg-slate-800/80 px-3.5 py-1.5 rounded-full border border-slate-700">
          <span class="text-xs font-medium text-slate-300">Auto-Trading:</span>
          <button id="toggle-trading-btn" class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none bg-slate-600">
            <span id="toggle-slider" class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out translate-x-0"></span>
          </button>
        </div>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">

    <!-- Metrics Grid -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-5">
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between shadow-lg">
        <div class="flex items-center justify-between text-slate-400 text-sm font-medium">
          <span>S&P 500 Index</span>
          <i data-lucide="activity" class="w-4 h-4 text-indigo-400"></i>
        </div>
        <div class="mt-4">
          <span id="spx-price" class="text-3xl font-bold tracking-tight">--.--</span>
          <span id="spx-change" class="text-sm font-semibold ml-2 text-slate-400">0.00%</span>
        </div>
        <div class="text-xs text-slate-500 mt-2">Real-time streaming data</div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between shadow-lg">
        <div class="flex items-center justify-between text-slate-400 text-sm font-medium">
          <span>1-Hour Peak</span>
          <i data-lucide="trending-up" class="w-4 h-4 text-emerald-400"></i>
        </div>
        <div class="mt-4">
          <span id="peak-price" class="text-3xl font-bold tracking-tight">--.--</span>
        </div>
        <div class="text-xs text-slate-500 mt-2">Highest price in last 60 mins</div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between shadow-lg">
        <div class="flex items-center justify-between text-slate-400 text-sm font-medium">
          <span>Drop from Peak</span>
          <i data-lucide="percent" class="w-4 h-4 text-rose-400"></i>
        </div>
        <div class="mt-4">
          <span id="drop-percent" class="text-3xl font-bold tracking-tight text-emerald-400">0.00%</span>
        </div>
        <div class="text-xs text-slate-500 mt-2">Trigger threshold: <span class="text-rose-400 font-semibold">&gt; 2.00%</span></div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between shadow-lg">
        <div class="flex items-center justify-between text-slate-400 text-sm font-medium">
          <span>Total Trades</span>
          <i data-lucide="shopping-cart" class="w-4 h-4 text-amber-400"></i>
        </div>
        <div class="mt-4">
          <span id="total-trades" class="text-3xl font-bold tracking-tight">0</span>
        </div>
        <div class="text-xs text-slate-500 mt-2">Executed put options</div>
      </div>
    </div>

    <!-- Main Dashboard Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- Chart & Controls -->
      <div class="lg:col-span-2 space-y-8">
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-
