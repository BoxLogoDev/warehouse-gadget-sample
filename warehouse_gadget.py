#!/usr/bin/env python3
"""창고 재고 실사 샘플 — 진입점 CLI.

서브커맨드:
  run      실사 플로우 전체 실행 (기본값: 시뮬레이터 카메라 + 목업 계수)
  capture  빈 1곳 촬영만 수행하고 결과를 JSON으로 출력
           (Muse Gadgets Linux SDK의 system.run에서 Muse가 호출하는 진입점)
  status   가장 최근 실행의 요약 상태를 JSON으로 출력
  report   가장 최근 실행의 완료 보고를 사람이 읽는 형태로 출력

가젯 없이 PC에서:  ./run.sh   또는   python3 warehouse_gadget.py run
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import data as ewm_data  # noqa: E402
import flow  # noqa: E402
from adapters import VoiceAdapter, build_camera_adapter, build_counting_adapter  # noqa: E402

OUT_BASE = BASE / "out"
ASSETS = BASE / "assets"

# --demo-notes용 샘플 메모 (실사용 시에는 --note나 ask 모드로 실제 메모를 넣는다)
DEMO_NOTES = {
    "A-01-02": "샘플 메모: 부족분은 파손 박스로 분리 보관됨",
    "B-01-02": "샘플 메모: 인접 빈에서 초과분이 이동 적재된 것으로 보임",
}


def latest_run_dir():
    runs = sorted(p for p in OUT_BASE.glob("run-*") if (p / "result.json").exists())
    return runs[-1] if runs else None


def load_latest_report():
    run_dir = latest_run_dir()
    if run_dir is None:
        return None
    return json.loads((run_dir / "result.json").read_text(encoding="utf-8"))


def make_resolver(args, voice):
    """--on-mismatch 값에 따라 불일치 처리 콜백을 만든다."""
    if args.on_mismatch == "ask":
        def resolve(task, counted_qty, status, _voice):
            print("  불일치 처리 선택 — [c] 수량 정정(계수값으로 확정) / [a] 그대로 확정(장부값 유지)")
            choice = input("  선택 (기본 c): ").strip().lower()
            note = voice.read_note(prompt="  음성 메모(텍스트 입력, 비우려면 Enter): ")
            if choice == "a":
                return "그대로 확정", task["expected_qty"], note
            return "수량 정정", counted_qty, note
        return resolve

    base = flow.default_resolver(args.on_mismatch)

    def resolve(task, counted_qty, status, _voice):
        action, final_qty, _ = base(task, counted_qty, status, _voice)
        note = args.note or (DEMO_NOTES.get(task["bin"], "") if args.demo_notes else "")
        return action, final_qty, note
    return resolve


def cmd_run(args):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.out) if args.out else OUT_BASE / ("run-%s" % stamp)
    voice = VoiceAdapter(run_dir / "voice")
    camera = build_camera_adapter(args.camera, ASSETS)
    counting = build_counting_adapter(args.counting)
    resolver = make_resolver(args, voice)
    report = flow.run_all(camera, counting, voice, run_dir,
                          policy=args.on_mismatch, resolver=resolver)
    print("\n산출물: %s" % run_dir)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


def cmd_capture(args):
    record = ewm_data.find_inventory(args.bin)
    if record is None:
        print(json.dumps({"error": "재고에 없는 빈입니다: %s" % args.bin}, ensure_ascii=False))
        return 1
    task = {"bin": record["bin"], "sku": record["sku"],
            "product_name": record["product_name"], "expected_qty": record["expected_qty"]}
    camera = build_camera_adapter(args.camera, ASSETS)
    out_dir = OUT_BASE / "captures"
    result = camera.capture(task, out_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_status(args):
    report = load_latest_report()
    if report is None:
        print(json.dumps({"status": "no_runs", "message": "아직 실행 기록이 없습니다."},
                         ensure_ascii=False))
        return 0
    print(json.dumps({
        "status": "completed",
        "generated_at": report["generated_at"],
        "warehouse": report["warehouse"]["name"],
        "camera": report["camera"],
        "counting": report["counting"],
        "summary": report["summary"],
        "ewm_transmission": report["ewm_transmission"],
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_report(args):
    report = load_latest_report()
    if report is None:
        print("아직 실행 기록이 없습니다. 먼저 run을 실행하세요.")
        return 1
    s = report["summary"]
    print("완료 보고 — %s (%s)" % (report["warehouse"]["name"], report["generated_at"]))
    print("총 %d건 · 일치 %d · 불일치 %d (부족 %d · 초과 %d)" % (
        s["total"], s["match"], s["mismatch"], s["shortage"], s["overage"]))
    for r in report["tasks"]:
        line = "- %s 빈 %s · EWM %d / 계수 %d / 확정 %d박스 · %s" % (
            r["task_id"], r["bin"], r["expected_qty"], r["counted_qty"],
            r["final_qty"], r["action"])
        if r["note"]:
            line += " · 메모: " + r["note"]
        print(line)
    print("EWM 결과 전송: %s" % report["ewm_transmission"])
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="창고 재고 실사 샘플 (Muse Gadgets 창고 단말)")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="실사 플로우 전체 실행")
    p_run.add_argument("--camera", choices=["sim", "pi"], default="sim")
    p_run.add_argument("--counting", choices=["mock", "sam"], default="mock")
    p_run.add_argument("--on-mismatch", choices=["correct", "accept", "ask"], default="correct",
                       help="불일치 처리: correct=수량 정정, accept=그대로 확정, ask=건마다 묻기")
    p_run.add_argument("--note", default="", help="불일치 건에 공통으로 붙일 메모")
    p_run.add_argument("--demo-notes", action="store_true", help="불일치 건에 샘플 메모를 붙인다")
    p_run.add_argument("--out", default="", help="산출물 폴더 직접 지정")

    p_cap = sub.add_parser("capture", help="빈 1곳 촬영 (SDK system.run 진입점)")
    p_cap.add_argument("--bin", required=True)
    p_cap.add_argument("--camera", choices=["sim", "pi"], default="sim")

    sub.add_parser("status", help="최근 실행 요약 (JSON)")
    sub.add_parser("report", help="최근 실행 완료 보고")

    args = parser.parse_args(argv)
    if args.command in (None, "run"):
        if args.command is None:  # 인자 없이 실행하면 run 기본값으로
            args = parser.parse_args(["run"])
        return cmd_run(args)
    if args.command == "capture":
        return cmd_capture(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "report":
        return cmd_report(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
