#!/usr/bin/env bash
# Install Calibre (ebook-convert) for digitize-book skill.
# Tries current environment first, then Docker, then SSH -> Docker on VPS.

set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-openclaw-b60d-openclaw-1}"
VPS_HOST="${VPS_HOST:-hostinger-vps}"
APT_CMD="${APT_CMD:-/usr/bin/apt-get}"

if [[ ! -x "$APT_CMD" ]]; then
  APT_CMD="apt-get"
fi

install_in_current_env() {
  if ! command -v "$APT_CMD" >/dev/null 2>&1; then
    return 1
  fi
  if [[ "$(id -u)" -ne 0 ]]; then
    return 1
  fi

  "$APT_CMD" update
  DEBIAN_FRONTEND=noninteractive "$APT_CMD" install -y --no-install-recommends calibre
}

verify_in_current_env() {
  if command -v ebook-convert >/dev/null 2>&1; then
    ebook-convert --version
    return 0
  fi
  return 1
}

verify_in_container() {
  docker exec "$CONTAINER_NAME" bash -lc 'command -v ebook-convert >/dev/null 2>&1 && ebook-convert --version'
}

ensure_node_runtime_access_in_container() {
  docker exec -u root "$CONTAINER_NAME" bash -lc '
    if id node >/dev/null 2>&1; then
      mkdir -p /data/.config/calibre
      chown -R node:node /data/.config
      chmod -R u+rwX,go-rwx /data/.config
      su -s /bin/bash -c "command -v ebook-convert >/dev/null 2>&1 && ebook-convert --version >/dev/null" node
    fi
  '
}

if verify_in_current_env; then
  echo "Calibre already installed in current environment."
  exit 0
fi

echo "Calibre not found in current environment. Trying installation..."

if install_in_current_env; then
  echo "Calibre installed in current environment."
  verify_in_current_env
  exit 0
fi

if command -v docker >/dev/null 2>&1; then
  echo "Trying Docker container: ${CONTAINER_NAME}"
  docker exec -u root "$CONTAINER_NAME" bash -lc '/usr/bin/apt-get update && DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get install -y --no-install-recommends calibre'
  ensure_node_runtime_access_in_container
  verify_in_container
  echo "Calibre installed in Docker container ${CONTAINER_NAME}."
  exit 0
fi

if command -v ssh >/dev/null 2>&1; then
  echo "Trying VPS over SSH: ${VPS_HOST} (container: ${CONTAINER_NAME})"
  ssh "$VPS_HOST" "docker exec -u root \"$CONTAINER_NAME\" bash -lc '/usr/bin/apt-get update && DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get install -y --no-install-recommends calibre'"
  ssh "$VPS_HOST" "docker exec -u root \"$CONTAINER_NAME\" bash -lc 'if id node >/dev/null 2>&1; then mkdir -p /data/.config/calibre && chown -R node:node /data/.config && chmod -R u+rwX,go-rwx /data/.config && su -s /bin/bash -c \"ebook-convert --version >/dev/null\" node; fi'"
  ssh "$VPS_HOST" "docker exec \"$CONTAINER_NAME\" bash -lc 'ebook-convert --version'"
  echo "Calibre installed on VPS container ${CONTAINER_NAME}."
  exit 0
fi

echo "ERROR: could not install Calibre automatically." >&2
echo "Need one of the following:" >&2
echo "  - root + apt-get in current environment, or" >&2
echo "  - docker CLI access, or" >&2
echo "  - ssh access to ${VPS_HOST} with docker." >&2
exit 1
