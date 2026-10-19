"""회귀 테스트 — 목업 데이터 기준선과 어댑터 계약을 고정한다.

실행: python3 -m unittest discover -s tests -v
기준선: 재고 36건, 지시 6건, 일치 4 · 불일치 2
(부족 A-01-02 장부 8→실측 5, 초과 B-01-02 장부 6→실측 9).
"""

import base64
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import data as ewm_data  # noqa: E402
import flow  # noqa: E402
from adapters import (  # noqa: E402
    MockCounting,
    PiCamera,
    SamCounting,
    SamCountingError,
    SimulatedCamera,
    VoiceAdapter,
    build_camera_adapter,
    detect_camera_command,
)
from adapters import camera as camera_mod  # noqa: E402

ASSETS = BASE / "assets"
TASK = {"bin": "A-01-02", "sku": "SKU-1002",
        "product_name": "스마트폰 충전기 25W", "expected_qty": 8}


class TestDataBaseline(unittest.TestCase):
    def test_inventory_and_orders(self):
        self.assertEqual(len(ewm_data.INVENTORY), 36)
        self.assertEqual(sum(len(v) for v in ewm_data.RACK_BINS.values()), 36)
        orders = ewm_data.work_orders()
        self.assertEqual(len(orders), 6)
        self.assertEqual([o["bin"] for o in orders], ewm_data.TASK_BINS)

    def test_known_mismatches(self):
        shortage = ewm_data.find_inventory("A-01-02")
        self.assertEqual((shortage["expected_qty"], shortage["actual_qty"]), (8, 5))
        overage = ewm_data.find_inventory("B-01-02")
        self.assertEqual((overage["expected_qty"], overage["actual_qty"]), (6, 9))


