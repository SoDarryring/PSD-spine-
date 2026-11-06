from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from psd_to_spine_gui import App, window_bounds


class WindowAndDropTests(unittest.TestCase):
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
        app = App()
        app.withdraw()
        try:
            with TemporaryDirectory() as folder:
                one, two = Path(folder) / "中文 设计.psd", Path(folder) / "第二个.psb"
                one.touch()
                two.touch()
                # Use the same Tcl list representation delivered by native tkdnd.
                data = app.tk.call("list", str(one), str(two), str(one))
                app.on_drop(SimpleNamespace(data=data))
                self.assertEqual(app.paths, [one, two])
                self.assertIsNone(app.output)
                self.assertEqual(app.count.get(), "2 个文件")
                self.assertTrue(app.TkdndVersion)
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
