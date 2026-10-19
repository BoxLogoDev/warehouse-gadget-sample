"""EWM 전송 시뮬레이션 — 완료 보고를 목업 EWM 백엔드에 반영한다.

실제 SAP 시스템이 아니라 로컬 목업이다. 두 가지 산출물을 만든다:

1. OData 스타일 전송 페이로드 (run_dir/ewm_payload.json)
   EWM OData 서비스(API_PHYSICAL_INVENTORY 계열)에 실사 결과를 POST하는
   형태를 흉내 낸 JSON. 실제로 네트워크 전송은 하지 않는다.
2. UI 상태 파일 (ewm-ui/ewm-state.json)
   Fiori 스타일 목업 UI가 읽는 현재 상태 스냅샷. 실사 전에는 지시가
   "미처리"로, run 후에는 "전송·확정"으로 바뀐 것이 UI에 반영된다.
"""

import json
from pathlib import Path

import data as ewm_data

BACKEND_LABEL = "Mock EWM — simulated backend"
ODATA_SERVICE = "/sap/opu/odata/sap/API_PHYSICAL_INVENTORY_SRV"


def adjustment_status(record):
    """차이 조정 상태 — 처리 방식(action)에서 도출한다."""
    if record["status"] == "match":
        return "차이 없음"
    if record["action"] == "수량 정정":
        return "조정 전기 완료"
    if record["action"] == "그대로 확정":
        return "차이 승인 · 미조정"
    return "조정 대기"


def enrich_task(record):
    """flow 결과 기록에 EWM 필드(WT 번호·저장유형·HU·사유 코드)를 붙인다."""
    inv = ewm_data.find_inventory(record["bin"]) or {}
    order = next((o for o in ewm_data.work_orders() if o["id"] == record["task_id"]), {})
    reason_code = ewm_data.reason_for(record["status"], record.get("note", ""))
    return {
        "task_id": record["task_id"],
        "wt_no": order.get("wt_no", ""),
        "pi_doc": order.get("pi_doc", ewm_data.PI_DOCUMENT_NO),
        "bin": record["bin"],
        "storage_type": inv.get("storage_type", ""),
        "storage_type_name": ewm_data.storage_type_name(inv.get("storage_type", "")),
        "sku": record["sku"],
        "product_no": inv.get("product_no", ""),
        "product_name": record["product_name"],
        "hu": inv.get("hu", ""),
        "expected_qty": record["expected_qty"],
        "counted_qty": record["counted_qty"],
        "final_qty": record["final_qty"],
        "diff": record["diff"],
        "status": record["status"],
        "action": record["action"],
        "reason_code": reason_code,
        "reason_name": ewm_data.REASON_CODES.get(reason_code, ""),
        "adjustment_status": adjustment_status(record),
        "note": record.get("note", ""),
        "ui_status": "전송 · 확정 완료",
    }


def odata_payload(report, tasks):
    """OData 스타일 배치 전송 페이로드."""
    entries = []
    for t in tasks:
        entries.append({
            "method": "POST",
            "uri": "PhysicalInventoryItems",
            "body": {
                "WarehouseNumber": report["warehouse"]["warehouse_no"],
                "PhysicalInventoryDocument": t["pi_doc"],
                "WarehouseTask": t["wt_no"],
                "StorageBin": t["bin"],
                "StorageType": t["storage_type"],
                "Product": t["product_no"],
                "ProductName": t["product_name"],
                "HandlingUnit": t["hu"],
                "BookQuantityInBaseUnit": t["expected_qty"],
                "CountedQuantityInBaseUnit": t["counted_qty"],
                "FinalQuantityInBaseUnit": t["final_qty"],
                "DifferenceQuantity": t["diff"],
                "DifferenceReason": t["reason_code"],
                "CountingStatus": "Counted",
                "PostingStatus": "Posted" if t["adjustment_status"] != "조정 대기" else "NotPosted",
            },
        })
    return {
        "note": BACKEND_LABEL + " — no real SAP system is contacted",
        "service": ODATA_SERVICE,
        "posted_at": report["generated_at"],
        "batch_requests": entries,
    }


def monitor_snapshot(tasks_by_bin):
    """구역·랙별 현황: 빈마다 장부 수량과 실사 상태."""
    zones = []
    for zone in ewm_data.WAREHOUSE["zones"]:
        racks = []
        for rack_id in zone["racks"]:
            bins = []
            counted = 0
            for bin_id in ewm_data.RACK_BINS[rack_id]:
                inv = ewm_data.find_inventory(bin_id)
                task = tasks_by_bin.get(bin_id)
                if task:
                    count_status = task["status"]
                    counted_qty = task["counted_qty"]
                    counted += 1
                else:
                    count_status = "pending"
                    counted_qty = None
                bins.append({
                    "bin": bin_id,
                    "product_name": inv["product_name"],
                    "expected_qty": inv["expected_qty"],
                    "counted_qty": counted_qty,
                    "count_status": count_status,
                })
            racks.append({
                "id": rack_id,
                "storage_type": ewm_data.ZONE_STORAGE_TYPE[zone["id"]],
                "storage_type_name": ewm_data.storage_type_name(
                    ewm_data.ZONE_STORAGE_TYPE[zone["id"]]),
                "bins": bins,
                "progress": counted / len(bins) if bins else 0,
            })
        zones.append({"id": zone["id"], "name": zone["name"], "racks": racks})
    return {"zones": zones}


def ui_state(report, tasks):
    tasks_by_bin = {t["bin"]: t for t in tasks}
    return {
        "backend": BACKEND_LABEL,
        "generated_at": report["generated_at"],
        "warehouse": report["warehouse"],
        "summary": report["summary"],
        "transmission": "transferred",
        "tasks": tasks,
        "differences": [t for t in tasks if t["diff"] != 0],
        "monitor": monitor_snapshot(tasks_by_bin),
        "inventory_count": len(ewm_data.INVENTORY),
        "bin_count": sum(len(v) for v in ewm_data.RACK_BINS.values()),
    }


def export(report, run_dir, project_base):
    """페이로드와 UI 상태를 쓴다. 반환: 전송 요약 dict."""
    tasks = [enrich_task(r) for r in report["tasks"]]
    run_dir = Path(run_dir)
    payload_path = run_dir / "ewm_payload.json"
    payload_path.write_text(
        json.dumps(odata_payload(report, tasks), ensure_ascii=False, indent=2),
        encoding="utf-8")

    ui_dir = Path(project_base) / "ewm-ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    state_path = ui_dir / "ewm-state.json"
    state_path.write_text(
        json.dumps(ui_state(report, tasks), ensure_ascii=False, indent=2),
        encoding="utf-8")

    return {
        "backend": BACKEND_LABEL,
        "service": ODATA_SERVICE,
        "posted_items": len(tasks),
        "payload_file": str(payload_path),
        "ui_state_file": str(state_path),
    }
