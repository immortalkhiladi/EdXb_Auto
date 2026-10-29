#!/usr/bin/env bash
# Manage individual developer accounts on the shared dev VM (run with sudo).
#   ff-user add <name> <dev|view> "<ssh public key>"   dev = view + edit + test, view = read-only
#   ff-user remove <name>                              removes login + keys (home kept as /home/<name>.disabled)
#   ff-user list
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
cmd="${1:-}"
case "$cmd" in
  add)
    name="${2:?name}"; level="${3:?dev|view}"; key="${4:?ssh public key}"
    [[ "$name" =~ ^[a-z][a-z0-9_-]{1,30}$ ]] || { echo "invalid user name"; exit 1; }
    [[ "$key" =~ ^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp256)\  ]] || { echo "paste a public key (starts with ssh-ed25519 ...)"; exit 1; }
    case "$level" in dev) grp=ffdev ;; view) grp=ffview ;; *) echo "level must be dev or view"; exit 1 ;; esac
    id "$name" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$name"
    usermod -aG "$grp" "$name"
    install -d -m 700 -o "$name" -g "$name" "/home/$name/.ssh"
    echo "$key" > "/home/$name/.ssh/authorized_keys"; chown "$name:$name" "/home/$name/.ssh/authorized_keys"; chmod 600 "/home/$name/.ssh/authorized_keys"
    install -d -m 700 -o "$name" -g "$name" "/home/$name/ff-data"
    echo "umask 002" >> "/home/$name/.profile"
    echo "Added $name ($level). Project folder: /srv/ff/project"
    ;;
  remove)
    name="${2:?name}"
    pkill -u "$name" || true
    usermod -L -s /usr/sbin/nologin "$name"; rm -f "/home/$name/.ssh/authorized_keys"
    gpasswd -d "$name" ffdev 2>/dev/null || true; gpasswd -d "$name" ffview 2>/dev/null || true
    echo "Access removed for $name."
    ;;
  list)
    echo "Editors (ffdev):  $(getent group ffdev | cut -d: -f4)"
    echo "Read-only (ffview): $(getent group ffview | cut -d: -f4)"
    ;;
  *) echo "usage: ff-user add|remove|list"; exit 1 ;;
esac
