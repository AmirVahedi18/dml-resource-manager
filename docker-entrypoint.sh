#!/bin/sh
# Bind-mounted host volumes (./data, ./logs) can be owned by anyone (root, a
# different uid, etc). Fix ownership to the dmlapp user before dropping
# privileges so RotatingFileHandler can always write to /app/logs/app.log.
set -e

chown -R dmlapp:dmlapp /app/data /app/logs

exec su -s /bin/sh -c 'exec "$0" "$@"' dmlapp -- "$@"
