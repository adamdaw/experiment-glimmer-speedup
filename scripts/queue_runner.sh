#!/bin/bash
# Sequential job queue: runs the first line of queue.txt not yet listed in queue.done; append lines to queue.txt anytime.
# A line "STOP" halts the runner. One job at a time => never two generating models.
cd "${GS_WORKDIR:-$(dirname "$0")/..}"
touch queue.txt queue.done
while true; do
  job=$(grep -vxF -f queue.done queue.txt | grep -v '^#' | grep -v '^$' | head -1)
  if [ -z "$job" ]; then sleep 30; continue; fi
  [ "$job" = "STOP" ] && { echo "$(date -Is) STOP"; exit 0; }
  echo "$(date -Is) START $job"
  bash -c "$job"; rc=$?
  echo "$(date -Is) END rc=$rc $job"
  echo "$job" >> queue.done
done
