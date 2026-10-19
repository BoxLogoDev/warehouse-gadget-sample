"""실사 플로우 본체 — 지시 수신부터 완료 보고까지.

웹 데모(src/main.js)의 상태 흐름과 같은 순서로 돈다:
  지시 수신 → 위치 안내 → 촬영 → 계수 → EWM 대조 →
  (불일치 시) 음성 안내 + 메모/정정 → 완료 보고(EWM 전송 시뮬레이션)

입출력은 전부 어댑터 경유라 하드웨어 교체 시 이 파일은 바뀌지 않는다.
"""

import json
import unicodedata
from datetime import datetime
from pathlib import Path

import data as ewm_data

STATUS_LABEL = {"match": "일치", "shortage": "부족", "overage": "초과"}


def _text_width(text):
    """터미널 표시 폭 — 동아시아 전각 문자는 2칸으로 센다."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
               for ch in str(text))


def _pad(text, width, align="left"):
    text = str(text)
    gap = max(0, width - _text_width(text))
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def render_report_table(report):
    """실행 결과를 지시별 표 형태 텍스트 리포트로 만든다.

    열: 지시 / 빈 / 품목 / 장부 / 실측 / 차이 / 상태 / 처리 / EWM 전송.
    EWM 전송 열은 run_all이 ewm_export.enrich_task 값을 병합한
    ewm_status가 있을 때 채워지고, 없으면 전송 상태 문구로 표시한다.
    """
    headers = ["지시", "빈", "품목", "장부", "실측", "차이", "상태", "처리", "EWM 전송"]
    aligns = ["left", "left", "left", "right", "right", "right", "center", "left", "left"]
    rows = []
    for r in report["tasks"]:
        diff = r["diff"]
        rows.append([
            r["task_id"],
            r["bin"],
            r["product_name"],
            r["expected_qty"],
            r["counted_qty"],
            ("%+d" % diff) if diff else "0",
            STATUS_LABEL.get(r["status"], r["status"]),
            r["action"],
            r.get("ewm_status") or report.get("ewm_transmission", "-"),
        ])
    widths = [max([_text_width(headers[i])] + [_text_width(row[i]) for row in rows])
              for i in range(len(headers))]

    def line(cells):
        return "  ".join(_pad(cells[i], widths[i], aligns[i]) for i in range(len(cells)))

    s = report["summary"]
    out = [
        "완료 보고 — %s (%s)" % (report["warehouse"]["name"], report["generated_at"]),
        "촬영 %s · 계수 %s · 불일치 처리 정책 %s" % (
            report.get("camera", "-"), report.get("counting", "-"),
            report.get("policy", "-")),
        "",
        line(headers),
        "  ".join("-" * w for w in widths),
    ]
    out.extend(line(row) for row in rows)
    out.append("")
    out.append("합계: 총 %d건 · 일치 %d · 불일치 %d (부족 %d · 초과 %d)" % (
        s["total"], s["match"], s["mismatch"], s["shortage"], s["overage"]))
    transfer = report.get("ewm_transfer") or {}
    if transfer:
        out.append("EWM 전송: %s — 실사 결과 %d건 반영 (페이로드 %s)" % (
            report["ewm_transmission"], transfer["posted_items"],
            Path(transfer["payload_file"]).name))
    else:
        out.append("EWM 전송: %s" % report["ewm_transmission"])
    notes = [(r["task_id"], r["note"]) for r in report["tasks"] if r.get("note")]
    if notes:
        out.append("")
        out.extend("메모 %s: %s" % (task_id, note) for task_id, note in notes)
    return "\n".join(out)


class RunLog:
    """stdout과 run.log 파일에 동시에 남기는 실행 로그."""

    def __init__(self, log_path):
        self.log_path = Path(log_path)
        self.lines = []

    def __call__(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        line = "[%s] %s" % (stamp, message)
        self.lines.append(line)
        print(line, flush=True)

    def close(self):
        self.log_path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def guide_text(task):
    """위치 안내 문구 — 웹 데모 자막 문구와 동일."""
    return "%s구역 랙 %s, 빈 %s로 이동하세요." % (
        ewm_data.zone_of_bin(task["bin"]),
        ewm_data.rack_of_bin(task["bin"]),
        task["bin"],
    )


def result_text(task, counted):
    """대조 결과 안내 문구. 불일치면 차이(부족/초과)를 숫자로 말한다."""
    expected = task["expected_qty"]
    if counted == expected:
        return "수량이 일치합니다. %s, %d박스 확인했습니다." % (task["bin"], counted)
    diff = counted - expected
    kind = "부족" if diff < 0 else "초과"
    return (
        "수량이 일치하지 않습니다. %s, 장부 %d박스, 실제 %d박스로 %d박스 %s합니다."
        % (task["bin"], expected, counted, abs(diff), kind)
    )


def default_resolver(policy):
    """불일치 처리 기본 정책: correct=수량 정정, accept=그대로 확정."""
    def resolve(task, counted_qty, status, voice):
        if policy == "accept":
            return "그대로 확정", task["expected_qty"], ""
        return "수량 정정", counted_qty, ""
    return resolve


def run_task(task, camera, counting, voice, resolver, log):
    """지시 1건의 전체 단계 실행. 반환: 결과 기록 dict."""
    log("── %s · 빈 %s · %s (%s) · 장부 %d박스" % (
        task["id"], task["bin"], task["product_name"], task["sku"], task["expected_qty"]))

    # 1~2. 지시 수신·위치 안내
    guide = guide_text(task)
    voice.announce(guide, "%s-guide" % task["id"].lower())
    log("안내: " + guide)

    # 3. 촬영
    shot = camera.capture(task, out_dir=Path(voice.voice_dir).parent / "captures")
    log("촬영: %s (%s)" % (shot["image_path"], shot["source"]))

    # 4. 계수
    counted = counting.count(shot["image_path"], task)
    log("계수: %d박스 · 라벨 %s (%s)" % (
        counted["counted_qty"], counted["label_text"], counted["engine"]))

    # 5. 대조
    expected = task["expected_qty"]
    diff = counted["counted_qty"] - expected
    status = "match" if diff == 0 else ("shortage" if diff < 0 else "overage")

    # 6. 결과 안내 + 불일치 처리
    announcement = voice.announce(result_text(task, counted["counted_qty"]),
                                  "%s-result" % task["id"].lower())
    log("안내: " + announcement["text"])
    note = ""
    if status == "match":
        action, final_qty = "일치 확정", expected
    else:
        action, final_qty, note = resolver(task, counted["counted_qty"], status, voice)
        log("처리: %s → 확정 %d박스%s" % (action, final_qty, (" · 메모: " + note) if note else ""))

    return {
        "task_id": task["id"],
        "bin": task["bin"],
        "sku": task["sku"],
        "product_name": task["product_name"],
        "expected_qty": expected,
        "counted_qty": counted["counted_qty"],
        "final_qty": final_qty,
        "status": status,
        "diff": diff,
        "action": action,
        "note": note,
        "image_path": shot["image_path"],
        "label_text": counted["label_text"],
        "voice_wav": announcement["wav_path"],
    }


def run_all(camera, counting, voice, run_dir, policy="correct", resolver=None,
            log=None, project_base=None):
    """지시 6건 전체 실행 후 result.json·run.log·report.txt를 남기고 보고 dict를 반환."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if log is None:
        log = RunLog(run_dir / "run.log")
    if resolver is None:
        resolver = default_resolver(policy)

    orders = ewm_data.work_orders()
    log("실사 작업 지시 %d건 수신 — %s" % (len(orders), ewm_data.WAREHOUSE["name"]))
    voice.announce("실사 작업 지시가 도착했습니다. %d건입니다." % len(orders), "00-start")

    records = [run_task(t, camera, counting, voice, resolver, log) for t in orders]

    summary = {
        "total": len(records),
        "match": sum(1 for r in records if r["status"] == "match"),
        "mismatch": sum(1 for r in records if r["status"] != "match"),
        "shortage": sum(1 for r in records if r["status"] == "shortage"),
        "overage": sum(1 for r in records if r["status"] == "overage"),
    }
    report = {
        "warehouse": ewm_data.WAREHOUSE,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "camera": camera.name,
        "counting": counting.name,
        "policy": policy,
        "tasks": records,
        "summary": summary,
        "ewm_transmission": "transferred (mock EWM backend)",
    }

    # 완료 보고를 목업 EWM 백엔드에 전송 반영한다:
    # OData 스타일 페이로드(run_dir/ewm_payload.json)와
    # Fiori 스타일 목업 UI 상태(ewm-ui/ewm-state.json)를 남긴다.
    import ewm_export

    base = Path(project_base) if project_base else Path(__file__).resolve().parent
    transfer = ewm_export.export(report, run_dir, base)
    report["ewm_transfer"] = transfer
    # 표 리포트의 EWM 전송 열에 쓸 상태(전송·확정/조정 상태)를 결과에 병합한다.
    enriched = {t["task_id"]: t
                for t in (ewm_export.enrich_task(r) for r in records)}
    for record in records:
        record["ewm_status"] = enriched[record["task_id"]]["ui_status"]
        record["ewm_adjustment"] = enriched[record["task_id"]]["adjustment_status"]
    log("EWM 전송: 실사 결과 %d건을 목업 백엔드에 반영 (페이로드 %s)"
        % (transfer["posted_items"], transfer["payload_file"]))

    voice.announce("실사가 완료됐습니다. %d건 중 %d건 일치, %d건 불일치입니다. "
                   "결과를 EWM에 전송합니다." % (summary["total"], summary["match"], summary["mismatch"]),
                   "99-done")
    log("완료 보고: 총 %d건 · 일치 %d · 불일치 %d (부족 %d · 초과 %d) — EWM 전송 완료(목업 백엔드)"
        % (summary["total"], summary["match"], summary["mismatch"],
           summary["shortage"], summary["overage"]))

    (run_dir / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "report.txt").write_text(
        render_report_table(report) + "\n", encoding="utf-8")
    log.close()
    return report
