from __future__ import annotations

from focus.core import *  # noqa: F401,F403

class FocusCommandsWindow(Adw.ApplicationWindow):
    def __init__(self, app: Focus) -> None:
        super().__init__(application=app, title="D-Bus Commands")
        self.app = app
        self.set_default_size(900, 660)
        self.set_resizable(True)
        self._build_ui()

    def _build_ui(self) -> None:
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.set_title_widget(
            Adw.WindowTitle(title="D-Bus Commands", subtitle="Run or copy Focus actions")
        )
        view.add_top_bar(header)

        page = Adw.PreferencesPage()
        intro = Adw.PreferencesGroup(
            title="How to use",
            description=(
                "Use Run to trigger actions inside the open Focus window. "
                "Use Copy Command to place the GApplication call on your clipboard."
            ),
        )
        page.add(intro)

        for group_title, commands in FOCUS_COMMAND_GROUPS:
            group = Adw.PreferencesGroup(title=group_title)
            group.add_css_class("list-stack")
            page.add(group)
            for command in commands:
                group.add(self._build_command_row(command))

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(page)
        view.set_content(scroller)
        self.set_content(view)

    def _build_command_row(self, command: FocusCommand) -> Adw.ActionRow:
        row = Adw.ActionRow(
            title=command.title,
            subtitle=f"{command.accelerator} - {command.description}",
        )
        row.set_activatable(False)

        suffix = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        run_btn = Gtk.Button(label="Run")
        run_btn.add_css_class("suggested-action")
        run_btn.add_css_class("flat")
        run_btn.connect("clicked", self._on_run_clicked, command.action_name)
        suffix.append(run_btn)

        copy_btn = Gtk.Button(label="Copy Command")
        copy_btn.add_css_class("flat")
        copy_btn.add_css_class("link")
        copy_btn.connect("clicked", self._on_copy_clicked, command.action_name)
        suffix.append(copy_btn)

        row.add_suffix(suffix)
        return row

    def _on_run_clicked(self, _button: Gtk.Button, action_name: str) -> None:
        action = self.app.lookup_action(action_name)
        if action is None:
            self.app._transient_toast(f"Action not available: {action_name}", window=self)
            return
        self.app.activate_action(action_name, None)

    def _on_copy_clicked(self, _button: Gtk.Button, action_name: str) -> None:
        object_path = ACTION_OBJECT_PATH
        app_path = self.app.get_dbus_object_path()
        if app_path:
            object_path = app_path
        command = _action_command(action_name, object_path=object_path)
        display = Gdk.Display.get_default()
        if display:
            display.get_clipboard().set(command)
            self.app._transient_toast("Command copied to clipboard.", window=self)


