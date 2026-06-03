```typescript src/apiHelper.ts
class RateLimiter {
  private queue: (() => void)[] = [];
  private processing = false;
  private timestamps: number[] = [];
  private maxRequests: number;
  private windowMs: number;

  constructor(maxRequests: number, windowMs: number) {
    this.maxRequests = maxRequests;
    this.windowMs = windowMs;
  }

  /**
   * Enqueue a "token request". Returns a promise that resolves when the caller is allowed
   * to proceed, i.e. when rate limit allows the next request.
   */
  wait(): Promise<void> {
    return new Promise<void>((resolve) => {
      this.queue.push(resolve);
      if (!this.processing) {
        this.process();
      }
    });
  }

  private async process() {
    this.processing = true;
    while (this.queue.length > 0) {
      await this.throttle();
      const next = this.queue.shift()!;
      next();
    }
    this.processing = false;
  }

  private async throttle(): Promise<void> {
    const now = Date.now();
    // discard timestamps outside the window
    this.timestamps = this.timestamps.filter((t) => now - t < this.windowMs);
    if (this.timestamps.length >= this.maxRequests) {
      // wait until the oldest request expires
      const oldest = this.timestamps[0];
      const waitTime = oldest + this.windowMs - now;
      await new Promise((r) => setTimeout(r, waitTime));
      // re-check after waiting (in case another request snuck in)
      return this.throttle();
    }
    // record this request
    this.timestamps.push(Date.now());
  }
}

export interface ApiHelperOptions {
  /**
   * Optional rate limiting configuration.
   * If omitted, no rate limiting is applied.
   */
  rateLimit?: {
    maxRequests: number; // number of requests allowed
    windowMs: number; // time window in milliseconds
  };
}

export class ApiHelper {
  private rateLimiter: RateLimiter | null = null;

  constructor(
    private baseUrl: string,
    options?: ApiHelperOptions,
  ) {
    if (options?.rateLimit) {
      this.rateLimiter = new RateLimiter(
        options.rateLimit.maxRequests,
        options.rateLimit.windowMs,
      );
    }
  }

  async get(path: string): Promise<any> {
    await this.rateLimiter?.wait();
    const res = await fetch(`${this.baseUrl}${path}`);
    return res.json();
  }

  async post(path: string, body: any): Promise<any> {
    await this.rateLimiter?.wait();
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return res.json();
  }
}
```
