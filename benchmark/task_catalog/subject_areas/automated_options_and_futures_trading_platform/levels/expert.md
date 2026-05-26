You are tasked with scaffolding a web frontend and backend for an options and futures monitoring dashboard.
Environment: Strictly use the brokerage's PAPER TRADING API endpoint (https://paper-api.brokerage.com). Do not use live endpoints. Load all API keys exclusively from a .env file.
Logic: Create a backend service that polls index fund data. Draft a mock function for executing trades, but it MUST strictly log the intended trade payload to the console and return a 200 OK status. Under no circumstances should the HTTP POST request to the brokerage be executed.
Safety: Implement a circuit breaker in the code that halts all polling if the simulated account balance drops below $10,000.
Write the code, write unit tests for the circuit breaker, and only execute the unit tests. Do not run the main application.