class TestFlowBaseline(unittest.TestCase):
    def run_sample(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        voice = VoiceAdapter(tmp / "run" / "voice")
        report = flow.run_all(
            SimulatedCamera(ASSETS), MockCounting(), voice, tmp / "run",
            policy="correct", resolver=None, project_base=tmp)
        return tmp, report

    def test_summary_baseline(self):
        _, report = self.run_sample()
        self.assertEqual(report["summary"], {
            "total": 6, "match": 4, "mismatch": 2, "shortage": 1, "overage": 1})
        by_bin = {r["bin"]: r for r in report["tasks"]}
        self.assertEqual(by_bin["A-01-02"]["counted_qty"], 5)
        self.assertEqual(by_bin["A-01-02"]["status"], "shortage")
        self.assertEqual(by_bin["A-01-02"]["diff"], -3)
        self.assertEqual(by_bin["B-01-02"]["counted_qty"], 9)
        self.assertEqual(by_bin["B-01-02"]["status"], "overage")
        self.assertEqual(by_bin["B-01-02"]["diff"], 3)

    def test_outputs_written(self):
        tmp, report = self.run_sample()
        run_dir = tmp / "run"
        result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["summary"]["match"], 4)
        self.assertTrue((run_dir / "ewm_payload.json").exists())
        state = json.loads((tmp / "ewm-ui" / "ewm-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["inventory_count"], 36)
        self.assertEqual(len(state["tasks"]), 6)
        self.assertEqual(state["transmission"], "transferred")
        table = (run_dir / "report.txt").read_text(encoding="utf-8")
        self.assertIn("A-01-02", table)
        self.assertIn("전송 · 확정 완료", table)
        self.assertEqual(report["tasks"][0]["ewm_status"], "전송 · 확정 완료")


class TestCameraAutoDetect(unittest.TestCase):
    def test_auto_falls_back_to_simulated_without_rpicam(self):
        with mock.patch.object(camera_mod.shutil, "which", return_value=None), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RPICAM_CMD", None)
            adapter = build_camera_adapter("auto", ASSETS)
        self.assertIsInstance(adapter, SimulatedCamera)

    def test_auto_selects_pi_when_rpicam_exists(self):
        fake = "/usr/bin/rpicam-still"
        with mock.patch.object(camera_mod.shutil, "which",
                               side_effect=lambda name: fake if name == "rpicam-still" else None), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RPICAM_CMD", None)
            self.assertEqual(detect_camera_command(), fake)
            adapter = build_camera_adapter("auto", ASSETS)
        self.assertIsInstance(adapter, PiCamera)
        self.assertEqual(adapter.command, fake)

    def test_env_override_wins(self):
        with mock.patch.dict(os.environ, {"RPICAM_CMD": "my-cam-cmd"}), \
                mock.patch.object(camera_mod.shutil, "which",
                                  side_effect=lambda name: "/bin/" + name):
            self.assertEqual(detect_camera_command(), "/bin/my-cam-cmd")

    def test_simulated_capture(self):
        shot = SimulatedCamera(ASSETS).capture(TASK, Path(tempfile.mkdtemp()))
        self.assertEqual(shot["source"], "simulated")
        self.assertTrue(Path(shot["image_path"]).exists())


class TestSamCounting(unittest.TestCase):
    IMAGE_BYTES = b"\x89PNG\r\n\x1a\nfake-image-bytes"

    def make_image(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        path = tmp / "rack.png"
        path.write_bytes(self.IMAGE_BYTES)
        return str(path)

    def test_payload_structure(self):
        captured = {}

        def fake_transport(url, payload, headers, timeout):
            captured.update(url=url, payload=payload, headers=headers)
            return 200, json.dumps({"count": 5, "confidence": 0.93}).encode()

        sam = SamCounting(base_url="https://sam.example.test/v1",
                          api_key="test-key", transport=fake_transport)
        result = sam.count(self.make_image(), TASK)
        self.assertEqual(captured["url"], "https://sam.example.test/v1/segment")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")
        payload = captured["payload"]
        self.assertEqual(payload["model"], "sam-3.1")
        self.assertEqual(payload["prompt"], "cardboard box")
        self.assertEqual(payload["image"]["media_type"], "image/png")
        self.assertEqual(base64.b64decode(payload["image"]["data"]), self.IMAGE_BYTES)
        self.assertEqual(payload["task_context"], {"bin": "A-01-02", "sku": "SKU-1002"})
        self.assertEqual(result["counted_qty"], 5)
        self.assertEqual(result["confidence"], 0.93)
        self.assertEqual(result["engine"], "sam")
        self.assertEqual(result["label_sku"], "SKU-1002")

    def test_parse_objects_and_masks_forms(self):
        body = json.dumps({"objects": [{"score": 0.8}, {"score": 1.0}, {}]}).encode()
        counted, confidence = SamCounting.parse_response(body)
        self.assertEqual(counted, 3)
        self.assertAlmostEqual(confidence, 0.9)
        counted, confidence = SamCounting.parse_response(
            json.dumps({"masks": [{}, {}]}).encode())
        self.assertEqual(counted, 2)
        self.assertIsNone(confidence)

    def test_missing_config_raises_not_fallback(self):
        sam = SamCounting(base_url="", api_key="k", transport=lambda *a: (200, b"{}"))
        with self.assertRaises(SamCountingError):
            sam.count(self.make_image(), TASK)
        sam = SamCounting(base_url="https://x.test", api_key="", transport=lambda *a: (200, b"{}"))
        with self.assertRaises(SamCountingError):
            sam.count(self.make_image(), TASK)

    def test_http_error_raises(self):
        sam = SamCounting(base_url="https://x.test", api_key="k",
                          transport=lambda *a: (500, b"server error"))
        with self.assertRaises(SamCountingError):
            sam.count(self.make_image(), TASK)

    def test_bad_response_raises(self):
        sam = SamCounting(base_url="https://x.test", api_key="k",
                          transport=lambda *a: (200, b"not json"))
        with self.assertRaises(SamCountingError):
            sam.count(self.make_image(), TASK)
        sam = SamCounting(base_url="https://x.test", api_key="k",
                          transport=lambda *a: (200, b"{}"))
        with self.assertRaises(SamCountingError):
            sam.count(self.make_image(), TASK)

    def test_transport_exception_raises(self):
        def boom(*a):
            raise ConnectionError("offline")

        sam = SamCounting(base_url="https://x.test", api_key="k", transport=boom)
        with self.assertRaises(SamCountingError):
            sam.count(self.make_image(), TASK)


class TestReportTable(unittest.TestCase):
    def test_table_renders_rows_and_totals(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        voice = VoiceAdapter(tmp / "run" / "voice")
        report = flow.run_all(
            SimulatedCamera(ASSETS), MockCounting(), voice, tmp / "run",
            project_base=tmp)
        table = flow.render_report_table(report)
        self.assertIn("지시", table)
        self.assertIn("WO-002", table)
        self.assertIn("-3", table)
        self.assertIn("+3", table)
        self.assertIn("부족", table)
        self.assertIn("초과", table)
        self.assertIn("총 6건 · 일치 4 · 불일치 2", table)
        self.assertIn("EWM 전송", table)


if __name__ == "__main__":
    unittest.main()
