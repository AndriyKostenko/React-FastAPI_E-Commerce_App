#!/bin/bash
set -e

# Create media directories if they don't exist
mkdir -p /media/generated
mkdir -p /media/images
mkdir -p /media/icons

# Fix permissions for taskiq_user (uid 1008)
# This runs AFTER volume mount, so it will fix any permission issues from the volume
chmod -R 755 /media
chown -R 1008:1008 /media

# Switch to taskiq_user and exec the taskiq worker
exec gosu taskiq_user "$@"
