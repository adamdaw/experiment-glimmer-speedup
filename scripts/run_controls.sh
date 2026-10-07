#!/bin/bash
cd "${GS_WORKDIR:-$(dirname "$0")/..}"
for m in g-a0 g-a1; do
  python3 scripts/tplcheck_gs.py $m > runs/tplcheck_$m.txt 2>&1
  python3 scripts/toolsmoke_gs.py $m --out runs/toolsmoke_$m.jsonl > runs/toolsmoke_$m.txt 2>&1
done
echo CONTROLS_DONE
