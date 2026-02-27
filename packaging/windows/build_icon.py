from PIL import Image


def main() -> None:
    image = Image.open("qslmaster_gui/resources/icon.png")
    image.save(
        "qslmaster.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
