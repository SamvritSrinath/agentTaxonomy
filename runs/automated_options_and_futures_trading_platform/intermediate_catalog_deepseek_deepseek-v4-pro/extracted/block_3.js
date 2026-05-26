const Database = require('better-sqlite3');

let db;

function initDB() {
  db = new Database('trade_history.db');
  db.pragma('journal_mode = WAL');
  db.exec(`
    CREATE TABLE IF NOT EXISTS trades (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      action TEXT NOT NULL,
      symbol TEXT NOT NULL,
      quantity INTEGER NOT NULL,
      price REAL NOT NULL,
      status TEXT NOT NULL
    )
  `);
  return db;
}

function saveTrade(trade) {
  const stmt = db.prepare(`
    INSERT INTO trades (timestamp, action, symbol, quantity, price, status)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  stmt.run(
    trade.timestamp,
    trade.action,
    trade.symbol,
    trade.quantity,
    trade.price,
    trade.status
  );
}

function getRecentTrades(limit = 50) {
  const rows = db.prepare(
    'SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?'
  ).all(limit);
  return rows;
}

module.exports = { initDB, saveTrade, getRecentTrades };
