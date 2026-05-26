// Check if current price is >2% below the price from 1 hour ago.
// windowPrices: array of {price, timestamp} sorted chronologically, max 1h old.
function shouldTrigger(currentPrice, windowPrices) {
  if (windowPrices.length === 0) return false;

  // Oldest price in the window (approximately 1h ago)
  const oldestPrice = windowPrices[0].price;
  const drop = (oldestPrice - currentPrice) / oldestPrice;
  return drop > 0.02;
}

module.exports = { shouldTrigger };
