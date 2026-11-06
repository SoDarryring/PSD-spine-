"""Opt-in checks with real Photoshop and Spine, using generated artwork only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

import psd_to_spine as core


@unittest.skipUnless(os.name == "nt" and os.environ.get("PSD_SPINE_INTEGRATION") == "1",
                     "Set PSD_SPINE_INTEGRATION=1 on Windows to run commercial-app integration checks")
class PhotoshopIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory(prefix="psd-spine-integration-")
        cls.root = Path(cls.temporary.name)
        cls.source = cls.root / "中文 中心点.psd"
        script = cls.root / "create-fixture.jsx"
        text = """#target photoshop
(function () {
    var previous = app.documents.length ? app.activeDocument : null;
    var oldDialogs = app.displayDialogs, oldUnits = app.preferences.rulerUnits;
    var doc = null;
    try {
        app.displayDialogs = DialogModes.NO;
        app.preferences.rulerUnits = Units.PIXELS;
        doc = app.documents.add(400, 300, 72, "PSD-to-Spine-generated-fixture", NewDocumentMode.RGB, DocumentFill.TRANSPARENT);
        var initial = doc.activeLayer;
        function rectangle (name, x, y, w, h, r, g, b, parent) {
            var layer = doc.artLayers.add(); layer.name = name;
            if (parent) layer.move(parent, ElementPlacement.INSIDE);
            doc.activeLayer = layer;
            doc.selection.select([[x,y], [x+w,y], [x+w,y+h], [x,y+h]]);
            var color = new SolidColor(); color.rgb.red=r; color.rgb.green=g; color.rgb.blue=b;
            doc.selection.fill(color); doc.selection.deselect(); return layer;
        }
        var locator = doc.layerSets.add(); locator.name = "定位组";
        rectangle("定位图层", 100,220,40,20,30,30,30,locator); locator.visible=false;
        rectangle("身体",150,130,100,120,40,160,220);
        initial.remove();
        var head = doc.layerSets.add(); head.name="头部组 [bone:head]";
        rectangle("头",160,70,80,60,240,180,70,head);
        rectangle("眼睛",180,90,10,10,255,255,255,head);
        var hidden=rectangle("隐藏参考",0,0,40,30,255,0,0); hidden.visible=false;
        doc.saveAs(new File(SOURCE_FILE),new PhotoshopSaveOptions(),true,Extension.LOWERCASE);
        return "OK";
    } finally {
        if (doc) doc.close(SaveOptions.DONOTSAVECHANGES);
        app.displayDialogs=oldDialogs; app.preferences.rulerUnits=oldUnits;
        if(previous) app.activeDocument=previous;
    }
})();
""".replace("SOURCE_FILE", json.dumps(str(cls.source).replace("\\", "/"), ensure_ascii=True))
        script.write_text(text, "utf-8-sig")
        try:
            core.export_photoshop(script)
        except Exception:
            cls.temporary.cleanup()
            raise
        cls.source_hash = hashlib.sha256(cls.source.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def tearDown(self):
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_hash)

    def export_json(self, **options):
        return core.convert(self.source, None, None, core.ExportOptions(**options),
                            log=lambda message: None, json_only=True)

    def test_chinese_names_draw_order_origin_and_pixels(self):
        plain = self.export_json()
        centered = self.export_json(bottom_layer_origin=True)
        data = json.loads(centered.read_text("utf-8"))
        self.assertEqual([slot["name"] for slot in data["slots"]], ["身体", "头", "眼睛"])
        self.assertEqual(data["bones"][1], {"name": "head", "parent": "root", "x": 65, "y": 135})
        body = data["skins"]["default"]["身体"]["身体"]
        self.assertEqual(body, {"x": 80, "y": 40, "width": 102, "height": 122})
        for image in (plain.parent / "images").glob("*.png"):
            with Image.open(image) as original, Image.open(centered.parent / "images" / image.name) as result:
                self.assertEqual(original.size, result.size)
                self.assertEqual(original.convert("RGBA").tobytes(), result.convert("RGBA").tobytes())

    def test_half_scale_uses_same_origin(self):
        path = self.export_json(scale=.5, bottom_layer_origin=True)
        data = json.loads(path.read_text("utf-8"))
        body = data["skins"]["default"]["身体"]["身体"]
        self.assertEqual(body, {"x": 40, "y": 20, "width": 52, "height": 62})

    def test_actual_spine_project_roundtrip_and_clean_output(self):
        spine = core.find_spine()
        if spine is None:
            self.skipTest("No Spine installation configured")
        project = core.convert(self.source, None, spine, core.ExportOptions(bottom_layer_origin=True),
                               log=lambda message: None)
        self.assertEqual({entry.name for entry in project.parent.iterdir()}, {self.source.stem + ".spine", "images"})
        settings = self.root / "roundtrip-settings.json"
        settings.write_text(json.dumps({"class": "export-json", "extension": ".json", "format": "JSON",
                                        "prettyPrint": True, "nonessential": True}), "utf-8")
        output = self.root / "roundtrip"
        completed = subprocess.run([str(spine), "-u", "3.8.99", "-i", str(project), "-o", str(output),
                                    "-e", str(settings)], capture_output=True, timeout=180,
                                   creationflags=core.CREATE_NO_WINDOW)
        self.assertEqual(completed.returncode, 0, "Spine project could not be reopened/exported")
        data = json.loads(next(output.glob("*.json")).read_text("utf-8-sig"))
        self.assertEqual(data["skeleton"]["spine"], "3.8.99")
        self.assertEqual(data["skeleton"]["images"], "./images/")
        self.assertEqual([slot["name"] for slot in data["slots"]], ["身体", "头", "眼睛"])


if __name__ == "__main__":
    unittest.main()
