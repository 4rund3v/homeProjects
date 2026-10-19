# Examples: k6 ramp script and the promql to read

## k6-ramp.js (learning shape)

```js
import http from 'k6/http';
import { check } from 'k6';

const base = 'http://<vip>/api';

export const options = {
  scenarios: {
    ramp: {
      executor: 'ramping-vus',
      exec: ['products', 'orders'],
      startVUs: 0,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '30s', target: 50 },
        { duration: '30s', target: 100 },
        { duration: '30s', target: 200 },
        { duration: '30s', target: 400 },
        { duration: '30s', target: 800 },
        { duration: '30s', target: 0 },
      ],
    },
  },
};

export function products() {
  const r = http.get(`${base}/products`);
  check(r, { '200': (r) => r.status === 200 });
}

export function orders() {
  const r = http.post(`${base}/orders`, JSON.stringify({ item: 'x' }),
    { headers: { 'Content-Type': 'application/json' } });
  check(r, { '200': (r) => r.status === 200 });
}
```

`ramping-vus` holds each VU level for the `duration` before moving on, so the percentiles *stabilize* at each level. A simple `stages: [{duration, target}]` without the hold does not give a steady state.

## The promql you read during the ramp

```
# Tail ratio — the knee detector
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[1m])) by (le, endpoint))
/
histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[1m])) by (le, endpoint))

# Delivered RPS (the actual, not the target)
sum(rate(http_request_duration_seconds_count[1m]))

# Pool state
max(kube_pod_container_... )  # or the app's own pool_in_use gauge
pool_in_use
pool_idle

# The gap: app p99 vs DB mean
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[1m])) by (le, endpoint))
-
avg(pg_stat_statements_mean_exec_time)
```

Run the ramp. Open a Grafana dashboard with the four queries. As the ramp climbs, the tail ratio crosses ~5, the pool pins, delivered RPS flattens, and the gap grows. *All four move together* at the knee. That co-movement is the signature.
