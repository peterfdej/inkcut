
"""
Copyright (c) 2017, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Jul 12, 2015

@author: jrm
"""
from __future__ import print_function

import json
import os

import jsonpickle as pickle
from atom.api import Str, Value
from enaml.layout.geometry import Rect
from enaml.qt.QtCore import QTimer
from enaml.widgets.api import Container
from enaml.widgets.window import Window
from enaml.workbench.ui.api import Workspace

import enaml

with enaml.imports():
    from inkcut.ui.manifest import UIManifest

from inkcut.core.utils import log


class InkcutWorkspace(Workspace):
    """Inkcut workspace with persistent dock and window layouts."""

    _manifest_id = Str()
    _dock_area = Value()
    _save_on_closing = Value()

    def start(self):
        self.content = Container(padding=0)

        manifest = UIManifest()
        self._manifest_id = manifest.id
        self.workbench.register(manifest)

        self.workbench.get_plugin('inkcut.ui')
        self.load_area()

        def save_on_closing(change):
            for window in Window.windows:
                self.save_window(window)

            self.save_area()

        for window in Window.windows:
            window.observe('closing', save_on_closing)

            def restore_window(w=window):
                self.load_window(w)

            QTimer.singleShot(0, restore_window)

        # Keep the callback alive while the workspace is active.
        self._save_on_closing = save_on_closing

    def stop(self):
        """Stop the workspace and unregister its UI manifest."""
        self.save_area()
        self.workbench.unregister(self._manifest_id)

    def save_area(self):
        """Save the current dock layout."""
        log.debug("Saving dock layout")

        area = self._dock_area
        if area is None:
            log.warning("No dock area available to save")
            return

        try:
            layout = area.save_layout()

            with open('inkcut.workspace.db', 'w', encoding='utf-8') as f:
                f.write(pickle.dumps(layout))

        except Exception as e:
            log.warning("Error saving dock layout: {}".format(e))

    def load_area(self):
        """Create the dock area and restore its saved layout."""
        plugin = self.workbench.get_plugin('inkcut.ui')

        area = plugin.create_new_area()
        area.name = 'dock_area'
        area.set_parent(self.content)

        self._dock_area = area

        filename = 'inkcut.workspace.db'

        if not os.path.exists(filename):
            return

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                layout = pickle.loads(f.read())

            if layout is not None:
                def restore_layout():
                    try:
                        area.apply_layout(layout)
                    except Exception as e:
                        log.warning(
                            "Error applying dock layout: {}".format(e)
                        )

                QTimer.singleShot(0, restore_layout)

        except Exception as e:
            log.warning("Error restoring dock layout: {}".format(e))

    def save_window(self, window):
        """Save the normal window geometry and maximized state."""
        try:
            maximized = window.is_maximized()

            if maximized:
                # Qt remembers the normal geometry while maximized.
                qt_window = window.proxy.widget
                rect = qt_window.normalGeometry()

                data = {
                    'x': rect.x(),
                    'y': rect.y(),
                    'width': rect.width(),
                    'height': rect.height(),
                    'maximized': True,
                }
            else:
                rect = window.geometry()

                data = {
                    'x': rect.x,
                    'y': rect.y,
                    'width': rect.width,
                    'height': rect.height,
                    'maximized': False,
                }

            with open('inkcut.window.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            log.warning("Error saving window geometry: {}".format(e))

    def load_window(self, window):
        """Restore the saved window geometry and maximized state."""
        filename = 'inkcut.window.json'

        if not os.path.exists(filename):
            return

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            rect = Rect(
                data['x'],
                data['y'],
                data['width'],
                data['height']
            )

            window.set_geometry(rect)

            if data.get('maximized', False):
                window.maximize()

        except Exception as e:
            log.warning("Error restoring window geometry: {}".format(e))
