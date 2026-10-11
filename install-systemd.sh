#!/usr/bin/env bash
# Run the checker every 10 minutes as a systemd user timer (Linux).
# Usage: ./install-systemd.sh            install and start
#        ./install-systemd.sh --remove   stop and remove
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
UNITS="$HOME/.config/systemd/user"

if [[ "${1:-}" == "--remove" ]]; then
    systemctl --user disable --now udi-checker.timer 2>/dev/null || true
    rm -f "$UNITS/udi-checker.service" "$UNITS/udi-checker.timer"
    systemctl --user daemon-reload
    echo "Removed."
    exit 0
fi

mkdir -p "$UNITS"
cat > "$UNITS/udi-checker.service" <<UNIT
[Unit]
Description=Check the police/UDI booking calendar for free appointments
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$DIR
ExecStart="$DIR/.venv/bin/python" checker.py
TimeoutStartSec=10min
UNIT

cat > "$UNITS/udi-checker.timer" <<UNIT
[Unit]
Description=Run the UDI appointment checker every 10 minutes

[Timer]
OnCalendar=*:0/10
RandomizedDelaySec=60
Persistent=true

[Install]
WantedBy=timers.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now udi-checker.timer
systemctl --user list-timers udi-checker.timer --no-pager
if [[ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != "yes" ]]; then
    echo
    echo "NOTE: run 'loginctl enable-linger' (or 'sudo loginctl enable-linger $USER') so the timer keeps"
    echo "running when you are logged out and starts again after a reboot."
fi
