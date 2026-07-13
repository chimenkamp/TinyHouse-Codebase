#!/usr/bin/env bash
set -u

# Quick SSH health check for EMQX001..EMQX006 via DNAT ports.
# Default: treat EMQX002 as expected-missing because it is currently not in TinyHouse.

HOST="${HOST:-132.180.196.167}"
SSH_USER="${SSH_USER:-admin}"
KEY_PATH="${KEY_PATH:-$HOME/.ssh/id_ed25519}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-6}"
ABSENT_NODES="${ABSENT_NODES:-EMQX002}"

NODES=(EMQX001 EMQX002 EMQX003 EMQX004 EMQX005 EMQX006)
PORTS=(4021 4022 4023 4024 4025 4026)

is_expected_absent() {
  local node="$1"
  for absent in $ABSENT_NODES; do
    if [[ "$absent" == "$node" ]]; then
      return 0
    fi
  done
  return 1
}

ok_count=0
fail_count=0
skip_count=0

echo "Checking EMQX nodes on ${HOST} as ${SSH_USER}..."
echo

for i in "${!NODES[@]}"; do
  node="${NODES[$i]}"
  port="${PORTS[$i]}"

  # Return both hostname and user so auth and identity are visible in one line.
  output="$(ssh -i "$KEY_PATH" \
    -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new \
    -o ConnectTimeout="$CONNECT_TIMEOUT" \
    -p "$port" \
    "$SSH_USER@$HOST" \
    "hostname; whoami" 2>&1)"
  rc=$?

  if [[ $rc -eq 0 ]]; then
    remote_host="$(echo "$output" | sed -n '1p')"
    remote_user="$(echo "$output" | sed -n '2p')"
    printf "[OK]   %-7s port=%-4s remote=%s user=%s\n" "$node" "$port" "$remote_host" "$remote_user"
    ok_count=$((ok_count + 1))
  else
    if is_expected_absent "$node"; then
      printf "[SKIP] %-7s port=%-4s expected-absent (%s)\n" "$node" "$port" "${output%%$'\n'*}"
      skip_count=$((skip_count + 1))
    else
      printf "[FAIL] %-7s port=%-4s %s\n" "$node" "$port" "${output%%$'\n'*}"
      fail_count=$((fail_count + 1))
    fi
  fi
done

echo
echo "Summary: OK=${ok_count} FAIL=${fail_count} SKIP=${skip_count}"

if [[ $fail_count -gt 0 ]]; then
  exit 1
fi

exit 0
