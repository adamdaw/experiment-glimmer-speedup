#!/bin/bash
# Per-minute memory/GTT/VRAM log. GS_DRM_DEVICE: amdgpu sysfs device dir; GS_BASE / GS_PROD_BASE: llama-swap servers.
DEV="${GS_DRM_DEVICE:-/sys/class/drm/card1/device}"
TEST="${GS_BASE:-http://localhost:8080}"
PROD="${GS_PROD_BASE:-}"
while true; do
  awk -v t="$(date +%FT%T)" '/MemAvailable/{a=$2}/SwapTotal/{st=$2}/SwapFree/{sf=$2}END{printf "%s avail=%.1fGiB swap_used=%.2fGiB ", t, a/1048576, (st-sf)/1048576}' /proc/meminfo
  g=$(cat "$DEV/mem_info_gtt_used"); v=$(cat "$DEV/mem_info_vram_used")
  p=$(curl -s -m2 "$PROD/running" | python3 -c 'import json,sys;print(",".join(m["model"] for m in json.load(sys.stdin)["running"]))' 2>/dev/null)
  t=$(curl -s -m2 "$TEST/running" | python3 -c 'import json,sys;print(",".join(m["model"]+":"+m["state"] for m in json.load(sys.stdin)["running"]))' 2>/dev/null)
  printf "gtt=%.1fGiB vram=%.1fGiB prod=[%s] test=[%s]\n" $(echo "$g/1073741824" | bc -l) $(echo "$v/1073741824" | bc -l) "$p" "$t"
  sleep 60
done
