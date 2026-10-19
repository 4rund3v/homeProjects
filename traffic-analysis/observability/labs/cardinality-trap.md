# Lab: cardinality trap, measured

## Prereqs

- The reference app running.
- Prometheus `/targets` and the `count by (__name__)` query available.

## Step 1 — baseline series count

```
# Total series
count({__name__=~".+"})

# Series on the app's request counter
count(http_request_duration_seconds_count)
```

Record both numbers. With the reference app's labels (`endpoint` only), the counter has 2 series. The histogram has 2 × 12 buckets = 24 series.

## Step 2 — add a `user_id` label

Patch the app to add a `user_id` label to the counter, and have the test load generate 100 distinct user_ids. Rebuild, push, deploy.

Re-read:

```
count(http_request_duration_seconds_count)
# now 100 × 2 endpoints = 200 series
count(http_request_duration_seconds_bucket)
# now 100 × 2 × 12 = 2400 series
```

## Step 3 — read the Prometheus series count

```
# In Prometheus / Targets / Overview, or:
count by (__name__) ({__name__=~".+"})
```

The histogram jumped from 24 to 2400 series. That is a 100× multiplication from one label.

## Step 4 — the query cost

```
# This query used to scan 24 series. Now it scans 2400.
sum(rate(http_request_duration_seconds_count[5m])) by (endpoint)
```

Time it. The query plan now has to *aggregate* over 100 user_ids per endpoint before summing. The result is the same (you sum over `endpoint`), but the work is 100×.

## Step 5 — the alert

Add an alert:

```
count by (__name__) ({__name__=~".+"}) > 10000
```

With the `user_id` label, the histogram crosses it. The alert fires. The *diagnosis* is:

```
topk(10, count by (user_id) (http_request_duration_seconds_count))
```

Which user_id values are adding the most series. The answer: all of them, evenly. That is the signature of a per-user label, not a leak.

## Restore

Remove the `user_id` label. Re-deploy. The series count drops back to 24. The alert clears.

## Question

A service adds a `tenant` label, "but we only have 5 tenants." Is that a cardinality trap? (No. 5 values × 12 buckets × N metrics is fine. The trap is the *unbounded* label: user, IP, request, trace. 5 tenants is a small-enumerated set, the same class as `endpoint`.)
