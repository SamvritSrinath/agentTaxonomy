// Fetch circuit breaker status
async function updateStatus() {
    try {
        const resp = await fetch('/circuit_status');
        const data = await resp.json();
        document.getElementById('cb-status').textContent = data.active ? 'Active' : 'HALTED';
        document.getElementById('balance').textContent = data.balance.toFixed(2);
    } catch (e) {
        console.error('Failed to fetch status', e);
    }
}

// Submit mock trade
document.getElementById('submit-trade').addEventListener('click', async () => {
    const payload = document.getElementById('trade-payload').value;
    try {
        const resp = await fetch('/execute_trade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(JSON.parse(payload))
        });
        const result = await resp.json();
        document.getElementById('trade-response').textContent = JSON.stringify(result);
    } catch (e) {
        document.getElementById('trade-response').textContent = 'Error: ' + e.message;
    }
});

// Poll status every 5 seconds
setInterval(updateStatus, 5000);
updateStatus();
