"""Optional: assemble actual app screenshots into a clearly labeled visual walkthrough.

Install Pillow + imageio-ffmpeg in a separate media environment; neither is an app runtime dependency.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if (ROOT / ".runtime/media").exists():
    sys.path.insert(0, str(ROOT / ".runtime/media"))


def main():
    from PIL import Image, ImageDraw, ImageFont
    import imageio_ffmpeg

    output = ROOT / "docs/demos/retailiq-walkthrough.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    title_font = ImageFont.truetype(str(font_path), 28) if font_path.exists() else ImageFont.load_default(size=28)
    small_font = ImageFont.truetype(str(font_path), 16) if font_path.exists() else ImageFont.load_default(size=16)
    scenes = [
        ("overview-desktop.png", "01 / Overview", "Sales, stock and the next 28 days."),
        (
            "forecasts-desktop.png",
            "02 / Demand forecasts",
            "Compare a baseline with ML. Inspect held-out error and daily uncertainty.",
        ),
        (
            "inventory-desktop.png",
            "03 / Inventory planner",
            "Review stock targets, supplier packs, budgets and explained proposals.",
        ),
        (
            "scenarios-desktop.png",
            "04 / Scenario lab",
            "Compare matched simulated outcomes; real business savings are unverified.",
        ),
        ("catalog-desktop.png", "05 / Product catalog", "Explore the products behind the numbers."),
    ]
    writer = imageio_ffmpeg.write_frames(
        str(output),
        (1440, 1088),
        fps=12,
        codec="libx264",
        pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p",
        quality=7,
        macro_block_size=16,
        ffmpeg_log_level="error",
    )
    writer.send(None)
    for name, title, description in scenes:
        screenshot = Image.open(ROOT / "docs/screenshots" / name).convert("RGB")
        screenshot = screenshot.resize((1440, round(screenshot.height * 1440 / screenshot.width)))
        frame = Image.new("RGB", (1440, 1088), "#f5f5ee")
        frame.paste(screenshot.crop((0, 0, 1440, min(1000, screenshot.height))), (0, 88))
        draw = ImageDraw.Draw(frame)
        draw.rectangle((0, 0, 1440, 88), fill="#203c2e")
        draw.text((28, 10), f"RetailIQ   /   {title}", font=title_font, fill="#eef3e2")
        draw.text((28, 49), description, font=small_font, fill="#c9d8b2")
        draw.text((1050, 16), "CAPTURED SCREEN WALKTHROUGH", font=small_font, fill="#c9d8b2")
        draw.text((1050, 43), "Synthetic demo · no actual purchases", font=small_font, fill="#c9d8b2")
        raw = frame.tobytes()
        for _ in range(5 * 12):
            writer.send(raw)
    writer.close()
    print(f"Created {output.name}: 25-second screenshot-based walkthrough.")


if __name__ == "__main__":
    main()
