# 창고 재고 실사 — Muse Gadgets 단말 샘플

Meta Global AI Developer Hackathon 출품작 「SAP EWM × 창고 재고 실사 앱」의
단말 쪽 샘플 구현. 하드웨어 없이 PC에서 실사 플로우 전체가 끝까지 돌고,
촬영·계수·음성은 어댑터 경계 뒤에 있어 실기기 도착 시 그 지점만 교체한다.

구성 근거: `~/workspace/goals/meta-global-ai-developer-hackathon/files/가젯-방향-검토-2026-10-19.md`
(실행 구성안 4절의 어댑터 연결 방안, 6절 준비 작업). 데이터·판정 규칙은
구현済 웹 데모(`~/workspace/projects/meta-hackathon-warehouse/`)와 동일하다.

## 가젯 없이 바로 실행 (회사 PC에서 써보기)

```bash
./run.sh                          # 지시 6건 전체 실행, 산출물은 out/run-<시각>/
./run.sh --on-mismatch ask        # 불일치 건마다 정정/확정 선택 + 메모 직접 입력
python3 warehouse_gadget.py report   # 마지막 실행의 완료 보고
python3 warehouse_gadget.py status   # 마지막 실행 요약 (JSON)
```

실행하면 건마다 지시 수신 → 위치 안내 → 촬영 → 계수 → EWM 대조 →
(불일치 시) 음성 안내·메모·정정 → 완료 보고 순서로 진행되고,
실행 폴더에 `result.json`(실사 결과), `run.log`(실행 로그),
`voice/`(안내 문구 .txt와 음성 .wav)가 남는다.

데이터: 인천 물류센터(WH-1000), 구역 2·랙 5·재고 20건, 실사 지시 6건.
웹 데모와 같게 4건 일치, 1건 부족(A-01-02: 장부 8 → 실제 5),
1건 초과(B-01-02: 장부 6 → 실제 9)로 나온다.

## 구조

```
warehouse_gadget.py   진입점 CLI (run / capture / status / report)
warehouse-gadget      SDK system.run용 래퍼 (같은 CLI를 이름으로 호출)
run.sh                PC 단독 실행 스크립트
data.py               목업 EWM 데이터 (웹 데모 src/data.js와 동일 값)
flow.py               실사 플로우 본체 (어댑터만 호출, 하드웨어 무지)
adapters/camera.py    촬영: SimulatedCamera(샘플 이미지) / PiCamera(rpicam-still)
adapters/counting.py  계수: MockCounting(웹 데모 규칙) / SamCounting(실연동 지점)
adapters/voice.py     음성: 안내 문구 → .wav+.txt (TTS 실연동 지점은 synthesize())
assets/               시뮬레이터 촬영 샘플 이미지 (tools/make_sample_images.py 생성)
out/                  실행 산출물
```

## 불일치 처리 옵션

- `--on-mismatch correct` (기본): 계수 수량으로 정정 확정
- `--on-mismatch accept`: 장부 수량 그대로 확정
- `--on-mismatch ask`: 건마다 터미널에서 선택하고 메모를 입력
- `--note "문구"`: 불일치 건 공통 메모 / `--demo-notes`: 샘플 메모 자동 부착

## Muse Gadgets 연결 지점

Linux Device SDK를 단말(라즈베리파이)에 설치하면 Muse 가 `system.run`으로
셸 명령을 실행할 수 있다. 이 샘플의 서브커맨드가 그 호출 대상이다.

```bash
# 촬영 1건 (결과는 stdout JSON 한 줄)
warehouse-gadget capture --bin A-01-02 --camera pi
# 상태 확인 / 완료 보고
warehouse-gadget status
warehouse-gadget report
```

전체 실사를 Muse 쪽에서 돌릴 때는 `warehouse-gadget run --camera pi`를
system.run으로 실행하고, 산출된 `out/run-*/result.json`을 `file.read`로
회수하면 된다 (64KB 청크 전송은 SDK 쪽 규칙).

## 라즈베리파이 배포 절차

1. (토큰 발급 후) gadgets.muse.ai에서 SDK 토큰을 발급한다. ← **이 단계만 토큰 필요**
2. (토큰 발급 후) 단말에 Linux Device SDK를 설치한다 (`install.sh`, systemd 서비스로 상주).
   토큰은 단말의 `/var/lib/musegadget`에 root 전용으로 저장되며, 이 레포에 넣지 않는다.
3. 이 폴더를 단말에 복사한다. Python 3 표준 라이브러리만 쓰므로 추가 설치가 없다.
4. 카메라를 확인한다: `rpicam-still -o /tmp/test.jpg`로 촬영이 되는지 본다.
   명령 이름이 다르면 환경변수 `RPICAM_CMD`로 바꾼다.
5. 단말 단독으로 먼저 돌린다: `python3 warehouse_gadget.py run --camera pi`
   촬영만 실카메라로 바뀌고 계수는 아직 목업이다.
6. Muse 앱(Settings > Devices, 개발자 모드)에서 단말을 페어링한 뒤,
   `warehouse-gadget` 래퍼를 PATH에 올리면 위 system.run 호출이 성립한다.

토큰이 없어도 3~5번(단말 단독 실행)까지는 진행을 막지 않는다.

## 하드웨어 도착 시 바꿀 지점

| 지점 | 지금 (샘플) | 실기기 |
|---|---|---|
| 촬영 | SimulatedCamera — `assets/` 샘플 이미지 반환 | `run --camera pi` (PiCamera, rpicam-still). Watcher로 가면 `camera.capture` 수신 구현을 `adapters/camera.py`에 같은 인터페이스로 추가 |
| 계수 | MockCounting — 웹 데모와 같은 목업 규칙 | `adapters/counting.py`의 `SamCounting.count()` 본문 구현 + `SAM_API_BASE_URL`·환경변수 `SAM_API_KEY` 설정. 경계 밖 코드는 무변경 |
| 음성 안내 | 문구 .txt + 무음 .wav 생성 | 환경변수 `WAREHOUSE_TTS_CMD`에 TTS 명령 지정(예: piper). Watcher에서는 결과 텍스트를 기기로 보내 `start_tts` 지점에서 재생 |
| 음성 메모 | 텍스트 입력(stdin/인자) | push-to-talk 전사 텍스트를 `VoiceAdapter.read_note(provided=...)`로 주입 |
| EWM | 목업 데이터(`data.py`), 전송은 시뮬레이션 표기 | 실제 EWM 연동은 설계상 OData 경로 제시만 — 이 샘플 범위 밖 |

## 샘플 이미지 다시 만들기

```bash
python3 tools/make_sample_images.py   # assets/rack-<bin>.png 6장 + default-rack.png
```

선반별 박스 수가 실제 재고 수량과 같게 그려지므로, 계수를 실사진 파이프라인으로
바꾼 뒤에도 같은 이미지로 판정 로직을 검증할 수 있다.
