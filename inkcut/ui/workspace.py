"""
Copyright (c) 2017, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Jul 12, 2015

@author: jrm
"""
from __future__ import print_function

import os
import jsonpickle as pickle

from atom.api import Str, Value

#from enaml.qt.QtWidgets import QApplication
from enaml.widgets.api import Container
from enaml.workbench.ui.api import Workspace

import enaml
with enaml.imports():
    from inkcut.ui.manifest import UIManifest

from inkcut.core.utils import log
from enaml.qt.QtCore import QTimer

def debug_layout(node, level=0):
    if node is None:
        return

    indent = "  " * level

    print(
        "{}{} name={} position={} orientation={} sizes={}".format(
            indent,
            type(node).__name__,
            getattr(node, "name", None),
            getattr(node, "position", None),
            getattr(node, "orientation", None),
            getattr(node, "sizes", None)
        ),
        flush=True
    )

    children = getattr(node, "children", None)

    if callable(children):
        for child in children():
            debug_layout(child, level + 1)

class InkcutWorkspace(Workspace):
    """ A custom Workspace class for the crash course example.

    """
    #: Storage for the plugin manifest's id.
    _manifest_id = Str()
    #_save_on_exit = Value()
    _dock_area = Value()
    _save_on_closing = Value()

    def start(self):
        self.content = Container(padding=0)

        manifest = UIManifest()
        self._manifest_id = manifest.id
        self.workbench.register(manifest)

        self.workbench.get_plugin('inkcut.ui')
        self.load_area()


        # Test: opslaan voordat het hoofdvenster wordt vernietigd.
        from enaml.widgets.window import Window

        def save_on_closing(change):
            print(
                "INKCUT TEST: window closing, children =",
                self.content.children,
                flush=True
            )
            self.save_area()

        #for window in Window.windows:
        #    window.observe('closing', save_on_closing)
        print(
            "INKCUT TEST: aantal vensters tijdens start =",
            len(Window.windows),
            flush=True
        )

        for window in Window.windows:
            print("INKCUT TEST: gevonden venster =", window, flush=True)
            window.observe('closing', save_on_closing)
            print(
                "INKCUT TEST: closing observers =",
                window.has_observers('closing'),
                flush=True
            )

        self._save_on_closing = save_on_closing

    def stop(self):
        """ Stop the workspace instance.

        This method will unregister the workspace's plugin that was
        registered on start.

        """
        print("INKCUT TEST: workspace.stop() aangeroepen", flush=True)
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
            print("INKCUT TEST: LAYOUT BIJ AFSLUITEN", flush=True)
            debug_layout(layout)

            with open('inkcut.workspace.db', 'w', encoding='utf-8') as f:
                f.write(pickle.dumps(layout))

            print("INKCUT TEST: dock layout opgeslagen", flush=True)

        except Exception as e:
            log.warning("Error saving dock layout: {}".format(e))

    def load_area(self):
        """Create the dock area and restore the saved layout."""
        plugin = self.workbench.get_plugin("inkcut.ui")

        area = plugin.create_new_area()
        area.name = 'dock_area'
        area.set_parent(self.content)

        # Keep a reference for saving on exit.
        self._dock_area = area

        filename = 'inkcut.workspace.db'

        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    layout = pickle.loads(f.read())

                if layout is not None:
                    def restore_layout():
                        print("INKCUT TEST: GELADEN LAYOUT", flush=True)
                        debug_layout(layout)

                        area.apply_layout(layout)

                        print("INKCUT TEST: LAYOUT NA APPLY", flush=True)
                        debug_layout(area.save_layout())

                    QTimer.singleShot(0, restore_layout)

            except Exception as e:
                log.warning(
                    "Error restoring dock layout: {}".format(e)
                )