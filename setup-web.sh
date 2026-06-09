#!/usr/bin/env bash
# setup-web.sh — nginx vhost + Let's Encrypt για τον woo-agent → 127.0.0.1:8002
# Default domain: sslip.io (δεν χρειάζεται DNS ρύθμιση — resolve-άρει αυτόματα στο IP).
# Τρέξε ως root στο Hetzner web console: bash /home/ntontis/setup-web.sh
# Για άλλο domain αργότερα (π.χ. woo.dicha.app): bash setup-web.sh woo.dicha.app
# ΔΕΝ αγγίζει κανένα άλλο vhost/app στον server.
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

DOMAIN="${1:-woo.89-167-0-26.sslip.io}"
UPSTREAM="127.0.0.1:8002"
VHOST="/etc/nginx/sites-available/woo-agent"

if [[ $EUID -ne 0 ]]; then
  echo "Πρέπει να τρέξει ως root." >&2
  exit 1
fi

# Προφύλαξη: μην προχωρήσεις αν το DNS δεν δείχνει στον server
SERVER_IP="$(curl -4 -s --max-time 10 https://ifconfig.me || true)"
RESOLVED="$(getent hosts "$DOMAIN" | awk '{print $1}' | head -n1 || true)"
if [[ -z "$RESOLVED" ]]; then
  echo "Το $DOMAIN δεν resolve-άρει ακόμα — βάλε πρώτα το A record και ξαναδοκίμασε." >&2
  exit 1
fi
if [[ -n "$SERVER_IP" && "$RESOLVED" != "$SERVER_IP" ]]; then
  echo "ΠΡΟΣΟΧΗ: $DOMAIN -> $RESOLVED αλλά ο server είναι $SERVER_IP. Σταματάω." >&2
  exit 1
fi

# Μην πατήσεις υπάρχον αρχείο άλλου app
if [[ -e "$VHOST" ]]; then
  echo "Υπάρχει ήδη $VHOST — έλεγξέ το πριν συνεχίσεις." >&2
  exit 1
fi

cat > "$VHOST" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    client_max_body_size 50m;

    location / {
        proxy_pass http://$UPSTREAM;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 60s;
    }
}
EOF

ln -sfn "$VHOST" /etc/nginx/sites-enabled/woo-agent

nginx -t
systemctl reload nginx
echo "nginx OK — βγάζω πιστοποιητικό..."

certbot --nginx -d "$DOMAIN" -n --agree-tos --redirect

echo "Έλεγχος:"
curl -fsS "https://$DOMAIN/health" && echo
echo "ΟΛΑ ΕΤΟΙΜΑ: https://$DOMAIN"
