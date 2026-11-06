from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import tkinter as tk
from tkinterdnd2 import DND_FILES, TkinterDnD

from psd_to_spine_gui import App, window_bounds
import bundled_documents as documents


class WindowAndDropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.drop_registrations = []
        register = TkinterDnD.DnDWrapper.drop_target_register

        def observe_register(widget, *types):
            cls.drop_registrations.append((widget, bool(widget._root().winfo_viewable())))
            return register(widget, *types)

        with patch.object(TkinterDnD.DnDWrapper, "drop_target_register", new=observe_register), \
                patch.object(tk.BaseWidget, "drop_target_register", new=observe_register), \
                TemporaryDirectory() as folder:
            initial = Path(folder) / "启动输入.psd"
            initial.touch()
            cls.app = App([initial])
            cls.before_map_registrations = list(cls.drop_registrations)
            cls.app.update()
            cls.app.remove_file(initial.resolve())
        cls.app.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def test_native_drop_registration_waits_for_first_visible_window(self):
        # Native OLE registration before first visibility reproduces the white
        # caption. Include startup inputs so their rows cannot register early.
        self.assertEqual(self.before_map_registrations, [])
        self.assertEqual(self.drop_registrations, [(self.app, True)])
        self.assertTrue(self.app._drop_registered)

    def test_native_drop_resolves_child_caption_to_registered_root(self):
        app = self.app
        types = app.tk.call("tkdnd::platform_specific_types", (DND_FILES,))
        target = app.tk.call("tkdnd::generic::FindWindowWithCommonTypes",
                             str(app.start_button._text_label), types)
        self.assertEqual(str(target[0]), str(app))

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
