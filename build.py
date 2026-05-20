#!/usr/bin/env python3
"""
Cross-platform build script for tracker-config.
Usage:
    python3 build.py          # build for current OS
    python3 build.py --clean  # remove dist/ and build/ first
"""

import sys
import os
import shutil
import subprocess
import argparse
from pathlib import Path

ROOT   = Path(__file__).parent
DIST   = ROOT / "dist"
BUILD  = ROOT / "build"
SPEC   = ROOT / "tracker-config.spec"
OUTPUT = DIST / "tracker-config"


def clean():
    for d in (DIST, BUILD):
        if d.exists():
            shutil.rmtree(d)
            print(f"Removed {d}")


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        str(SPEC),
    ]
    print(f"Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print("\n✗ Build failed.")
        sys.exit(1)


def post_build():
    """Create platform-specific launcher and print instructions."""
    if sys.platform == "win32":
        _post_windows()
    else:
        _post_linux()


def _post_linux():
    launcher = ROOT / "dist" / "tracker-config.sh"
    launcher.write_text(
        "#!/bin/bash\n"
        "# Stops ModemManager and launches tracker-config\n"
        "SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n"
        "if systemctl is-active --quiet ModemManager 2>/dev/null; then\n"
        "    sudo systemctl stop ModemManager\n"
        "fi\n"
        "\"$SCRIPT_DIR/tracker-config/tracker-config\" \"$@\"\n"
    )
    launcher.chmod(0o755)

    print("\n✓ Build concluído!")
    print(f"\n  Executável: {OUTPUT}/tracker-config")
    print(f"  Launcher:   {launcher}")
    print("\nPara instalar (opcional):")
    print("  sudo cp -r dist/tracker-config /opt/tracker-config")
    print("  sudo cp dist/tracker-config.sh /usr/local/bin/tracker-config")
    print("  sudo chmod +x /usr/local/bin/tracker-config")
    print("\nPré-requisitos no sistema:")
    print("  sudo apt install libxcb-cursor0")
    print("  sudo usermod -aG dialout $USER")


def _post_windows():
    exe = OUTPUT / "tracker-config.exe"
    print("\n✓ Build concluído!")
    print(f"\n  Executável: {exe}")
    print("\nDistribua a pasta dist/tracker-config/ completa.")
    print("O .exe não funciona sozinho — depende das DLLs na mesma pasta.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", help="Remove dist/ e build/ antes de compilar")
    args = parser.parse_args()

    print(f"tracker-config build — {sys.platform}")
    print("=" * 50)

    if args.clean:
        clean()

    build()
    post_build()


if __name__ == "__main__":
    main()
