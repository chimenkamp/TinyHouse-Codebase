#!/usr/bin/env bash
set -u

# Copy/paste any line below directly in your CLI.
# EMQX002 is currently not in TinyHouse and may fail.

echo "EMQX001 (4021)"
ssh -i ~/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=6 -p 4021 admin@132.180.196.167 "hostname; whoami; python3 --version; wormhole --version; systemctl is-active mosquitto" || true

echo "EMQX002 (4022)"
ssh -i ~/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=6 -p 4022 admin@132.180.196.167 "hostname; whoami; python3 --version; wormhole --version; systemctl is-active mosquitto" || true

echo "EMQX003 (4023)"
ssh -i ~/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=6 -p 4023 admin@132.180.196.167 "hostname; whoami; python3 --version; wormhole --version; systemctl is-active mosquitto" || true

echo "EMQX004 (4024)"
ssh -i ~/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=6 -p 4024 admin@132.180.196.167 "hostname; whoami; python3 --version; wormhole --version; systemctl is-active mosquitto" || true

echo "EMQX005 (4025)"
ssh -i ~/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=6 -p 4025 admin@132.180.196.167 "hostname; whoami; python3 --version; wormhole --version; systemctl is-active mosquitto" || true

echo "EMQX006 (4026)"
ssh -i ~/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=6 -p 4026 admin@132.180.196.167 "hostname; whoami; python3 --version; wormhole --version; systemctl is-active mosquitto" || true
