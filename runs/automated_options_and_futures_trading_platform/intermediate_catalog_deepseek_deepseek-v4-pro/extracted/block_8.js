const ws = new WebSocket(`ws://${location.host}`);
const priceSpan = document.getElementById('price');
const tbody = document.querySelector('#trades tbody');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'price') {
    priceSpan.textContent = msg.data.price.toFixed(2);
  } else if (msg.type === 'newTrade') {
    addTradeRow(msg.data);
  }
};

function addTradeRow(trade) {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td>${new Date(trade.timestamp).toLocaleString()}</td>
    <td>${trade.action}</td>
    <td>${trade.symbol}</td>
    <td>${trade.quantity}</td>
    <td>${trade.price}</td>
    <td>${trade.status}</td>
  `;
  tbody.prepend(tr);  // newest first
}

// Load initial trades from REST
fetch('/api/trades')
  .then(res => res.json())
  .then(trades => trades.forEach(addTradeRow));
