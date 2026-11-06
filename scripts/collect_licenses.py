"""Copy dependency license texts from the actual build environment."""
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys


def collect(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    versions = {"Python": sys.version.split()[0]}
    for name in ("customtkinter", "tkinterdnd2", "Pillow", "darkdetect", "packaging", "PyInstaller"):
        distribution = metadata.distribution(name)
        versions[name] = distribution.version
        for relative in distribution.files or ():
            if not any(word in relative.name.upper() for word in ("LICENSE", "COPYING", "NOTICE")):
                continue
            source = Path(distribution.locate_file(relative))
            if source.is_file():
                safe_parts = [part for part in relative.parts if part not in ("..", ".")]
                target = destination / name / Path(*safe_parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copy2(python_license, destination / "Python-LICENSE.txt")
    for runtime in (Path(sys.base_prefix) / "tcl").glob("*/license.terms"):
        shutil.copy2(runtime, destination / (runtime.parent.name + "-license.terms"))
    original_notices = Path(__file__).resolve().parents[1] / "vendor" / "licenses"
    for name in ("Tcl-license.terms", "TkDnD-license.terms"):
        shutil.copy2(original_notices / name, destination / name)
    (destination / "dependency-versions.json").write_text(json.dumps(versions, indent=2), "utf-8")


if __name__ == "__main__":
    collect(Path(sys.argv[1]))
