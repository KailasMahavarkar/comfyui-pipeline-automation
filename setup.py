"""Setup script for ComfyUI Pipeline Automation nodes."""

import sys
import subprocess


MIN_PYTHON = (3, 10)


def check_python():
    if sys.version_info < MIN_PYTHON:
        print(f"ERROR: Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required "
              f"(you have {sys.version_info.major}.{sys.version_info.minor})")
        sys.exit(1)
    print(f"Python {sys.version_info.major}.{sys.version_info.minor} ... OK")


def install_requirements():
    print("Installing dependencies...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        check=False,
    )
    if result.returncode != 0:
        print("ERROR: pip install failed.")
        sys.exit(1)
    print("Dependencies installed ... OK")


def verify_imports():
    imports = [
        ("PIL", "Pillow"),
        ("numpy", "numpy"),
        ("piexif", "piexif"),
        ("croniter", "croniter"),
    ]
    failed = []
    for module, package in imports:
        try:
            __import__(module)
            print(f"  {package} ... OK")
        except ImportError:
            print(f"  {package} ... MISSING")
            failed.append(package)

    if failed:
        print(f"ERROR: Failed to import: {', '.join(failed)}")
        sys.exit(1)


def main():
    print("=== ComfyUI Pipeline Automation Setup ===\n")
    check_python()
    install_requirements()
    print("\nVerifying imports:")
    verify_imports()
    print("\nSetup complete. Restart ComfyUI to load the nodes.")


if __name__ == "__main__":
    main()
