#!/usr/bin/env bash
# 가젯 없이 PC에서 실사 플로우 전체를 실행한다 (시뮬레이터 모드).
#   ./run.sh                  전체 실행 (불일치 시 수량 정정 + 샘플 메모)
#   ./run.sh --on-mismatch ask   불일치 건마다 처리 방법과 메모를 직접 입력
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f assets/default-rack.png ]; then
  python3 tools/make_sample_images.py
fi
exec python3 warehouse_gadget.py run --demo-notes "$@"
