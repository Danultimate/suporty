#!/usr/bin/env bash
# deploy.sh — one-shot VPS bootstrap script
# Run as root or a user with Docker + sudo privileges.
set -euo pipefail

echo "==> Checking prerequisites..."
command -v docker  >/dev/null 2>&1 || { echo "Docker not found. Install it first."; exit 1; }
command -v docker compose >/dev/null 2>&1 || { echo "Docker Compose v2 not found."; exit 1; }

echo "==> Checking .env..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "  .env file created from .env.example"
  echo "  !! Edit .env and set OPENAI_API_KEY and POSTGRES_PASSWORD before continuing."
  echo ""
  exit 0
fi

echo "==> Building images..."
docker compose build --no-cache

echo "==> Pulling Ollama model (this may take a few minutes on first run)..."
docker compose up -d db ollama
docker compose run --rm ollama-init

echo "==> Starting full stack..."
docker compose up -d

echo "==> Waiting for app to become healthy..."
for i in $(seq 1 12); do
  if curl -sf http://localhost/health >/dev/null 2>&1; then
    echo "==> App is healthy!"
    break
  fi
  echo "   attempt $i/12..."
  sleep 5
done

echo ""
echo "Deployment complete."
echo "  Webhook:   POST http://<your-vps-ip>/api/v1/webhook/ticket"
echo "  Health:    GET  http://<your-vps-ip>/health"
echo "  Readiness: GET  http://<your-vps-ip>/api/v1/readiness"
echo ""
echo "Next steps:"
echo "  1. Point your domain to this VPS IP"
echo "  2. Provision TLS (certbot --nginx -d yourdomain.com)"
echo "  3. Uncomment the HTTPS block in docker/nginx.conf"
echo "  4. docker compose restart nginx"
