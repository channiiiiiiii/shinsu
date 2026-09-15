"""DAMAGOCHI 원본 이미지를 모바일용 WebP로 재현 가능하게 변환한다."""
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "DAMAGOCHI" / "assets"
TARGET = ROOT / "web" / "game-assets"
SPECIES = ("tiger", "lion", "wolf", "dragon", "phoenix", "turtle", "fox", "griffin", "kirin", "bahamut")


def convert(source: Path, target: Path, size: int, quality: int = 82) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
        image.save(target, "WEBP", quality=quality, method=6)


def main() -> None:
    for species in SPECIES:
        for stage in range(1, 5):
            source = SOURCE / species / f"{species}_stage{stage}.png"
            convert(source, TARGET / "species" / species / f"stage{stage}.webp", 760)
    for source in (SOURCE / "bosses").iterdir():
        if source.is_file() and source.stem != "ifrit":
            convert(source, TARGET / "bosses" / f"{source.stem}.webp", 900)
    convert(SOURCE / "bosses" / "ifrit.png", TARGET / "bosses" / "ifrit.webp", 900)
    for source in (SOURCE / "promo").iterdir():
        if source.is_file():
            convert(source, TARGET / "promo" / f"{source.stem}.webp", 1100, 84)
    print("신수 40장, 보스 5장, 홍보 4장 변환 완료")


if __name__ == "__main__":
    main()
