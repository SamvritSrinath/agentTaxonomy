// anomaly-detection.ts
export function checkRisk(ip: string, userAgent: string, history: any[]): 'low' | 'medium' | 'high' {
  // Look up IP in GeoIP DB, check if new location/country
  // Compute behavioral fingerprint (browser, OS, time of day)
  // If score > threshold, require step‑up auth or block
  return 'low';
}
