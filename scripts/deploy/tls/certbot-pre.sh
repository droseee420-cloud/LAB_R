#!/bin/sh
set -eu

containers=$(docker ps -q \
  --filter label=com.docker.compose.project=refraction \
  --filter label=com.docker.compose.service=proxy)
if [ -n "$containers" ]; then
  docker stop $containers >/dev/null
fi
