#!/usr/bin/env bash
set -euo pipefail

SESSION="device-manager"
SERVE_CMD="uv run uvicorn device_manager.infrastructure_web.main:app --reload --host 0.0.0.0 --port 8000"
WORKER_CMD="uv run celery -A device_manager.application.consumers worker --loglevel=info"
FRONTEND_CMD="cd frontend && npm run dev"

if command -v tmux >/dev/null 2>&1; then
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "tmux session '$SESSION' already exists — attaching."
    tmux attach-session -t "$SESSION"
    exit 0
  fi
  tmux new-session -d -s "$SESSION" -n serve "$SERVE_CMD"
  tmux new-window -t "$SESSION:" -n worker "$WORKER_CMD"
  tmux new-window -t "$SESSION:" -n frontend "$FRONTEND_CMD"
  echo "tmux session '$SESSION' started. Windows: serve / worker / frontend"
  echo "  Attach:  tmux attach -t $SESSION"
  echo "  Kill:    tmux kill-session -t $SESSION"
  tmux attach-session -t "$SESSION"
else
  echo "tmux not found — run these in separate terminals:"
  echo "  $SERVE_CMD"
  echo "  $WORKER_CMD"
  echo "  $FRONTEND_CMD"
fi
