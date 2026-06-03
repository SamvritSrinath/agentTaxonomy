const path = require("path");
const dotenv = require("dotenv");

dotenv.config({
  path: path.resolve(process.cwd(), ".env")
});

const PAPER_API_BASE_URL = "https://paper-api.brokerage.com";

const config = {
  paperApiBaseUrl: PAPER_API_BASE_URL,

  brokerageApiKey: process.env.BROKERAGE_API_KEY,
  brokerageApiSecret: process.env.BROKERAGE_API_SECRET,

  port: Number(process.env.PORT || 4000),
  pollIntervalMs: Number(process.env.POLL_INTERVAL_MS || 15000),
  simulatedStartBalance: Number(process.env.SIMULATED_START_BALANCE || 25000)
};

function assertBrokerageCredentialsPresent() {
  if (!config.brokerageApiKey || !config.brokerageApiSecret) {
    throw new Error(
      "Missing BROKERAGE_API_KEY or BROKERAGE_API_SECRET. Load them from backend/.env only."
    );
  }
}

function assertPaperEndpointOnly(apiBaseUrl) {
  if (apiBaseUrl !== PAPER_API_BASE_URL) {
    throw new Error(
      `Unsafe brokerage endpoint blocked. Only ${PAPER_API_BASE_URL} is allowed.`
    );
  }
}

module.exports = {
  config,
  PAPER_API_BASE_URL,
  assertBrokerageCredentialsPresent,
  assertPaperEndpointOnly
};
