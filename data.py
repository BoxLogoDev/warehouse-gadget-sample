"""목업 EWM 데이터 — SAP EWM 용어·코드 체계를 반영한 샘플.

핵심 시나리오는 웹 데모(src/data.js)와 동일하게 유지한다:
  재고 실사 지시 6건, 일치 4, 부족 1(A-01-02: 장부 8 → 실제 5),
  초과 1(B-01-02: 장부 6 → 실제 9).
그 위에 EWM식 필드를 얹었다: 창고번호(1000), 저장유형 코드, 저장빈 좌표,
품목번호, HU(Handling Unit) 번호, 창고 작업(WT) 번호, 실사 문서 번호,
차이 사유 코드. 전부 목업 값이며 실제 SAP 시스템의 데이터가 아니다.

수량은 박스 단위. expected_qty는 EWM 장부 수량, actual_qty는 현장 실제 수량.
웹 데모의 simulateCount 규칙: 계수 결과 = actual_qty, 라벨 = 지시의 SKU.
"""

WAREHOUSE = {
    "id": "WH-1000",
    "warehouse_no": "1000",  # EWM 창고번호
    "name": "인천 물류센터 (WH-1000)",
    "zones": [
        {"id": "A", "name": "A구역", "racks": ["A-01", "A-02", "A-03", "A-04"]},
        {"id": "B", "name": "B구역", "racks": ["B-01", "B-02", "B-03"]},
        {"id": "C", "name": "C구역", "racks": ["C-01", "C-02"]},
    ],
}

# EWM 저장유형 (Storage Type) — 구역별 성격
STORAGE_TYPES = {
    "0010": "팔레트 랙",
    "0020": "선반 랙",
    "0030": "벌크 보관",
}
ZONE_STORAGE_TYPE = {"A": "0020", "B": "0010", "C": "0030"}

# 랙별 빈 구성 (랙마다 빈 4개, 총 36빈)
RACK_BINS = {
    "A-01": ["A-01-01", "A-01-02", "A-01-03", "A-01-04"],
    "A-02": ["A-02-01", "A-02-02", "A-02-03", "A-02-04"],
    "A-03": ["A-03-01", "A-03-02", "A-03-03", "A-03-04"],
    "A-04": ["A-04-01", "A-04-02", "A-04-03", "A-04-04"],
    "B-01": ["B-01-01", "B-01-02", "B-01-03", "B-01-04"],
    "B-02": ["B-02-01", "B-02-02", "B-02-03", "B-02-04"],
    "B-03": ["B-03-01", "B-03-02", "B-03-03", "B-03-04"],
    "C-01": ["C-01-01", "C-01-02", "C-01-03", "C-01-04"],
    "C-02": ["C-02-01", "C-02-02", "C-02-03", "C-02-04"],
}

# 실사 문서(Physical Inventory Document) 번호 — 이번 실사 회차 전체가 한 문서
PI_DOCUMENT_NO = "2026000001"


def _hu(seq):
    """EWM HU 번호 형식(20자리 숫자)의 목업 값."""
    return "1122334455%010d" % seq


def _rec(bin_id, sku, product_name, expected, actual, seq):
    return {
        "bin": bin_id,
        "sku": sku,
        "product_no": "1000" + sku.split("-")[1],  # EWM 품목번호(목업)
        "product_name": product_name,
        "expected_qty": expected,
        "actual_qty": actual,
        "storage_type": ZONE_STORAGE_TYPE[bin_id.split("-")[0]],
        "hu": _hu(seq),
        "uom": "EA",
    }


