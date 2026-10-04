"""The Graphics panel's two bottom buttons at several window sizes and GUI scales, for looking at borders (dev tooling).

    python kotor/tools/py/gui_scales.py OUT.png EXE [BASE_EXE] WxH:SCALE [WxH:SCALE ...]

SCALE 0 is the automatic one. Each size is a headless run of EXE (and of BASE_EXE, when given, as the row's left
picture: before and after a change) that opens Options, then Graphics, and crops "Advanced Options" and "Enhanced
Graphics" out of the picture, enlarged without smoothing. A border that is right is one even outline: no second line
inside it, no brighter side. Run from the repository root; the panel's place comes from the 640x480 panels being
centred in the GUI's pixel space (the window over the scale).

    python kotor/tools/py/gui_scales.py kotor/out/scales.png kotor/out/kotor.exe 1440x1080:1.5 3840x2160:0
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw


def shot(exe, size, scale, name):
    w, h = map(int, size.split("x"))
    sc = float(scale)
    if sc == 0:
        sc = max(1.0, int(min(w / 800, h / 600) * 4) / 4)
    ui_w, ui_h = int(w / sc), int(h / sc)
    mx, my = (ui_w - 800) // 2, (ui_h - 600) // 2          # the 800x600 main menu
    ox, oy = (ui_w - 640) // 2, (ui_h - 480) // 2          # the 640x480 option panels

    def at(bx, by, px, py):
        return int((bx + px) * sc), int((by + py) * sc)

    options = at(mx, my, 485, 384)       # BTN_OPTIONS
    graphics = at(ox, oy, 191, 264)      # BTN_GRAPHICS
    lines = [f"25 mouse click {options[0]} {options[1]}", "28 mouse move 2 2",
             f"45 mouse click {graphics[0]} {graphics[1]}", "48 mouse move 2 2"]
    os.makedirs("kotor/out/scales", exist_ok=True)
    script = f"kotor/out/scales/{name}.txt"
    open(script, "w").write("\n".join(lines) + "\n")
    ini = f"kotor/out/scales/{name}.ini"
    open(ini, "w").write(f"[Graphics Options]\nGUI Scale={scale}\n")
    png = f"kotor/out/scales/{name}.png"
    subprocess.run([os.path.abspath(exe), "--headless", "--gfx", "--size", size, "--settings", ini, "--saves", "kotor/out/scales/saves",
                    "--frames", "70", "--input", script, "--screenshot-at", f"60:{png}"], capture_output=True)
    box = (int((ox + 56) * sc), int((oy + 348) * sc), int((ox + 304) * sc), int((oy + 404) * sc))
    im = Image.open(png).convert("RGB").crop(box)
    z = max(1, 480 // im.width)
    im = im.resize((im.width * z, im.height * z), Image.NEAREST)
    ImageDraw.Draw(im).text((2, 2), f"{name} x{sc}", fill=(255, 255, 0))
    return im


def main():
    out, exe = sys.argv[1:3]
    rest = sys.argv[3:]
    base = None
    if rest and ":" not in rest[0]:
        base, rest = rest[0], rest[1:]
    rows = []
    for combo in rest:
        size, scale = combo.split(":")
        row = []
        if base:
            row.append(shot(base, size, scale, f"base_{size}_{scale}"))
        row.append(shot(exe, size, scale, f"{size}_{scale}"))
        rows.append(row)
    width = max(sum(t.width + 8 for t in r) for r in rows)
    height = sum(max(t.height for t in r) + 4 for r in rows)
    sheet = Image.new("RGB", (width, height), (255, 0, 255))
    y = 0
    for r in rows:
        x = 0
        for t in r:
            sheet.paste(t, (x, y))
            x += t.width + 8
        y += max(t.height for t in r) + 4
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
