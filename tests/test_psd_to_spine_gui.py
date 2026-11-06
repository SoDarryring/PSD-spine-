from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from psd_to_spine_gui import App, window_bounds
import bundled_documents as documents


class WindowAndDropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = App()
        cls.app.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def test_help_viewer_displays_original_license_and_reuses_its_window(self):
        app = self.app
        app.show_help()
        first = app.help_window
        first.withdraw()
        app.show_help()
        self.assertIs(app.help_window, first)
        self.assertGreaterEqual(documents.verify_documents(), 6)
        for entry in app.help_entries:
            app.select_help_document(entry["title"])
            self.assertEqual(app.help_text.get("1.0", "end-1c"),
                             documents.read_document(entry).decode("utf-8-sig", errors="replace"))

    def test_startup_window_uses_large_screen_and_stays_in_work_area(self):
        for area, dpi in (((0, 0, 1920, 1040), 1), ((0, 0, 3840, 2080), 2),
                          ((-1920, 0, 0, 1040), 1.5), ((0, 0, 1366, 728), 1.25)):
            with self.subTest(area=area, dpi=dpi):
                width, height, x, y = window_bounds(area, dpi)
                self.assertGreaterEqual(x, area[0])
                self.assertGreaterEqual(y, area[1])
                self.assertLessEqual(x + width * dpi, area[2])
                self.assertLessEqual(y + height * dpi, area[3])
        self.assertEqual(window_bounds((0, 0, 1920, 1040), 1)[:2], (1280, 860))

    def test_native_drop_parses_multiple_chinese_paths_with_spaces_and_deduplicates(self):
        app = self.app
        with TemporaryDirectory() as folder:
            one, two = Path(folder) / "中文 设计.psd", Path(folder) / "第二个.psb"
            one.touch()
            two.touch()
            # Use the same Tcl list representation delivered by native tkdnd.
            data = app.tk.call("list", str(one), str(two), str(one))
            app.on_drop(SimpleNamespace(data=data))
            self.assertEqual(app.paths, [one.resolve(), two.resolve()])
            self.assertIsNone(app.output)
            self.assertEqual(app.count.get(), "2 个文件")
            self.assertTrue(app.TkdndVersion)


if __name__ == "__main__":
    unittest.main()
