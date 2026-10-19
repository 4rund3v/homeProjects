# 02 — Prometheus histograms: how p95 actually gets computed

## The two metric families

A Prometheus `Histogram` exports three series per label-set:

```
http_request_duration_seconds_bucket{endpoint="/api/products", le="0.05"} 12345
http_request_duration_seconds_count{endpoint="/api/products"}          98765
http_request_duration_seconds_sum{endpoint="/api/products"}            4567.8
```

`le` is the bucket label. The bucket `le="0.05"` means "requests with duration ≤ 0.05 s". There is an implicit `le="+Inf"` bucket that always equals the count.

## `histogram_quantile` — the only way

You *cannot* get a p95 from one scrape of one histogram. You must `rate()` the counts over a window, then interpolate within the bucket that straddles 0.95:

```
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint)
)
```

The `sum ... by (le, endpoint)` is critical: without it you get p95 *per pod*, not p95 *for the endpoint*. The `by (le, endpoint)` keeps the le label so the quantile function knows which bucket to interpolate into.

## The interpolation is linear within the straddling bucket

If the p95 position falls in the `le="0.25"` bucket (i.e. 80% of requests are ≤ 0.1 s, 96% are ≤ 0.25 s), `histogram_quantile` reports a value *between* 0.1 and 0.25, linearly interpolated. The number you see is **not** the latency of any single request. It is the estimated p95. The closer your buckets are to the SLO range, the more the number means.

This is the #1 source of "our p95 dashboard says 0.2 s but our actual p95 is 0.15 s" complaints. It is bucket resolution, not a bug.

## Bucket +Inf and the `+Inf` trap

```
http_request_duration_seconds_bucket{le="+Inf"}  =  total_requests
```

If you see p99 report as something close to your max bucket *every* time, you are in +Inf interpolation. The fix: widen the buckets (add 2.5, 5, 10) or narrow the SLO range.

## Scrape interval and the 5-minute window

`rate(...[5m])` divides by the *actual* number of scrapes in the window, not 300 s. If your scrape interval is 60 s, a 5-minute window has ~5 samples. A spike that lasts 10 s is one sample — it shows up in the rate, but the `by (le)` sum loses bucket shape.

That is why lab 5 in `project/labs/break-the-system.md` (scrape interval blind spot) exists. Scrape interval is a *measurement resolution*, not a detail.

## Cardinality of `le` labels

Each histogram series has 10–12 buckets × N label-sets. That is why `observability/02-cardinality` is a separate doc — adding a label to a histogram multiplies your series count by the bucket count.
