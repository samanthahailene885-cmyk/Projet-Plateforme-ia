#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python create_admin.py

NODE_VERSION=20.18.1
curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.gz" -o /tmp/node.tar.gz
tar -xzf /tmp/node.tar.gz -C /tmp
export PATH="/tmp/node-v${NODE_VERSION}-linux-x64/bin:${PATH}"
(
  cd maquette
  npm ci
  npm run build
)
