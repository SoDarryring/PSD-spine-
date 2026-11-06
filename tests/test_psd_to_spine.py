import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import psd_to_spine as core


class PsdExportTests(unittest.TestCase):
    def fake_photoshop(self, script):
        source = next(script.parent.glob("*.psd"))
        path = self.make_export(script.parent / "project")
        path.rename(path.with_name(source.stem + ".json"))
        image = path.parent / "images/head.png"
        image.parent.mkdir()
        image.write_bytes(b"test image")

    def fake_import(self, spine, source_json):
        result = source_json.with_suffix(".spine")
        result.write_bytes(b"test project")
        return result

    def test_successful_output_has_only_project_and_images_next_to_psd(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "分层 设计.psd"
            source.write_bytes(b"original PSD")
            spine = root / "Spine.com"
            spine.touch()
            with patch.object(core, "export_photoshop", side_effect=self.fake_photoshop), \
                    patch.object(core, "import_project", side_effect=self.fake_import):
                result = core.convert(source, None, spine, core.ExportOptions(), log=lambda text: None)
            self.assertEqual(result.parent.parent, source.parent)
            self.assertEqual({p.name for p in result.parent.iterdir()}, {"分层 设计.spine", "images"})
            self.assertEqual(source.read_bytes(), b"original PSD")
            self.assertFalse(list(root.glob(".psd-spine-*")))

    def test_json_only_keeps_requested_json_but_no_manifest_or_log(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "sample.psd"
            source.write_bytes(b"original PSD")
            with patch.object(core, "export_photoshop", side_effect=self.fake_photoshop):
                result = core.convert(source, None, None, core.ExportOptions(), json_only=True, log=lambda text: None)
            self.assertEqual({p.name for p in result.parent.iterdir()}, {"sample.json", "images"})

    def test_failure_cleans_temporary_files_without_touching_existing_results(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "sample.psd"
            source.write_bytes(b"original PSD")
            existing = root / "sample"
            existing.mkdir()
            (existing / "keep.txt").write_text("keep")
            with patch.object(core, "export_photoshop", side_effect=RuntimeError("export failed")):
                with self.assertRaisesRegex(RuntimeError, "export failed"):
                    core.convert(source, None, None, core.ExportOptions(), json_only=True, log=lambda text: None)
            self.assertEqual((existing / "keep.txt").read_text(), "keep")
            self.assertFalse(list(root.glob(".psd-spine-*")))
            self.assertFalse((root / "sample_2").exists())

    def test_frozen_resource_is_loaded_inside_bundle(self):
        with patch.object(core.sys, "frozen", True, create=True), \
                patch.object(core.sys, "_MEIPASS", "/private/bundle", create=True):
            self.assertEqual(core.resource_dir(), Path("/private/bundle/vendor/photoshop-to-spine"))

    def test_official_empty_slot_trailing_comma_is_repaired(self):
        data = core.load_export_json('{"slots":[{"name":"head"},\n],"skins":{},}')
        self.assertEqual(data, {"slots": [{"name": "head"}], "skins": {}})

    def test_repair_does_not_change_commas_or_escaped_quotes_inside_names(self):
        value = {"name": 'some ,] and ,} and \\"quotes"'}
        self.assertEqual(core.load_export_json(json.dumps(value)), value)

    def test_repair_does_not_hide_other_json_errors(self):
        with self.assertRaises(ValueError):
            core.load_export_json('{"slots": [broken,]}')

    def test_invalid_options_rejected_before_starting_photoshop(self):
        for options in (core.ExportOptions(scale=0), core.ExportOptions(scale=4.1),
                        core.ExportOptions(scale=float("nan")), core.ExportOptions(padding=-1),
                        core.ExportOptions(padding=1.5)):
            with self.subTest(options=options), self.assertRaises(ValueError):
                options.validate()

    def test_output_reservation_never_overwrites_and_handles_collisions(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            first = core.reserve_output(root, "同名 PSD")
            (first / "keep.txt").write_text("original")
            second = core.reserve_output(root, "同名 PSD")
            self.assertEqual(second.name, "同名 PSD_2")
            self.assertEqual((first / "keep.txt").read_text(), "original")

    def make_export(self, directory, image_name="head"):
        path = Path(directory) / "sample.json"
        data = {"bones": [{"name": "root"}],
                "slots": [{"name": "head", "bone": "root", "attachment": "head"}],
                "skins": {"default": {"head": {"head": {"path": image_name}}}},
                "animations": {"animation": {}}}
        path.write_text(json.dumps(data), "utf-8")
        return path

    def test_relative_image_path_survives_moving_output(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = self.make_export(root, "皮肤/头部")
            image = root / "images/皮肤/头部.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"image")
            stats = core.validate_export(path)
            self.assertEqual(stats, {"bones": 1, "slots": 1, "images": 1})
            self.assertEqual(json.loads(path.read_text("utf-8"))["skeleton"]["images"], "./images/")

    def test_missing_image_is_not_reported_as_success(self):
        with TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "缺少图层图片"):
                core.validate_export(self.make_export(folder))

    def test_path_traversal_in_attachment_is_rejected(self):
        with TemporaryDirectory() as folder:
            path = self.make_export(folder, "../outside")
            with self.assertRaisesRegex(ValueError, "超出"):
                core.validate_export(path)

    def test_empty_document_is_rejected(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "empty.json"
            path.write_text('{"bones":[{"name":"root"}],"slots":[]}', "utf-8")
            with self.assertRaisesRegex(ValueError, "没有可导出"):
                core.validate_export(path)

    def test_adapter_handles_quotes_unicode_and_windows_paths(self):
        script = core.build_export_script(Path("C:/test/a'b 中文.psd"),
                                          Path("C:/output/test.json"), core.ExportOptions())
        self.assertEqual(script.count("#target photoshop"), 1)
        self.assertNotIn("\nshowSettingsDialog();", script)
        self.assertIn("run();", script)
        self.assertIn("previousDocs", script)
        self.assertIn("DONOTSAVECHANGES", script)
        self.assertIn('"ignoreHiddenLayers": true', script)
        self.assertIn('"selectionOnly": false', script)
        self.assertIn("a'b \\u4e2d\\u6587.psd", script)

    def test_bottom_layer_origin_sets_real_psd_ruler_instead_of_only_moving_root(self):
        script = core.build_export_script(Path("source.psd"), Path("output.json"),
                                          core.ExportOptions(bottom_layer_origin=True))
        self.assertIn("if (true)", script)
        self.assertIn("container.layers.length - 1", script)
        self.assertIn("bottomLeaf(layer)", script)
        self.assertIn("setRulerOrigin((left + right) / 2, (top + bottom) / 2)", script)
        self.assertIn('desc.putInteger(cID("T   "), Math.round(values[a] * 65536))', script)

    def test_import_requires_exact_version_and_nonempty_real_project(self):
        with TemporaryDirectory() as folder:
            path = self.make_export(folder)
            def run(command, **kwargs):
                self.assertEqual(command[1:3], ["-u", "3.8.99"])
                self.assertEqual(kwargs["cwd"], path.parent)
                path.with_suffix(".spine").write_bytes(b"project")
                return core.subprocess.CompletedProcess(command, 0, b"OK", b"")
            with patch.object(core.subprocess, "run", side_effect=run):
                self.assertEqual(core.import_project(Path("Spine.com"), path), path.with_suffix(".spine"))

    def test_zero_exit_without_project_is_failure(self):
        with TemporaryDirectory() as folder:
            path = self.make_export(folder)
            with patch.object(core.subprocess, "run", return_value=core.subprocess.CompletedProcess([], 0, b"", b"")):
                with self.assertRaisesRegex(RuntimeError, "工程生成失败"):
                    core.import_project(Path("Spine.com"), path)

    def test_existing_project_is_never_deleted(self):
        with TemporaryDirectory() as folder:
            path = self.make_export(folder)
            project = path.with_suffix(".spine")
            project.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                core.import_project(Path("Spine.com"), path)
            self.assertEqual(project.read_bytes(), b"original")

    def test_spine_exe_resolves_console_sibling(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Spine.exe").touch()
            (root / "Spine.com").touch()
            self.assertEqual(core.find_spine(str(root / "Spine.exe")), (root / "Spine.com").resolve())


if __name__ == "__main__":
    unittest.main()
