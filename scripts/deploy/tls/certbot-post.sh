#!/bin/sh
set -eu

containers=$(docker ps -aq \
  --filter label=com.docker.compose.project=refraction \
  --filter label=com.docker.compose.service=proxy)
if [ -n "$containers" ]; then
  docker start $containers >/dev/null
fi