# 재고 36건 (기존 20건 값은 웹 데모와 동일, 신규 16건은 전부 일치 건)
INVENTORY = [
    _rec("A-01-01", "SKU-1001", "무선 이어폰 케이스", 12, 12, 1),
    _rec("A-01-02", "SKU-1002", "스마트폰 충전기 25W", 8, 5, 2),
    _rec("A-01-03", "SKU-1003", "USB-C 케이블 1m", 20, 20, 3),
    _rec("A-01-04", "SKU-1004", "노트북 거치대", 6, 6, 4),
    _rec("A-02-01", "SKU-2001", "블루투스 키보드", 10, 10, 5),
    _rec("A-02-02", "SKU-2002", "무선 마우스", 15, 15, 6),
    _rec("A-02-03", "SKU-2003", "모니터 암", 4, 4, 7),
    _rec("A-02-04", "SKU-2004", "웹캠 FHD", 9, 9, 8),
    _rec("A-03-01", "SKU-3001", "보조배터리 10000mAh", 18, 18, 9),
    _rec("A-03-02", "SKU-3002", "스마트워치 밴드", 14, 14, 10),
    _rec("A-03-03", "SKU-3003", "태블릿 파우치", 7, 7, 11),
    _rec("A-03-04", "SKU-3004", "HDMI 케이블 2m", 11, 11, 12),
    _rec("A-04-01", "SKU-6001", "무선 도어벨", 7, 7, 13),
    _rec("A-04-02", "SKU-6002", "LED 스트립 조명", 12, 12, 14),
    _rec("A-04-03", "SKU-6003", "스마트 플러그", 9, 9, 15),
    _rec("A-04-04", "SKU-6004", "온습도 센서", 15, 15, 16),
    _rec("B-01-01", "SKU-4001", "기계식 키보드 스위치", 16, 16, 17),
    _rec("B-01-02", "SKU-4002", "SSD 외장 케이스", 6, 9, 18),
    _rec("B-01-03", "SKU-4003", "랜 케이블 CAT6", 22, 22, 19),
    _rec("B-01-04", "SKU-4004", "멀티탭 4구", 13, 13, 20),
    _rec("B-02-01", "SKU-5001", "노트북 파우치 14인치", 5, 5, 21),
    _rec("B-02-02", "SKU-5002", "무선 충전 패드", 10, 10, 22),
    _rec("B-02-03", "SKU-5003", "이어폰 팁 세트", 24, 24, 23),
    _rec("B-02-04", "SKU-5004", "휴대용 선풍기", 8, 8, 24),
    _rec("B-03-01", "SKU-7001", "게이밍 마우스 패드", 18, 18, 25),
    _rec("B-03-02", "SKU-7002", "USB 허브 7포트", 8, 8, 26),
    _rec("B-03-03", "SKU-7003", "노트북 쿨링 패드", 5, 5, 27),
    _rec("B-03-04", "SKU-7004", "카드 리더기", 11, 11, 28),
    _rec("C-01-01", "SKU-8001", "PC 케이스 미들타워", 4, 4, 29),
    _rec("C-01-02", "SKU-8002", "게이밍 모니터 27인치", 3, 3, 30),
    _rec("C-01-03", "SKU-8003", "사무용 의자", 6, 6, 31),
    _rec("C-01-04", "SKU-8004", "전동 스탠딩 데스크 프레임", 2, 2, 32),
    _rec("C-02-01", "SKU-9001", "프린터 토너 카트리지", 10, 10, 33),
    _rec("C-02-02", "SKU-9002", "A4 복사용지 박스", 25, 25, 34),
    _rec("C-02-03", "SKU-9003", "라벨 프린터", 4, 4, 35),
    _rec("C-02-04", "SKU-9004", "서지 보호 멀티탭 8구", 13, 13, 36),
]

# 실사 지시 6건: 일치 4, 부족 1(A-01-02: 8→5), 초과 1(B-01-02: 6→9) — 웹 데모와 동일
TASK_BINS = ["A-01-01", "A-01-02", "A-02-02", "A-03-01", "B-01-02", "B-02-02"]

# EWM 차이 사유 코드 (목업)
REASON_CODES = {
    "DF01": "수량 차이 — 파손/분리 보관",
    "DF02": "수량 차이 — 오적재(인접 빈 이동)",
    "DF03": "수량 차이 — 분실",
    "DF04": "수량 차이 — 입고 오류",
}


def reason_for(status, note=""):
    """실사 상태와 메모로 차이 사유 코드를 정한다. 일치 건은 빈 문자열."""
    if status == "shortage":
        return "DF01" if "파손" in (note or "") else "DF03"
    if status == "overage":
        return "DF02"
    return ""


def find_inventory(bin_id):
    for record in INVENTORY:
        if record["bin"] == bin_id:
            return record
    return None


def rack_of_bin(bin_id):
    return "-".join(bin_id.split("-")[:2])


def zone_of_bin(bin_id):
    return bin_id.split("-")[0]


def storage_type_name(code):
    return STORAGE_TYPES.get(code, "")


def work_orders():
    orders = []
    for index, bin_id in enumerate(TASK_BINS):
        record = find_inventory(bin_id)
        orders.append(
            {
                "id": "WO-%03d" % (index + 1),
                "wt_no": "10000001%02d" % (index + 1),  # EWM 창고 작업(WT) 번호(목업)
                "pi_doc": PI_DOCUMENT_NO,
                "bin": record["bin"],
                "sku": record["sku"],
                "product_no": record["product_no"],
                "product_name": record["product_name"],
                "expected_qty": record["expected_qty"],
                "storage_type": record["storage_type"],
                "hu": record["hu"],
            }
        )
    return orders
