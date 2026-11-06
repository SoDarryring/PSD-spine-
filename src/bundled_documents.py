"""Read and verify original license texts carried inside the EXE."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def document_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "documents"
    root = Path(__file__).resolve().parents[1]
    destination = root / ".work" / "embedded-notices"
    index = destination / "index.json"
    sources = [Path(__file__), root / "scripts/collect_licenses.py", root / "LICENSE", root / "THIRD_PARTY_NOTICES.md"]
    if not index.is_file() or any(file.stat().st_mtime > index.stat().st_mtime for file in sources):
        spec = importlib.util.spec_from_file_location("license_builder", root / "scripts" / "collect_licenses.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        builder.collect_bundle(destination)
    return destination


def document_entries() -> list[dict]:
    entries = json.loads((document_root() / "index.json").read_text("utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("内置许可目录为空。")
    return entries


def read_document(entry: dict) -> bytes:
    root = document_root().resolve()
    path = (root / entry["path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("内置许可文件缺失或路径无效。")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("内置许可文件校验失败。")
    return data


def verify_documents() -> int:
    entries = document_entries()
    for entry in entries:
        read_document(entry)
    required = {"LICENSE", "THIRD_PARTY_NOTICES.md",
                "licenses/PhotoshopToSpine-LICENSE.txt", "licenses/Tcl-license.terms",
                "licenses/TkDnD-license.terms"}
    if not required.issubset({entry["path"] for entry in entries}):
        raise ValueError("内置许可材料不完整。")
    return len(entries)
