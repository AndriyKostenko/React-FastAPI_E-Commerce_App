#!/bin/sh
set -e

# Substitute environment variables in the config template.
# sed replaces ${TELEGRAM_BOT_TOKEN} and ${TELEGRAM_CHAT_ID} literally —
# no external envsubst binary required (busybox sh + sed is sufficient).
sed \
  -e "s|\${TELEGRAM_BOT_TOKEN}|${TELEGRAM_BOT_TOKEN}|g" \
  -e "s|\${TELEGRAM_CHAT_ID}|${TELEGRAM_CHAT_ID}|g" \
  /etc/alertmanager/alertmanager.yml.tmpl > /tmp/alertmanager.yml

exec /bin/alertmanager \
  --config.file=/tmp/alertmanager.yml \
  --storage.path=/alertmanager \
  --cluster.listen-address= \
  "$@"
