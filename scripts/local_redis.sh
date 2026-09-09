#!/usr/bin/env bash
set -euo pipefail

redis_bin="/home/sudosu/miniforge3/envs/ryuk-ai/bin"
state_dir="/home/sudosu/.local/share/ryuk/redis"
pid_file="$state_dir/redis.pid"
log_file="$state_dir/redis.log"
port="56379"

mkdir -p "$state_dir"

case "${1:-status}" in
  start)
    "$redis_bin/redis-server" \
      --bind 127.0.0.1 \
      --protected-mode yes \
      --port "$port" \
      --daemonize yes \
      --dir "$state_dir" \
      --pidfile "$pid_file" \
      --logfile "$log_file" \
      --save "" \
      --appendonly no
    ;;
  stop)
    "$redis_bin/redis-cli" -h 127.0.0.1 -p "$port" shutdown nosave
    ;;
  status)
    "$redis_bin/redis-cli" -h 127.0.0.1 -p "$port" ping
    ;;
  test)
    export REDIS_TEST_URL="redis://127.0.0.1:$port/15"
    "$redis_bin/python" -m pytest tests/test_distributed_control_plane_integration.py \
      -k redis -v
    ;;
  *)
    echo "usage: $0 {start|stop|status|test}" >&2
    exit 2
    ;;
esac
