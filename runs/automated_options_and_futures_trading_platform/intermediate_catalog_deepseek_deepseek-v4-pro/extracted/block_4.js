const WebSocket = require('ws');
const EventEmitter = require('events');

class BrokerClient extends EventEmitter {
  constructor(endpoint = 'wss://api.brokerage.com/live', useMock = true) {
    super();
    this.endpoint = endpoint;
    this.useMock = useMock;
    this.connect();
  }

  connect() {
    if (this.useMock) {
      this.startMock();
      return;
    }

    // Attempt real connection – fallback to mock on error
    this.ws = new WebSocket(this.endpoint);
    this.ws.on('open', () => console.log('Broker WS open'));
    this.ws.on('message', (data) => this.handleMessage(data.toString()));
    this.ws.on('error', (err) => {
      console.error('Broker WS error, switching to mock:', err.message);
      this.startMock();
    });
    this.ws.on('close', () => console.log('Broker WS closed'));
  }

  // Simulated market data
  startMock() {
    if (this.mockInterval) return;
    let price = 4500;
    console.log('Using mock broker data');
    this.mockInterval = setInterval(() => {
      // random walk
      price += (Math.random() - 0.5) * 10;
      const msg = JSON.stringify({
        symbol: 'SPX',
        price: Math.round(price * 100) / 100,
        timestamp: new Date().toISOString()
      });
      this.handleMessage(msg);
    }, 1000); // every second
  }

  handleMessage(raw) {
    try {
      const data = JSON.parse(raw);
      if (data.price && data.symbol === 'SPX') {
        this.emit('price', {
          price: data.price,
          timestamp: data.timestamp
        });
      }
    } catch (e) {
      console.error('Invalid broker message:', raw);
    }
  }
}

module.exports = BrokerClient;
