"""촬영 어댑터 — 같은 인터페이스에 시뮬레이터와 라즈베리파이 카메라 두 구현.

인터페이스: capture(task, out_dir) -> dict
  반환: {"image_path": str, "source": str, "bin": str, "captured_at": iso8601}

실기기 교체 지점:
- Pi: PiCamera (rpicam-still 호출). 환경변수 RPICAM_CMD로 명령 교체 가능.
- SenseCAP Watcher: camera.capture(JPEG base64 반환)를 받는 구현을
  이 인터페이스로 추가하면 된다 (구성안 4절 어댑터 표 참조).
"""

import abc
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


class CameraAdapter(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def capture(self, task, out_dir):
        """task의 빈을 촬영해 이미지 경로와 메타데이터를 반환한다."""
        raise NotImplementedError


class SimulatedCamera(CameraAdapter):
    """하드웨어 없는 시뮬레이터: assets/의 샘플 랙 이미지를 반환한다.

    파일 규칙: assets/rack-<bin>.png (예: rack-A-01-02.png), 없으면
    assets/default-rack.png를 반환한다.
    """

    name = "simulated"

    def __init__(self, assets_dir):
        self.assets_dir = Path(assets_dir)

    def capture(self, task, out_dir):
        bin_id = task["bin"]
        candidate = self.assets_dir / ("rack-%s.png" % bin_id)
        if not candidate.exists():
            candidate = self.assets_dir / "default-rack.png"
        if not candidate.exists():
            raise FileNotFoundError(
                "샘플 이미지가 없습니다: %s (tools/make_sample_images.py를 먼저 실행하세요)"
                % candidate
            )
        return {
            "image_path": str(candidate),
            "source": "simulated",
            "bin": bin_id,
            "captured_at": datetime.now().isoformat(timespec="seconds"),
        }


class PiCamera(CameraAdapter):
    """라즈베리파이 카메라: rpicam-still(구 libcamera-still) 명령 호출."""

    name = "pi"

    def __init__(self, command=None, width=1920, height=1440):
        # 환경변수 RPICAM_CMD가 있으면 그 명령을 우선한다.
        self.command = command or os.environ.get("RPICAM_CMD", "rpicam-still")
        self.width = width
        self.height = height

    def capture(self, task, out_dir):
        if shutil.which(self.command) is None:
            raise RuntimeError(
                "카메라 명령 '%s'을(를) 찾을 수 없습니다. 라즈베리파이에서 "
                "rpicam-apps가 설치돼 있는지 확인하세요. (시뮬레이터로 돌리려면 "
                "--camera sim)" % self.command
            )
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%H%M%S")
        target = out_dir / ("capture-%s-%s.jpg" % (task["bin"], stamp))
        cmd = [
            self.command,
            "-o", str(target),
            "--width", str(self.width),
            "--height", str(self.height),
            "-t", "800",  # 프리뷰·노출 안정화 대기(ms)
            "-n",
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return {
            "image_path": str(target),
            "source": "pi-camera",
            "bin": task["bin"],
            "captured_at": datetime.now().isoformat(timespec="seconds"),
        }


def build_camera_adapter(kind, assets_dir, out_dir=None):
    if kind == "sim":
        return SimulatedCamera(assets_dir)
    if kind == "pi":
        return PiCamera()
    raise ValueError("알 수 없는 카메라 종류: %s (sim|pi)" % kind)
