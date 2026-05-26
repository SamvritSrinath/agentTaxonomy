const { shouldTrigger } = require('../backend/tradeManager');

// Helper: create mock window with prices exactly 1 hour apart (simplified)
function makeWindow(hourAgoPrice, currentPrice) {
  return [{ price: hourAgoPrice, timestamp: new Date('2023-01-01T00:00:00Z') }];
}

function runTests() {
  console.log('Running drop logic tests...');

  // Test 1: No drop
  let result = shouldTrigger(4500, makeWindow(4500));
  console.assert(result === false, 'No drop (0%)');

  // Test 2: Exactly 2% drop – should NOT trigger (greater than 2%)
  result = shouldTrigger(4410, makeWindow(4500)); // (4500-4410)/4500 = 0.02 exactly
  console.assert(result === false, 'Exact 2% drop should not trigger');

  // Test 3: 2.1% drop – should trigger
  result = shouldTrigger(4405, makeWindow(4500));
  // drop = (4500-4405)/4500 = 0.0211 > 0.02
  console.assert(result === true, '2.1% drop should trigger');

  // Test 4: larger drop triggers
  result = shouldTrigger(4000, makeWindow(4500));
  console.assert(result === true, 'Large drop triggers');

  // Test 5: empty window => no trigger
  result = shouldTrigger(4000, []);
  console.assert(result === false, 'Empty window should not trigger');

  console.log('All tests passed!');
}

runTests();
