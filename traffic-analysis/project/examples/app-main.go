# Reference: app main.go

Not a deliverable — a 100-line Go HTTP service that does *just enough* to produce traffic, latency, and a Postgres query per request.

```go
package main

import (
  "database/sql"
  "fmt"
  "log"
  "net/http"
  "os"
  "time"

  "github.com/jackc/pgx/v5/pgxpool"
  "github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
  db    *pgxpool.Pool
  p50   = httpHistogram("http_request_duration_seconds", "Request latency in seconds", []float64{.005,.01,.025,.05,.1,.25,.5,1.0,2.5,5.0,10.0})
)

func main() {
  dsn := os.Getenv("DATABASE_URL")
  pool, _ := pgxpool.New(dsn)
  pool.MaxConns = 25   // the pool is the single most important thing to observe
  db = pool

  http.HandleFunc("/api/products", products)
  http.HandleFunc("/api/orders", orders)
  http.Handle("/metrics", promhttp.Handler())
  log.Fatal(http.ListenAndServe(":8080", nil))
}

func products(w http.ResponseWriter, r *http.Request) {
  start := time.Now()
  var n int
  db.QueryRow(`SELECT COUNT(*) FROM products`).Scan(&n)
  fmt.Fprintf(w, `{"count":%d}`, n)
  p50.Observe(time.Since(start).Seconds())
}
```

The `httpHistogram` helper is a thin wrapper around `prometheus.NewHistogramVec` with labels `["endpoint"]`. Do not invent labels — cardinality traps are covered in `observability/02-cardinality`.

## What to observe from the app

- `http_request_duration_seconds_bucket` — the raw buckets Prometheus stores.
- `http_request_duration_seconds_count` — total requests (RPS source).
- `http_request_duration_seconds_sum` — total time (mean = sum/count).

## Do not observe from the app

- Per-request IDs, per-user labels. Cardinality explodes. Use traces for that (`observability/03`).
