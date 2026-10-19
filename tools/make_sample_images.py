#!/usr/bin/env python3
"""샘플 랙 이미지 생성 — 표준 라이브러리만으로 PNG를 그린다.

촬영 어댑터(시뮬레이터)가 반환할 이미지다. 각 지시 대상 빈의 랙을
4단 선반으로 그리고, 선반별 박스 수를 실제 재고(actual_qty)와 같게
맞춘다. 대상 선반은 주황 테두리로 강조한다 (웹 데모 랙 장면과 같은 구도).

실행: python3 tools/make_sample_images.py  → assets/rack-<bin>.png, default-rack.png
"""

import struct
import sys
import zlib
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import data as ewm_data  # noqa: E402

W, H = 720, 1000

# 5x7 비트맵 글꼴 (필요 문자만)
FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", ".#.#.", "..#..", "..#..", "..#..", ".#.#.", "#...#"),
    "Y": ("#...#", ".#.#.", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "0": (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "2": (".###.", "#...#", "....#", "..##.", ".#...", "#....", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
}


class Canvas:
    def __init__(self, w, h, color):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)
        self.rect(0, 0, w, h, color)

    def rect(self, x, y, w, h, color):
        r, g, b = color
        for yy in range(max(0, y), min(self.h, y + h)):
            base = (yy * self.w + max(0, x)) * 3
            for xx in range(max(0, x), min(self.w, x + w)):
                i = (yy * self.w + xx) * 3
                self.px[i:i + 3] = bytes((r, g, b))
            _ = base

    def border(self, x, y, w, h, color, t=3):
        self.rect(x, y, w, t, color)
        self.rect(x, y + h - t, w, t, color)
        self.rect(x, y, t, h, color)
        self.rect(x + w - t, y, t, h, color)

    def text(self, x, y, s, color, scale=2):
        cx = x
        for ch in s.upper():
            glyph = FONT.get(ch, FONT[" "])
            for row_i, row in enumerate(glyph):
                for col_i, cell in enumerate(row):
                    if cell == "#":
                        self.rect(cx + col_i * scale, y + row_i * scale, scale, scale, color)
            cx += 6 * scale
        return cx

    def save_png(self, path):
        raw = b"".join(
            b"\x00" + bytes(self.px[y * self.w * 3:(y + 1) * self.w * 3])
            for y in range(self.h)
        )

        def chunk(tag, payload):
            c = struct.pack(">I", len(payload)) + tag + payload
            return c + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

        png = (b"\x89PNG\r\n\x1a\n"
               + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
               + chunk(b"IEND", b""))
        Path(path).write_bytes(png)


BG = (24, 28, 36)
POST = (95, 106, 122)
SHELF_BG = (36, 42, 54)
SHELF_BG_T = (56, 46, 34)
BOARD = (70, 79, 94)
BOX = (192, 148, 98)
BOX_T = (228, 182, 118)
BOX_LINE = (128, 94, 56)
PLATE = (14, 18, 24)
WHITE = (235, 238, 242)
ORANGE = (255, 150, 50)


def draw_rack(rack_id, target_bin):
    img = Canvas(W, H, BG)
    zone = rack_id.split("-")[0]
    img.rect(0, 0, W, 64, (14, 18, 24))
    img.text(28, 18, "RACK %s  ZONE %s" % (rack_id, zone), WHITE, scale=3)
    if target_bin:
        img.text(430, 18, "TARGET", ORANGE, scale=3)

    bins = list(reversed(ewm_data.RACK_BINS[rack_id]))  # 웹 데모처럼 위→아래 역순
    shelf_h = 224
    top = 84
    for i, bin_id in enumerate(bins):
        y = top + i * shelf_h
        record = ewm_data.find_inventory(bin_id)
        is_target = bin_id == target_bin
        img.rect(28, y, W - 56, shelf_h - 14, SHELF_BG_T if is_target else SHELF_BG)
        if is_target:
            img.border(28, y, W - 56, shelf_h - 14, ORANGE, 4)
        img.rect(28, y + shelf_h - 26, W - 56, 12, BOARD)  # 선반 판
        # 이름표
        label = bin_id + ("  " + record["sku"] if record else "")
        img.rect(44, y + 12, len(label) * 12 + 16, 30, PLATE)
        img.text(52, y + 19, label, ORANGE if is_target else WHITE, scale=2)
        # 박스: actual_qty만큼
        qty = record["actual_qty"] if record else 0
        bx, by = 48, y + 56
        per_row = 9
        for n in range(qty):
            col, row = n % per_row, n // per_row
            x = bx + col * 66
            yy = by + row * 50
            img.rect(x, yy, 56, 42, BOX_T if is_target else BOX)
            img.border(x, yy, 56, 42, BOX_LINE, 2)
            img.rect(x + 4, yy + 18, 48, 5, BOX_LINE)  # 테이프 줄
    # 기둥
    img.rect(16, 76, 12, H - 92, POST)
    img.rect(W - 28, 76, 12, H - 92, POST)
    return img


def main():
    assets = BASE / "assets"
    assets.mkdir(exist_ok=True)
    made = []
    for bin_id in ewm_data.TASK_BINS:
        rack_id = ewm_data.rack_of_bin(bin_id)
        path = assets / ("rack-%s.png" % bin_id)
        draw_rack(rack_id, bin_id).save_png(path)
        made.append(path.name)
    draw_rack("A-01", None).save_png(assets / "default-rack.png")
    made.append("default-rack.png")
    print("생성 완료:", ", ".join(made))


if __name__ == "__main__":
    main()
