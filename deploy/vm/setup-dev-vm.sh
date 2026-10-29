#!/usr/bin/env bash
# One-time setup of the shared development VM (Ubuntu 22.04/24.04). Run as root:
#   sudo ADMIN_USER=azureuser ./setup-dev-vm.sh
# Result: shared project folder /srv/ff/project (edit group + read-only group), shared Python venv,
#         key-only SSH for named accounts, nightly backup job, no public dev ports.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
ADMIN_USER="${ADMIN_USER:?set ADMIN_USER to the VM admin account name (e.g. azureuser) so it is not locked out}"
HERE="$(cd "$(dirname "$0")" && pwd)"

apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip acl unzip zip curl fail2ban unattended-upgrades ca-certificates
if ! command -v node >/dev/null; then curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs; fi
if ! command -v az >/dev/null; then curl -sL https://aka.ms/InstallAzureCLIDeb | bash; fi

groupadd -f ffdev; groupadd -f ffview; groupadd -f ffops
usermod -aG ffops,ffdev "$ADMIN_USER"
install -d -m 2770 -g ffdev /srv/ff/project
chmod 0755 /srv/ff
# files copied in by the admin are owned by root: hand them to the editors' group
chgrp -R ffdev /srv/ff/project
chmod -R g+rwX,o-rwx /srv/ff/project
find /srv/ff/project -type d -exec chmod g+s {} +
# editors: read/write (setgid keeps group ownership). viewers: read-only via ACL (also default ACL for new files).
setfacl -R -m g:ffview:rX /srv/ff/project
setfacl -R -d -m g:ffdev:rwX,g:ffview:rX /srv/ff/project
setfacl -m g:ffview:rx /srv/ff
install -d -m 750 -g ffops /srv/ff/backups
echo 'umask 002' > /etc/profile.d/ff-umask.sh

[ -d /srv/ff/venv ] || python3 -m venv /srv/ff/venv
chgrp -R ffdev /srv/ff/venv; chmod -R g+rwX /srv/ff/venv
if [ -f /srv/ff/project/backend/requirements-dev.txt ]; then
  /srv/ff/venv/bin/pip install -q -r /srv/ff/project/backend/requirements-dev.txt
  chgrp -R ffdev /srv/ff/venv; chmod -R g+rwX /srv/ff/venv
fi

install -m 755 "$HERE/backup-source.sh" /usr/local/bin/ff-backup
install -m 755 "$HERE/ff-user.sh" /usr/local/bin/ff-user
install -m 755 "$HERE/ff-run.sh" /usr/local/bin/ff-run
# backup destination: edit /etc/default/ff-backup later if you did not pass BACKUP_ACCOUNT now
echo "BACKUP_ACCOUNT=${BACKUP_ACCOUNT:-}" > /etc/default/ff-backup; chmod 644 /etc/default/ff-backup
echo "15 2 * * * root . /etc/default/ff-backup; export BACKUP_ACCOUNT; /usr/local/bin/ff-backup nightly >> /var/log/ff-backup.log 2>&1" > /etc/cron.d/ff-backup

# SSH: keys only, named groups only, no root
cat > /etc/ssh/sshd_config.d/99-ff.conf <<SSH
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
AllowGroups ffdev ffview ffops
MaxAuthTries 3
ClientAliveInterval 300
SSH
sshd -t && systemctl reload ssh || systemctl reload sshd
systemctl enable --now fail2ban unattended-upgrades
echo
echo "Done. Next: copy the project to /srv/ff/project, then   sudo ff-user add alice dev \"ssh-ed25519 AAAA...\""
