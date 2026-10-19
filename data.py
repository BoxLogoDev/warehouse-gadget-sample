"""목업 EWM 데이터 — 웹 데모(src/data.js)와 동일한 값.

수량은 박스 단위. expected_qty는 EWM 장부 수량, actual_qty는 현장 실제 수량.
웹 데모의 simulateCount 규칙: 계수 결과 = actual_qty, 라벨 = 지시의 SKU.
"""

WAREHOUSE = {
    "id": "WH-1000",
    "name": "인천 물류센터 (WH-1000)",
    "zones": [
        {"id": "A", "name": "A구역", "racks": ["A-01", "A-02", "A-03"]},
        {"id": "B", "name": "B구역", "racks": ["B-01", "B-02"]},
    ],
}

# 랙별 빈 구성 (웹 데모 warehouse 구조와 동일: 랙마다 빈 4개)
RACK_BINS = {
    "A-01": ["A-01-01", "A-01-02", "A-01-03", "A-01-04"],
    "A-02": ["A-02-01", "A-02-02", "A-02-03", "A-02-04"],
    "A-03": ["A-03-01", "A-03-02", "A-03-03", "A-03-04"],
    "B-01": ["B-01-01", "B-01-02", "B-01-03", "B-01-04"],
    "B-02": ["B-02-01", "B-02-02", "B-02-03", "B-02-04"],
}

# 재고 20건 (웹 데모 inventory와 동일)
INVENTORY = [
    {"bin": "A-01-01", "sku": "SKU-1001", "product_name": "무선 이어폰 케이스", "expected_qty": 12, "actual_qty": 12},
    {"bin": "A-01-02", "sku": "SKU-1002", "product_name": "스마트폰 충전기 25W", "expected_qty": 8, "actual_qty": 5},
    {"bin": "A-01-03", "sku": "SKU-1003", "product_name": "USB-C 케이블 1m", "expected_qty": 20, "actual_qty": 20},
    {"bin": "A-01-04", "sku": "SKU-1004", "product_name": "노트북 거치대", "expected_qty": 6, "actual_qty": 6},
    {"bin": "A-02-01", "sku": "SKU-2001", "product_name": "블루투스 키보드", "expected_qty": 10, "actual_qty": 10},
    {"bin": "A-02-02", "sku": "SKU-2002", "product_name": "무선 마우스", "expected_qty": 15, "actual_qty": 15},
    {"bin": "A-02-03", "sku": "SKU-2003", "product_name": "모니터 암", "expected_qty": 4, "actual_qty": 4},
    {"bin": "A-02-04", "sku": "SKU-2004", "product_name": "웹캠 FHD", "expected_qty": 9, "actual_qty": 9},
    {"bin": "A-03-01", "sku": "SKU-3001", "product_name": "보조배터리 10000mAh", "expected_qty": 18, "actual_qty": 18},
    {"bin": "A-03-02", "sku": "SKU-3002", "product_name": "스마트워치 밴드", "expected_qty": 14, "actual_qty": 14},
    {"bin": "A-03-03", "sku": "SKU-3003", "product_name": "태블릿 파우치", "expected_qty": 7, "actual_qty": 7},
    {"bin": "A-03-04", "sku": "SKU-3004", "product_name": "HDMI 케이블 2m", "expected_qty": 11, "actual_qty": 11},
    {"bin": "B-01-01", "sku": "SKU-4001", "product_name": "기계식 키보드 스위치", "expected_qty": 16, "actual_qty": 16},
    {"bin": "B-01-02", "sku": "SKU-4002", "product_name": "SSD 외장 케이스", "expected_qty": 6, "actual_qty": 9},
    {"bin": "B-01-03", "sku": "SKU-4003", "product_name": "랜 케이블 CAT6", "expected_qty": 22, "actual_qty": 22},
    {"bin": "B-01-04", "sku": "SKU-4004", "product_name": "멀티탭 4구", "expected_qty": 13, "actual_qty": 13},
    {"bin": "B-02-01", "sku": "SKU-5001", "product_name": "노트북 파우치 14인치", "expected_qty": 5, "actual_qty": 5},
    {"bin": "B-02-02", "sku": "SKU-5002", "product_name": "무선 충전 패드", "expected_qty": 10, "actual_qty": 10},
    {"bin": "B-02-03", "sku": "SKU-5003", "product_name": "이어폰 팁 세트", "expected_qty": 24, "actual_qty": 24},
    {"bin": "B-02-04", "sku": "SKU-5004", "product_name": "휴대용 선풍기", "expected_qty": 8, "actual_qty": 8},
]

# 실사 지시 6건: 일치 4, 부족 1(A-01-02: 8→5), 초과 1(B-01-02: 6→9) — 웹 데모와 동일
TASK_BINS = ["A-01-01", "A-01-02", "A-02-02", "A-03-01", "B-01-02", "B-02-02"]


def find_inventory(bin_id):
    for record in INVENTORY:
        if record["bin"] == bin_id:
            return record
    return None


def rack_of_bin(bin_id):
    return "-".join(bin_id.split("-")[:2])


def zone_of_bin(bin_id):
    return bin_id.split("-")[0]


def work_orders():
    orders = []
    for index, bin_id in enumerate(TASK_BINS):
        record = find_inventory(bin_id)
        orders.append(
            {
                "id": "WO-%03d" % (index + 1),
                "bin": record["bin"],
                "sku": record["sku"],
                "product_name": record["product_name"],
                "expected_qty": record["expected_qty"],
            }
        )
    return orders
