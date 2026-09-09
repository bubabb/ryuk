#!/usr/bin/env bash
set -euo pipefail

postgres_bin="/home/sudosu/miniforge3/envs/ryuk-ai/bin"
data_dir="/home/sudosu/.local/share/ryuk/postgres-data"
socket_dir="/home/sudosu/.local/share/ryuk/postgres-socket"
log_file="/home/sudosu/.local/share/ryuk/postgres.log"
port="55432"

case "${1:-status}" in
  start)
    "$postgres_bin/pg_ctl" -D "$data_dir" -l "$log_file" \
      -o "-c listen_addresses='' -c unix_socket_directories='$socket_dir' -c port=$port" \
      start
    ;;
  stop)
    "$postgres_bin/pg_ctl" -D "$data_dir" stop -m fast
    ;;
  status)
    "$postgres_bin/pg_ctl" -D "$data_dir" status
    ;;
  test)
    export POSTGRES_TEST_URL="postgresql://ryuk_app@/ryuk_test?host=$socket_dir&port=$port"
    "$postgres_bin/python" -m pytest \
      tests/test_distributed_control_plane_integration.py::test_real_postgresql_records_are_durable_and_tenant_scoped \
      -v
    ;;
  *)
    echo "usage: $0 {start|stop|status|test}" >&2
    exit 2
    ;;
esac
