"""실사 플로우 어댑터 패키지.

하드웨어·외부 서비스와의 경계는 전부 이 패키지 안에 둔다.
플로우 본체(flow.py)는 어댑터 인터페이스만 호출하므로,
실기기 도착 시 이 패키지의 구현 교체만으로 전환된다.
"""

from .camera import (
    CameraAdapter,
    PiCamera,
    SimulatedCamera,
    build_camera_adapter,
    detect_camera_command,
)
from .counting import (
    CountingAdapter,
    MockCounting,
    SamCounting,
    SamCountingError,
    build_counting_adapter,
)
from .voice import VoiceAdapter

__all__ = [
    "CameraAdapter",
    "SimulatedCamera",
    "PiCamera",
    "build_camera_adapter",
    "detect_camera_command",
    "CountingAdapter",
    "MockCounting",
    "SamCounting",
    "SamCountingError",
    "build_counting_adapter",
    "VoiceAdapter",
]
