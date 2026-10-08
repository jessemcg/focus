"""Read-only native ABI/capability checks; importable without GTK installed."""
from __future__ import annotations

import subprocess


def check_native() -> dict:
    try:
        import gi
        for namespace, version in (("Gtk", "4.0"), ("Adw", "1"), ("Vte", "3.91"), ("GdkPixbuf", "2.0")):
            gi.require_version(namespace, version)
        from gi.repository import Gtk, Adw, Vte, GLib, GdkPixbuf
        versions = {"glib": (GLib.MAJOR_VERSION, GLib.MINOR_VERSION, GLib.MICRO_VERSION),
                    "gtk": (Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version()),
                    "adwaita": (Adw.get_major_version(), Adw.get_minor_version(), Adw.get_micro_version())}
        required = {"glib": (2, 80, 0), "gtk": (4, 12, 0), "adwaita": (1, 4, 0)}
        apis = (hasattr(Gtk, "FileDialog"), hasattr(Adw, "NavigationSplitView"),
                hasattr(Adw, "ToolbarView"), hasattr(Adw, "SpinRow"),
                hasattr(Adw, "SplitButton"), hasattr(Vte.Terminal, "spawn_async"))
        return {"ok": all(versions[k] >= v for k, v in required.items()) and all(apis),
                "versions": versions, "vte_namespace": "3.91", "apis": all(apis)}
    except (ImportError, ValueError, AttributeError) as exc:
        return {"ok": False, "error": str(exc)}
