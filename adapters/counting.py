"""계수 어댑터 — 목업 계수와 SAM 3.1 실호출의 경계.

인터페이스: count(image_path, task) -> dict
  반환: {"counted_qty": int, "label_sku": str, "label_text": str, "engine": str}

- MockCounting: 웹 데모 simulateCount와 동일 규칙
  (counted = 그 빈의 actual_qty, label = 지시의 SKU).
- SamCounting: SAM 3.1 실호출 구현. 요청 페이로드 구성(build_payload)과
  응답 파싱(parse_response)이 코드로 완성돼 있고, 실제 네트워크 호출은
  transport 함수 하나로 격리돼 있다. 설정(URL·키)이 없거나 호출·파싱이
  실패하면 Mock으로 떨어지지 않고 SamCountingError로 명시 보고한다.
  그 경계 밖(플로우·대조·보고)은 손대지 않는다.
"""

import abc
import base64
import json
import os
import sys
import urllib.error
import urllib.request
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


# ── SAM 3.1 실연동 설정 ─────────────────────────────────────────
# 실연동 시 채울 값:
#   SAM_API_BASE_URL : Meta Model API 엔드포인트 (환경변수로도 지정 가능)
#   SAM_API_KEY_ENV  : API 키가 들어 있는 환경변수 이름 (키는 코드에 넣지 않는다)
#   SAM_MODEL        : 계수에 쓸 모델 식별자
#   COUNT_PROMPT     : 박스 계수용 텍스트 프롬프트
# 페이로드·응답 스키마는 이 샘플이 정한 계약이다. 실제 Meta Model API의
# SAM 3.1 엔드포인트 규격이 공개되면 build_payload/parse_response의
# 필드 매핑만 그 규격에 맞추면 되고, 호출·오류 처리 흐름은 그대로 쓴다.
SAM_API_BASE_URL = os.environ.get("SAM_API_BASE_URL", "")
SAM_API_KEY_ENV = "SAM_API_KEY"
SAM_MODEL = "sam-3.1"
COUNT_PROMPT = "cardboard box"
SAM_TIMEOUT_SEC = 30

_MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


class SamCountingError(RuntimeError):
    """SAM 계수 실패 — 설정 누락·호출 실패·응답 파싱 실패를 한데 모은다."""


def _urllib_transport(url, payload, headers, timeout):
    """기본 전송: JSON POST. 반환 (HTTP 상태, 응답 본문 bytes)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


class SamCounting(CountingAdapter):
    """SAM 3.1 실호출 계수.

    동작:
      1) build_payload: 촬영 이미지를 base64로 실은 JSON 페이로드를 만든다.
      2) transport로 POST한다 (기본 urllib, 테스트에서는 함수 주입 가능).
      3) parse_response: 응답에서 개수(count/objects/masks)와 신뢰도를 뽑는다.
    어느 단계든 실패하면 SamCountingError를 던진다 — 목업으로 조용히
    대체하지 않는다. 라벨(SKU) 판독은 SAM 범위 밖이라 지시의 SKU를
    그대로 쓰고, 실연동 시 OCR 단계를 별도로 붙인다.
    """

    name = "sam"

    def __init__(self, base_url=None, api_key=None, model=SAM_MODEL,
                 prompt=COUNT_PROMPT, transport=None, timeout=SAM_TIMEOUT_SEC):
        self.base_url = base_url if base_url is not None else SAM_API_BASE_URL
        self.api_key = api_key if api_key is not None else os.environ.get(SAM_API_KEY_ENV, "")
        self.model = model
        self.prompt = prompt
        self.transport = transport or _urllib_transport
        self.timeout = timeout

    def endpoint(self):
        return self.base_url.rstrip("/") + "/segment"

    def build_payload(self, image_path, task):
        path = Path(image_path)
        if not path.exists():
            raise SamCountingError("계수할 이미지가 없습니다: %s" % path)
        media_type = _MEDIA_TYPES.get(path.suffix.lower())
        if media_type is None:
            raise SamCountingError(
                "지원하지 않는 이미지 형식입니다: %s (jpg/png만 가능)" % path.suffix)
        return {
            "model": self.model,
            "image": {
                "media_type": media_type,
                "data": base64.b64encode(path.read_bytes()).decode("ascii"),
            },
            "prompt": self.prompt,
            "task_context": {"bin": task["bin"], "sku": task["sku"]},
        }

    @staticmethod
    def parse_response(body):
        """응답 본문에서 (개수, 신뢰도)를 뽑는다.

        허용 형태: {"count": n, "confidence": f} /
        {"objects": [...], "confidence": f} / {"masks": [...]}.
        신뢰도가 항목별로 오면 평균을 쓴다. 해석할 수 없으면 오류.
        """
        try:
            data = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise SamCountingError("SAM 응답을 JSON으로 해석할 수 없습니다: %s" % exc)
        if not isinstance(data, dict):
            raise SamCountingError("SAM 응답 형식이 객체가 아닙니다: %r" % (data,))
        items = None
        if isinstance(data.get("count"), int):
            counted = data["count"]
        elif isinstance(data.get("objects"), list):
            items = data["objects"]
            counted = len(items)
        elif isinstance(data.get("masks"), list):
            items = data["masks"]
            counted = len(items)
        else:
            raise SamCountingError(
                "SAM 응답에서 개수를 찾을 수 없습니다 (count/objects/masks 없음): %s"
                % json.dumps(data, ensure_ascii=False)[:200])
        confidence = data.get("confidence")
        if confidence is None and items:
            scores = [it.get("score", it.get("confidence")) for it in items
                      if isinstance(it, dict)]
            scores = [s for s in scores if isinstance(s, (int, float))]
            confidence = sum(scores) / len(scores) if scores else None
        return counted, confidence

    def count(self, image_path, task):
        if not self.base_url:
            raise SamCountingError(
                "SAM_API_BASE_URL이 설정되지 않았습니다. 엔드포인트를 지정하거나 "
                "--counting mock으로 실행하세요.")
        if not self.api_key:
            raise SamCountingError(
                "API 키 환경변수 %s가 비어 있습니다. 키를 설정하거나 "
                "--counting mock으로 실행하세요." % SAM_API_KEY_ENV)
        payload = self.build_payload(image_path, task)
        headers = {"Authorization": "Bearer " + self.api_key}
        try:
            status, body = self.transport(
                self.endpoint(), payload, headers, self.timeout)
        except SamCountingError:
            raise
        except Exception as exc:  # 네트워크 오류 등 전송 단계 실패
            raise SamCountingError("SAM 호출이 실패했습니다: %s" % exc)
        if status != 200:
            snippet = body.decode("utf-8", "replace")[:200] if isinstance(body, bytes) else str(body)[:200]
            raise SamCountingError("SAM 호출이 HTTP %d를 반환했습니다: %s" % (status, snippet))
        counted, confidence = self.parse_response(body)
        return {
            "counted_qty": counted,
            "confidence": confidence,
            "label_sku": task["sku"],
            "label_text": "%s · %s" % (task["sku"], task["product_name"]),
            "engine": "sam",
        }


def build_counting_adapter(kind):
    if kind == "mock":
        return MockCounting()
    if kind == "sam":
        return SamCounting()
    raise ValueError("알 수 없는 계수 종류: %s (mock|sam)" % kind)
