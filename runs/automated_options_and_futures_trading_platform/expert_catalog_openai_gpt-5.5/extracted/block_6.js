const axios = require("axios");
const {
  config,
  assertBrokerageCredentialsPresent,
  assertPaperEndpointOnly
} = require("./config");

const DEFAULT_INDEX_FUNDS = ["SPY", "QQQ", "IWM", "DIA"];

class BrokerageClient {
  constructor({
    httpClient = axios,
    apiBaseUrl = config.paperApiBaseUrl,
    apiKey = config.brokerageApiKey,
    apiSecret = config.brokerageApiSecret
  } = {}) {
    assertPaperEndpointOnly(apiBaseUrl);

    this.httpClient = httpClient;
    this.apiBaseUrl = apiBaseUrl;
    this.apiKey = apiKey;
    this.apiSecret = apiSecret;
  }

  ensureReady() {
    assertBrokerageCredentialsPresent();
  }

  async getIndexFundData(symbols = DEFAULT_INDEX_FUNDS) {
    this.ensureReady();

    assertPaperEndpointOnly(this.apiBaseUrl);

    const response = await this.httpClient.get(
      `${this.apiBaseUrl}/v1/marketdata/index-funds`,
      {
        params: {
          symbols: symbols.join(",")
        },
        headers: {
          "X-API-Key": this.apiKey,
          "X-API-Secret": this.apiSecret
        },
        timeout: 10000
      }
    );

    return response.data;
  }
}

module.exports = {
  BrokerageClient,
  DEFAULT_INDEX_FUNDS
};
