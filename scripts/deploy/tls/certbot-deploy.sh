#!/bin/sh
set -eu

lineage=${RENEWED_LINEAGE:-/etc/letsencrypt/live/refraction.info}
if [ "$(basename "$lineage")" != "refraction.info" ]; then
  exit 0
fi

target=/opt/refraction-lab/shared/tls
install -d -m 750 -o 101 -g 101 "$target"
install -m 640 -o 101 -g 101 "$lineage/fullchain.pem" "$target/fullchain.pem.new"
install -m 640 -o 101 -g 101 "$lineage/privkey.pem" "$target/privkey.pem.new"
mv -f "$target/fullchain.pem.new" "$target/fullchain.pem"
mv -f "$target/privkey.pem.new" "$target/privkey.pem"
