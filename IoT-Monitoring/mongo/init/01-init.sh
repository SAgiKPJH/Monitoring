#!/bin/bash
# Runs once, on first container start (empty data dir), via the official mongo entrypoint.
# Creates the application user, the "readings" collection and its query index.
set -euo pipefail

: "${MONGO_INITDB_DATABASE:=monitoring}"
: "${MONGO_APP_USERNAME:=iot}"
: "${MONGO_APP_PASSWORD:=iotpass}"

echo "[init] creating user '${MONGO_APP_USERNAME}' + collection in db '${MONGO_INITDB_DATABASE}'"

mongosh --host 127.0.0.1 \
  -u "${MONGO_INITDB_ROOT_USERNAME}" -p "${MONGO_INITDB_ROOT_PASSWORD}" \
  --authenticationDatabase admin <<EOF
const target = db.getSiblingDB("${MONGO_INITDB_DATABASE}");
target.createUser({
  user: "${MONGO_APP_USERNAME}",
  pwd: "${MONGO_APP_PASSWORD}",
  roles: [ { role: "readWrite", db: "${MONGO_INITDB_DATABASE}" } ]
});
target.createCollection("readings");
target.readings.createIndex({ deviceId: 1, timestamp: -1 });
target.createCollection("errors");
target.errors.createIndex({ deviceId: 1, timestamp: -1 });
print("[init] done");
EOF
