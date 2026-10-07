#!/bin/bash
# pinned revisions; low priority
set -u
D="$(realpath -m "${GS_MODEL_DIR:-./models}")"
mkdir -p "$D"
cd "$D"
M=70bf1b61ac09f91b24d39038091b41c582bc5d7a
U=faa5b025c584459c13febfa5c59883516710ae39
dl() { repo=$1; rev=$2; f=$3;
  echo "$(date -Is) start $repo@$rev $f"
  nice -n 19 hf download "$repo" "$f" --revision "$rev" --local-dir "$D" >/dev/null 2>&1 || { echo "FAIL $f"; return; }
  echo "$(date -Is) done $f $(stat -c %s "$D/$f")"; }
dl meta-models/Muse-Glimmer-30B-GGUF $M dflash-Muse-Glimmer-30B-Q4_K_M.gguf
dl meta-models/Muse-Glimmer-30B-GGUF $M Muse-Glimmer-30B-KQuant-Dynamic-Q4_K_XL.gguf
dl unsloth/Muse-Glimmer-30B-GGUF $U Muse-Glimmer-30B-UD-Q5_K_M.gguf
dl unsloth/Muse-Glimmer-30B-GGUF $U Muse-Glimmer-30B-UD-Q6_K_XL.gguf
# Added for the public bundle: the Q8_0 target already existed before the study, so the original script did not fetch it.
# Its sha256 matches this repo at revision $U (see README); the revision it was originally downloaded at was not recorded.
dl unsloth/Muse-Glimmer-30B-GGUF $U Muse-Glimmer-30B-Q8_0.gguf
echo ALLDONE
