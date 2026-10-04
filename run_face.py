#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path


FACEFUSION = Path(__file__).parent / "facefusion" / "run_facefusion_cuda.sh"


def main():
    if len(sys.argv) != 4:
        print(
            f"Использование:\n"
            f"  python {Path(sys.argv[0]).name} <source> <target> <output>\n\n"
            f"Пример:\n"
            f"  python {Path(sys.argv[0]).name} test.png t2.mp4 result.mp4"
        )
        sys.exit(1)

    source = Path(sys.argv[1]).expanduser().resolve()
    target = Path(sys.argv[2]).expanduser().resolve()
    output = Path(sys.argv[3]).expanduser().resolve()

    if not source.exists():
        print(f"Ошибка: source не найден: {source}")
        sys.exit(1)

    if not target.exists():
        print(f"Ошибка: target не найден: {target}")
        sys.exit(1)

    command = [
        str(FACEFUSION),
        "headless-run",

        "--processors", "face_swapper",
        "--execution-providers", "cuda",

        "--source-paths", str(source),
        "--target-path", str(target),
        "--output-path", str(output),

        "--face-swapper-model", "hyperswap_1a_256",
        "--face-swapper-pixel-boost", "512x512",

        "--workflow-strategy", "disk",
        "--video-memory-strategy", "strict",
        "--execution-thread-count", "1",

        "--log-level", "info",
    ]

    print("Запуск FaceFusion:")
    print(" ".join(command))
    print()

    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
