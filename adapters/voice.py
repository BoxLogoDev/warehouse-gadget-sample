"""음성 어댑터 — 안내 문구 음성화 지점과 메모 입력 대체 경로.

- announce(text, slug): 안내 문구를 음성 파일로 남긴다.
  실 TTS 엔진이 연결되지 않은 환경에서는 문구 텍스트(.txt)와
  무음 WAV(.wav)를 생성해 플로우가 끊기지 않게 한다.
  실연동 지점은 synthesize() 하나다: 환경변수 WAREHOUSE_TTS_CMD에
  TTS 명령(예: "piper --model ko.onnx --output_file {out}")을 지정하면
  그 명령으로 실제 음성을 만든다. Watcher에서는 결과 텍스트를 기기로
  보내 start_tts 지점에서 재생하는 방식으로 교체한다(구성안 4절).
- read_note(): 음성 메모 입력의 대체 경로. 실기기에서는 push-to-talk
  전사 텍스트가 들어올 자리이며, 지금은 텍스트(인자 또는 stdin)로 받는다.
"""

import os
import subprocess
import wave
from pathlib import Path

SAMPLE_RATE = 16000  # Hz, 16bit mono


def _silent_wav(path, text):
    """문구 길이에 비례한 무음 WAV를 만든다 (실 TTS 없을 때의 자리표시자)."""
    seconds = max(0.8, min(6.0, len(text) * 0.09))
    frames = int(SAMPLE_RATE * seconds)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"\x00\x00" * frames)
    return seconds


def synthesize(text, wav_path):
    """TTS 실연동 지점. 반환: (방식, 길이초)

    WAREHOUSE_TTS_CMD가 있으면 그 명령을 실행해 실제 음성을 만들고,
    없으면 무음 WAV를 만든다. 명령 문자열의 {out}이 출력 경로로 치환된다.
    """
    cmd_template = os.environ.get("WAREHOUSE_TTS_CMD", "")
    if cmd_template:
        cmd = cmd_template.replace("{out}", str(wav_path))
        subprocess.run(cmd, shell=True, check=True, input=text.encode("utf-8"))
        with wave.open(str(wav_path), "rb") as wav:
            return "tts-cmd", wav.getnframes() / float(wav.getframerate())
    return "silent", _silent_wav(wav_path, text)


class VoiceAdapter:
    name = "file-tts"

    def __init__(self, voice_dir):
        self.voice_dir = Path(voice_dir)
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        self._seq = 0

    def announce(self, text, slug):
        """안내 문구를 음성 파일+텍스트 파일로 남기고 경로를 반환한다."""
        self._seq += 1
        base = "%02d-%s" % (self._seq, slug)
        wav_path = self.voice_dir / (base + ".wav")
        txt_path = self.voice_dir / (base + ".txt")
        txt_path.write_text(text, encoding="utf-8")
        mode, seconds = synthesize(text, wav_path)
        return {
            "text": text,
            "wav_path": str(wav_path),
            "txt_path": str(txt_path),
            "tts_mode": mode,
            "duration_sec": round(seconds, 2),
        }

    def read_note(self, provided=None, prompt="음성 메모(텍스트 입력): "):
        """메모 입력 대체 경로. provided가 있으면 그대로, 없으면 stdin 한 줄."""
        if provided is not None:
            return provided
        try:
            return input(prompt).strip()
        except EOFError:
            return ""
