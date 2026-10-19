"""계수 어댑터 — 목업 계수와 SAM 3.1 실호출의 경계.

인터페이스: count(image_path, task) -> dict
  반환: {"counted_qty": int, "label_sku": str, "label_text": str, "engine": str}

- MockCounting: 웹 데모 simulateCount와 동일 규칙
  (counted = 그 빈의 actual_qty, label = 지시의 SKU).
- SamCounting: SAM 3.1 실연동 지점. 아래 설정 상수와 count() 본문이
  교체 지점이며, 그 경계 밖(플로우·대조·보고)은 손대지 않는다.
"""

import abc
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import data as ewm_data  # noqa: E402


class CountingAdapter(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def count(self, image_path, task):
        raise NotImplementedError


class MockCounting(CountingAdapter):
    """목업 계수 — 웹 데모와 결과가 일치하도록 actual_qty를 그대로 반환."""

    name = "mock"

    def count(self, image_path, task):
        record = ewm_data.find_inventory(task["bin"])
        counted = record["actual_qty"] if record else task["expected_qty"]
        return {
            "counted_qty": counted,
            "label_sku": task["sku"],
            "label_text": "%s · %s" % (task["sku"], task["product_name"]),
            "engine": "mock",
        }


# ── SAM 3.1 실연동 설정 (교체 지점) ─────────────────────────────
# 실연동 시 채울 값:
#   SAM_API_BASE_URL : Meta Model API 엔드포인트 (환경변수로도 지정 가능)
#   SAM_API_KEY_ENV  : API 키가 들어 있는 환경변수 이름 (키는 코드에 넣지 않는다)
#   SAM_MODEL        : 계수에 쓸 모델 식별자
#   COUNT_PROMPT     : 박스 계수용 텍스트 프롬프트
SAM_API_BASE_URL = os.environ.get("SAM_API_BASE_URL", "")
SAM_API_KEY_ENV = "SAM_API_KEY"
SAM_MODEL = "sam-3.1"
COUNT_PROMPT = "cardboard box"


class SamCounting(CountingAdapter):
    """SAM 3.1 실호출 자리.

    실연동 절차:
      1) SAM_API_BASE_URL과 환경변수 SAM_API_KEY를 채운다.
      2) 아래 count()에서 image_path의 JPEG/PNG를 읽어 SAM 3.1에
         COUNT_PROMPT로 세그멘테이션을 요청하고 마스크 개수를 센다.
      3) 라벨 판독(OCR)은 별도 단계로 붙이고 label_sku/label_text를 채운다.
    이 메서드 외의 코드는 실연동 시에도 변경하지 않는다.
    """

    name = "sam"

    def count(self, image_path, task):
        raise NotImplementedError(
            "SAM 3.1 실연동 지점입니다. adapters/counting.py의 SamCounting.count()를 "
            "구현하고 SAM_API_BASE_URL·%s를 설정하세요. 지금은 --counting mock으로 "
            "실행하면 전 플로우를 확인할 수 있습니다." % SAM_API_KEY_ENV
        )


def build_counting_adapter(kind):
    if kind == "mock":
        return MockCounting()
    if kind == "sam":
        return SamCounting()
    raise ValueError("알 수 없는 계수 종류: %s (mock|sam)" % kind)
