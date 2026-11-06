#!/usr/bin/env python3
"""PSD → official PhotoshopToSpine exporter → Spine 3.8.99 project.

Only the standard library is required. Photoshop is controlled through its
installed COM interface using Windows PowerShell, without installing a plugin.
"""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable

VERSION = "1.1.4"
SPINE_VERSION = "3.8.99"
UPSTREAM_REVISION = "69c429295b5b19f66f959ad2ac644d40a14121e5"
UPSTREAM_SHA256 = "554b924e22189cd08fdea02e10530827f3a22ad790ee5a85975f511329bcf9ef"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def resource_dir() -> Path:
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    return base / "vendor" / "photoshop-to-spine"


def settings_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SpinePsdConverter"


def read_settings() -> dict:
    try:
        value = json.loads((settings_dir() / "settings.json").read_text("utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(value: dict) -> None:
    directory = settings_dir()
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / "settings.tmp"
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf-8")
    temporary.replace(directory / "settings.json")


def find_spine(configured: str = "") -> Path | None:
    candidates = [configured, os.environ.get("SPINE_EXE", ""),
                  read_settings().get("spine", ""), shutil.which("Spine.com")]
    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(key):
            candidates.append(str(Path(os.environ[key]) / "Spine" / "Spine.com"))
    if os.name == "nt":
        import ctypes
        drives = ctypes.windll.kernel32.GetLogicalDrives()
        for index in range(26):
            if drives & (1 << index):
                root = Path(f"{chr(65 + index)}:/")
                candidates.append(str(root / "Spine" / "Spine.com"))
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.name.lower() == "spine.exe" and path.with_suffix(".com").is_file():
            path = path.with_suffix(".com")
        if path.is_file():
            return path.resolve()
    return None


@dataclass(frozen=True)
class ExportOptions:
    scale: float = 1.0
    padding: int = 1
    ignore_hidden: bool = True
    ignore_background: bool = True
    trim: bool = True
    bottom_layer_origin: bool = False

    def validate(self):
        if not 0 < self.scale <= 4:
            raise ValueError("缩放比例必须大于 0 且不超过 400%。")
        if not isinstance(self.padding, int) or not 0 <= self.padding <= 256:
            raise ValueError("图片留边必须是 0～256 的整数。")


@contextmanager
def photoshop_lock():
    """Serialize this tool's instances, including ones with different outputs."""
    import msvcrt
    directory = settings_dir()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "photoshop.lock").open("a+b") as stream:
        if stream.seek(0, 2) == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("另一项 PSD 转换正在使用 Photoshop，请等待完成。") from exc
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def reserve_output(root: Path, stem: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for index in range(1, 100000):
        destination = root / (stem if index == 1 else f"{stem}_{index}")
        try:
            destination.mkdir()
            return destination
        except FileExistsError:
            continue
    raise RuntimeError("同名输出目录过多，请选择其他输出位置。")


def build_export_script(source: Path, target_json: Path, options: ExportOptions) -> str:
    """Adapt the integration points; keep the vendored exporter byte-for-byte."""
    options.validate()
    try:
        raw = (resource_dir() / "PhotoshopToSpine.jsx").read_bytes()
    except FileNotFoundError as exc:
        raise RuntimeError("缺少内置官方插件，请重新完整解压软件。") from exc
    if hashlib.sha256(raw).hexdigest() != UPSTREAM_SHA256:
        raise RuntimeError("官方插件文件与已验证版本不一致，请重新完整解压软件。")
    upstream = raw.decode("utf-8-sig")
    if not upstream.rstrip().endswith("showSettingsDialog();"):
        raise RuntimeError("官方插件入口发生变化，停止转换以避免弹出未受控的对话框。")
    upstream = upstream.rstrip()[:-len("showSettingsDialog();")]
    upstream = re.sub(r"^#target photoshop\s*$", "", upstream, flags=re.MULTILINE)
    upstream = upstream.replace("app.bringToFront();", "")
    # Enforce the image boundary BEFORE Photoshop writes a file. Names can
    # contain folder tags, so post-export validation alone is too late.
    image_writer = 'new File(imagesDir + attachmentPath + ".png")'
    if upstream.count(image_writer) != 1:
        raise RuntimeError("官方插件图片写入入口发生变化，停止转换。")
    upstream = upstream.replace(image_writer, "checkedImageFile(imagesDir, attachmentPath)")
    config = {
        "language": "zh", "ignoreHiddenLayers": options.ignore_hidden,
        "ignoreBackground": options.ignore_background, "writeTemplate": False,
        "writeJson": True, "trimWhitespace": options.trim, "selectionOnly": False,
        "scale": options.scale, "padding": options.padding,
        "imagesDir": str(target_json.parent / "images").replace("\\", "/") + "/",
        "jsonPath": str(target_json).replace("\\", "/"),
    }
    # All source processing happens on a private on-disk copy. Even the official
    # exporter's metadata cleanup cannot dirty the user's original document.
    return """#target photoshop
(function () {
    var previousDocs = [], previousActive = null;
    var oldDialogs = app.displayDialogs, oldUnits = app.preferences.rulerUnits;
    for (var i = 0; i < app.documents.length; i++) previousDocs.push(app.documents[i]);
    if (app.documents.length) previousActive = app.activeDocument;
    var alert = function (message) { throw new Error(String(message)); };
    function checkedImageFile (directory, name) {
        var decoded = name;
        try { decoded = decodeURIComponent(name); } catch (ignored) {}
        decoded = decoded.replace(/\\\\/g, "/");
        if (/^[\\/]|[:\\x00-\\x1f]/.test(decoded) || /(^|\\/)\\.\\.?([\\/]|$)/.test(decoded))
            throw new Error("图层图片路径必须位于 images 目录中，请检查 [folder] 或 [path] 标签。");
        var file = new File(directory + name + ".png");
        var base = new Folder(directory).fsName.replace(/\\\\/g, "/").toLowerCase() + "/";
        if (file.fsName.replace(/\\\\/g, "/").toLowerCase().indexOf(base) !== 0)
            throw new Error("图层图片路径超出 images 目录。");
        return file;
    }
    try {
        app.displayDialogs = DialogModes.NO;
        app.preferences.rulerUnits = Units.PIXELS;
        app.open(new File(SOURCE_FILE));
        OFFICIAL_SCRIPT
        settings = EXPORT_SETTINGS;
        selectLanguage();
        showProgress = function () {};
        incrProgress = function (name) { lastLayerName = name; };
        if (BOTTOM_LAYER_ORIGIN) {
            // Only the private document is changed. Measure in canvas pixels,
            // then let the official exporter handle bones, meshes and scaling
            // using Photoshop's real ruler origin, including its crop logic.
            function setRulerOrigin (x, y) {
                var axes = ["H", "V"], values = [x, y];
                for (var a = 0; a < 2; a++) {
                    var desc = new ActionDescriptor(), ref = new ActionReference();
                    ref.putProperty(cID("Prpr"), cID("Rlr" + axes[a]));
                    ref.putEnumerated(cID("Dcmn"), cID("Ordn"), cID("Trgt"));
                    desc.putReference(cID("null"), ref);
                    desc.putInteger(cID("T   "), Math.round(values[a] * 65536));
                    executeAction(cID("setd"), desc, DialogModes.NO);
                }
            }
            setRulerOrigin(0, 0);
            function bottomLeaf (container) {
                for (var b = container.layers.length - 1; b >= 0; b--) {
                    var layer = container.layers[b];
                    if (layer.typename == "LayerSet") {
                        var child = bottomLeaf(layer);
                        if (child) return child;
                    } else return layer;
                }
                return null;
            }
            var originLayer = bottomLeaf(originalDoc);
            if (!originLayer) throw new Error("PSD 没有可用于中心点的最底层图层。");
            var originBounds;
            try { originBounds = originLayer.boundsNoEffects; } catch (ignored) {}
            if (!originBounds) originBounds = originLayer.bounds;
            var left = originBounds[0].as("px"), top = originBounds[1].as("px");
            var right = originBounds[2].as("px"), bottom = originBounds[3].as("px");
            if (!(right > left && bottom > top))
                throw new Error("最底层图层为空，无法确定中心点。请调整最底层图层或关闭中心点选项。");
            setRulerOrigin((left + right) / 2, (top + bottom) / 2);
        }
        cancel = false;
        run();
        if (cancel) throw new Error("转换已取消。");
        if (errors && errors.length) throw new Error(errors.join("\\n"));
        if (!new File(EXPORT_FILE).exists) throw new Error("官方插件未生成 JSON。");
        return "OK";
    } catch (e) {
        throw new Error((lastLayerName ? "[" + lastLayerName + "] " : "") + e.message);
    } finally {
        for (var d = app.documents.length - 1; d >= 0; d--) {
            var doc = app.documents[d], owned = true;
            for (var p = 0; p < previousDocs.length; p++) {
                if (doc == previousDocs[p]) { owned = false; break; }
            }
            if (owned) { try { doc.close(SaveOptions.DONOTSAVECHANGES); } catch (ignored) {} }
        }
        if (previousActive) { try { app.activeDocument = previousActive; } catch (ignored) {} }
        app.displayDialogs = oldDialogs;
        app.preferences.rulerUnits = oldUnits;
    }
})();
""".replace("OFFICIAL_SCRIPT", upstream).replace(
        "SOURCE_FILE", json.dumps(str(source).replace("\\", "/"), ensure_ascii=True)
    ).replace("BOTTOM_LAYER_ORIGIN", str(options.bottom_layer_origin).lower()).replace(
        "EXPORT_SETTINGS", json.dumps(config, ensure_ascii=True)).replace(
        "EXPORT_FILE", json.dumps(str(target_json).replace("\\", "/"), ensure_ascii=True)
    )


def export_photoshop(script: Path) -> None:
    # Paths are data in an environment variable, never interpolated into shell code.
    command = """
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$photoshop = $null
try {
    $photoshop = New-Object -ComObject Photoshop.Application
    $result = $photoshop.DoJavaScriptFile($env:SPINE_PSD_SCRIPT)
    if ($result -ne 'OK') { throw 'Photoshop 未返回成功状态。' }
    Write-Output 'OK'
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
} finally {
    if ($null -ne $photoshop) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($photoshop) }
}
"""
    encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
    env = dict(os.environ, SPINE_PSD_SCRIPT=str(script))
    # Do not terminate Photoshop or abandon a running COM script on a timer.
    # The GUI stays responsive and can stop the batch after the current PSD.
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-EncodedCommand", encoded],
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError("Photoshop 导出失败：" + detail)


def load_export_json(text: str) -> dict:
    # v7.42 counts empty slots but skips writing them, which can leave a trailing
    # comma. Repair structural trailing commas only, never text inside a name.
    result = []
    in_string = escaped = False
    for index, character in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character == ",":
            following = index + 1
            while following < len(text) and text[following].isspace():
                following += 1
            if following < len(text) and text[following] in "]}":
                continue
        result.append(character)
    return json.loads("".join(result))


def validate_export(path: Path) -> dict:
    data = load_export_json(path.read_text("utf-8-sig"))
    if not data.get("bones") or not data.get("slots"):
        raise ValueError("PSD 没有可导出的图层，请检查可见性及 [ignore] 标签。")
    skins = data.get("skins", {})
    if not isinstance(skins, dict):
        raise ValueError("插件输出不是预期的旧版 Spine JSON 格式。")
    images = path.parent / "images"
    image_count = 0
    for skin in skins.values():
        for slot in skin.values():
            for name, attachment in slot.items():
                if attachment.get("type") == "linkedmesh":
                    continue
                image_name = attachment.get("path", name)
                image_path = (images / (image_name + ".png")).resolve()
                if not image_path.is_relative_to(images.resolve()):
                    raise ValueError("图层图片引用超出 images 目录，请检查图层命名。")
                if not image_path.is_file():
                    raise ValueError(f"缺少图层图片：{image_name}.png")
                image_count += 1
    if not image_count:
        raise ValueError("官方插件没有导出可用图片。")
    data.setdefault("skeleton", {})["images"] = "./images/"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    return {"bones": len(data["bones"]), "slots": len(data["slots"]), "images": image_count}


def import_project(spine: Path, source_json: Path, timeout: int = 180) -> Path:
    project = source_json.with_suffix(".spine")
    if project.exists():
        raise FileExistsError("输出工程已存在，停止以避免覆盖。")
    command = [str(spine), "-u", SPINE_VERSION, "-i", source_json.name,
               "-o", project.name, "-r"]
    completed = subprocess.run(command, cwd=source_json.parent, capture_output=True,
                               timeout=timeout, creationflags=CREATE_NO_WINDOW)
    output = completed.stdout.decode("utf-8", errors="replace")
    errors = completed.stderr.decode("utf-8", errors="replace")
    if completed.returncode or not project.is_file() or not project.stat().st_size:
        diagnostics = settings_dir() / "diagnostics"
        diagnostics.mkdir(parents=True, exist_ok=True)
        (diagnostics / "spine-import.log").write_text(output + errors, "utf-8")
        raise RuntimeError("Spine 3.8.99 工程生成失败，请确认程序已激活且可运行 3.8.99；诊断日志已保存到软件配置区。")
    return project


def convert(source: Path, output: Path | None, spine: Path | None, options: ExportOptions,
            log: Callable[[str], None] = print, *, json_only: bool = False) -> Path:
    if os.name != "nt":
        raise RuntimeError("本工具需要 Windows 和已安装的 Photoshop。")
    source = source.resolve()
    if source.suffix.lower() not in (".psd", ".psb") or not source.is_file():
        raise ValueError("请选择存在的 PSD 或 PSB 源文件。")
    options.validate()
    if not json_only and (spine is None or not spine.is_file()):
        raise ValueError("生成 .spine 需要先选择已安装并激活的 Spine 程序。")
    output_root = output.resolve() if output is not None else source.parent
    output_root.mkdir(parents=True, exist_ok=True)
    with photoshop_lock():
        # Keep all intermediate files out of the delivered project. The temporary
        # directory is on the destination volume so large PSDs don't fill the
        # system drive. Completed files are moved into a newly reserved folder.
        with tempfile.TemporaryDirectory(prefix=".psd-spine-", dir=output_root) as temporary:
            work = Path(temporary)
            private_source = work / source.name
            log(f"复制源文件：{source.name}")
            shutil.copy2(source, private_source)
            job = work / "project"
            job.mkdir()
            target_json = job / (source.stem + ".json")
            script = work / "export.jsx"
            script.write_text(build_export_script(private_source, target_json, options), "utf-8-sig")
            log("Photoshop 正在处理图层、蒙版和图层样式，请等待……")
            export_photoshop(script)
            stats = validate_export(target_json)
            log(f"导出完成：{stats['images']} 张图片，{stats['bones']} 根骨骼，{stats['slots']} 个插槽。")
            if json_only:
                result = target_json
            else:
                log("正在通过 Spine 3.8.99 生成工程……")
                result = import_project(spine, target_json)
                target_json.unlink()
            # Only the selected delivery format and images leave staging.
            destination = reserve_output(output_root, source.stem)
            published = []
            try:
                for entry in job.iterdir():
                    final = destination / entry.name
                    entry.replace(final)
                    published.append(final)
            except OSError:
                for entry in reversed(published):
                    entry.replace(job / entry.name)
                destination.rmdir()  # Empty directory reserved by this job only.
                raise
            result = destination / result.name
            log(f"完成：{destination.name}/{result.name}")
            return result


def main(argv=None) -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="通过官方 Photoshop 插件一键生成 Spine 3.8.99 工程")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=None, help="默认在每个 PSD 所在目录创建同名工程文件夹")
    parser.add_argument("--spine", default="")
    parser.add_argument("--scale", type=float, default=100, help="缩放百分比，默认 100")
    parser.add_argument("--padding", type=int, default=1)
    parser.add_argument("--include-hidden", action="store_true")
    parser.add_argument("--include-background", action="store_true")
    parser.add_argument("--no-trim", action="store_true")
    parser.add_argument("--bottom-layer-origin", action="store_true", help="以最底层图层内容边界的中心作为 Spine 原点")
    parser.add_argument("--json-only", action="store_true", help="仅输出 JSON 和图片，不生成 .spine")
    args = parser.parse_args(argv)
    options = ExportOptions(args.scale / 100, args.padding, not args.include_hidden,
                            not args.include_background, not args.no_trim, args.bottom_layer_origin)
    spine = find_spine(args.spine)
    failed = 0
    for source in args.inputs:
        try:
            convert(source, args.output, spine, options, json_only=args.json_only)
        except Exception as exc:
            print(f"[失败] {source.name}：{exc}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
