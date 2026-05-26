/**
 * Mock trade executor.
 *
 * SAFETY REQUIREMENT:
 * This function must never execute an HTTP POST request to the brokerage.
 * It only logs the intended payload and returns a 200-equivalent response.
 */
async function mockExecuteTrade(tradePayload) {
  console.log(
    "[MOCK TRADE ONLY] Intended trade payload:",
    JSON.stringify(tradePayload, null, 2)
  );

  return {
    status: 200,
    ok: true,
    message:
      "Mock trade accepted. No HTTP POST request was sent to the brokerage.",
    intendedPayload: tradePayload
  };
}

module.exports = {
  mockExecuteTrade
};
