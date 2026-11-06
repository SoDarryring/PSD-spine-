"""Copy dependency license texts from the actual build environment."""
import importlib.metadata as metadata
import hashlib
import json
from pathlib import Path
import shutil
import sys


def collect(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    versions = {"Python": sys.version.split()[0]}
    for name in ("customtkinter", "tkinterdnd2", "Pillow", "darkdetect", "packaging", "PyInstaller"):
        try:
            distribution = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            if name == "PyInstaller":  # Optional when running directly from source.
                continue
            raise
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


def collect_bundle(destination: Path):
    """Build the original license resource embedded in EXE."""
    root = Path(__file__).resolve().parents[1]
    destination.mkdir(parents=True, exist_ok=True)
    collect(destination / "licenses")
    for source, name in ((root / "LICENSE", "LICENSE"),
                         (root / "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md"),
                         (root / "vendor/photoshop-to-spine/LICENSE", "licenses/PhotoshopToSpine-LICENSE.txt")):
        shutil.copy2(source, destination / name)
    titles = {"LICENSE": "项目许可证（MIT）",
              "THIRD_PARTY_NOTICES.md": "第三方组件说明"}
    entries = []
    used_titles = set()
    files = [destination / name for name in titles]
    files.extend(sorted((destination / "licenses").rglob("*")))
    for file in files:
        if not file.is_file():
            continue
        relative = file.relative_to(destination).as_posix()
        parts = file.relative_to(destination).parts
        title = titles.get(relative) or (parts[1] + " / " + file.name if len(parts) > 2 else file.name)
        if title in used_titles:
            title = relative
        used_titles.add(title)
        entries.append({"path": relative, "title": title,
                        "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
    (destination / "index.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), "utf-8")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--bundle":
        collect_bundle(Path(sys.argv[2]))
    else:
        collect(Path(sys.argv[1]))
