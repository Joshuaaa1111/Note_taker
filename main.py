import sys
import os
import gi

# Require GTK 4 and WebKitGTK 6.0
gi.require_version('Gtk', '4.0')
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk, Gdk, GLib, WebKit
import markdown


def md_to_html(md_text, scroll_pos=0):
    """Converts Markdown to HTML with Highlight.js syntax highlighting."""
    if not md_text:
        return ""

    raw_html = markdown.markdown(
        md_text, 
        extensions=['fenced_code', 'tables', 'extra', 'sane_lists']
    )

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <!-- Highlight.js CDN (Atom One Dark theme) -->
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
        <script>
            // Restore scroll position instantly on load
            window.addEventListener('DOMContentLoaded', () => {{
                hljs.highlightAll();
                window.scrollTo(0, {scroll_pos});
            }});
        </script>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                line-height: 1.6;
                padding: 15px;
                color: #e1e1e1;
                background-color: #1e1e1e;
            }}
            h1, h2, h3, h4, h5, h6 {{
                color: #3584e4;
                margin-top: 1em;
                margin-bottom: 0.5em;
            }}
            :not(pre) > code {{
                background-color: #2d2d2d;
                color: #e5a50a;
                padding: 2px 5px;
                border-radius: 4px;
                font-family: monospace;
            }}
            pre {{
                margin: 1em 0;
                border-radius: 6px;
                overflow: hidden;
            }}
            pre code.hljs {{
                padding: 12px;
                font-family: monospace;
                font-size: 13px;
            }}
            blockquote {{
                border-left: 4px solid #3584e4;
                margin: 0;
                padding-left: 10px;
                color: #9a9996;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
            }}
            th, td {{
                border: 1px solid #454545;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: #2d2d2d;
            }}
            a {{
                color: #62a0ea;
            }}
            hr {{
                border: none;
                border-top: 1px solid #454545;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        {raw_html}
    </body>
    </html>
    """
    return full_html


class NoteTaker(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.set_title("Markdown Note Taker (WebKit GTK4)")
        self.set_default_size(950, 600) 

        self.autosave_timeout_id = None
        self.loading_note = False
        
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.notes_folder = os.path.join(self.script_dir, "Notes")
        if not os.path.exists(self.notes_folder):
            os.makedirs(self.notes_folder)

        # Keyboard Shortcut Controller
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)

        # Main Outer Container
        self.base_layout = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        self.base_layout.set_margin_top(15)
        self.base_layout.set_margin_bottom(15)
        self.base_layout.set_margin_start(15)
        self.base_layout.set_margin_end(15)

        # 1. Sidebar Layout
        self.sidebar_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.sidebar_layout.set_size_request(200, -1)

        sidebar_title = Gtk.Label(label="<b>Your Notes (.md)</b>")
        sidebar_title.set_use_markup(True)
        sidebar_title.set_xalign(0.0)
        self.sidebar_layout.append(sidebar_title)

        self.list_scroll = Gtk.ScrolledWindow()
        self.list_scroll.set_vexpand(True)
        
        self.note_list_box = Gtk.ListBox()
        self.note_list_box.connect('row-selected', self.on_note_selected)
        
        self.list_scroll.set_child(self.note_list_box)
        self.sidebar_layout.append(self.list_scroll)
        
        self.new_note_btn = Gtk.Button(label="+ New Note")
        self.new_note_btn.connect('clicked', self.on_new_note_clicked)
        self.sidebar_layout.append(self.new_note_btn)

        self.base_layout.append(self.sidebar_layout)

        # 2. Right Panel Layout
        self.editor_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.editor_layout.set_hexpand(True)

        self.title_entry = Gtk.Entry()
        self.title_entry.set_placeholder_text("Enter note title here...")
        self.title_entry.connect('changed', self.reset_autosave_timer)
        self.editor_layout.append(self.title_entry)

        # 3. Paned Split View Setup
        self.content_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.content_paned.set_vexpand(True)
        self.content_paned.set_wide_handle(True)

        # Left Side: Text Editor Window
        self.scrolled_editor = Gtk.ScrolledWindow()
        self.scrolled_editor.set_hexpand(True)
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.get_buffer().connect('changed', self.on_text_changed)
        self.scrolled_editor.set_child(self.text_view)

        # Right Side: WebKit Renderer
        self.web_view = WebKit.WebView()
        self.web_view.set_hexpand(True)

        # Attach and lock dimensions
        self.content_paned.set_start_child(self.scrolled_editor)
        self.content_paned.set_end_child(self.web_view)
        self.content_paned.set_shrink_start_child(False)
        self.content_paned.set_shrink_end_child(False)
        self.content_paned.set_position(350)  # Forces middle split line

        self.editor_layout.append(self.content_paned)

        # Status Tracking Bar & Controls
        self.status_label = Gtk.Label(label="Ready to write.")
        self.status_label.set_xalign(0.0)
        self.editor_layout.append(self.status_label)

        self.btn_layout = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        self.save_button = Gtk.Button(label="Save Note (Ctrl+S)")
        self.save_button.connect('clicked', self.on_save_clicked)
        self.btn_layout.append(self.save_button)
        
        self.delete_button = Gtk.Button(label="Delete Note")
        self.delete_button.connect('clicked', self.on_delete_clicked)
        self.btn_layout.append(self.delete_button)
        
        self.editor_layout.append(self.btn_layout)
        self.base_layout.append(self.editor_layout)

        self.set_child(self.base_layout)
        self.refresh_note_list()

    def on_text_changed(self, buffer):
        self.reset_autosave_timer(buffer)
        
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        raw_text = buffer.get_text(start_iter, end_iter, True)
        
        # Get scroll position asynchronously from WebKit before reloading
        self.web_view.evaluate_javascript(
            "window.scrollY;", 
            -1, 
            None, 
            None, 
            None, 
            self._on_scroll_pos_retrieved, 
            raw_text
        )

    def on_key_pressed(self, controller, keyval, keycode, state):
        is_ctrl = (state & Gdk.ModifierType.CONTROL_MASK) != 0
        if is_ctrl:
            key_name = Gdk.keyval_name(keyval)
            if key_name == "s":
                self.on_save_clicked(None)
                return True
            elif key_name == "n":
                self.on_new_note_clicked(None)
                return True
        return False

    def _on_scroll_pos_retrieved(self, web_view, result, raw_text):
        try:
            js_value = web_view.evaluate_javascript_finish(result)
            scroll_pos = js_value.to_double() if js_value else 0
        except Exception:
            scroll_pos = 0
            
        html_content = md_to_html(raw_text, scroll_pos=scroll_pos)
        self.web_view.load_html(html_content, "file:///")

    def refresh_note_list(self, keep_selected_title=None):
        self.note_list_box.disconnect_by_func(self.on_note_selected)

        while True:
            row = self.note_list_box.get_row_at_index(0)
            if row is None:
                break
            self.note_list_box.remove(row)

        if os.path.exists(self.notes_folder):
            files = sorted([f for f in os.listdir(self.notes_folder) if f.endswith('.md')])
            target_row = None
            for filename in files:
                display_name = os.path.splitext(filename)[0]
                label = Gtk.Label(label=display_name)
                label.set_xalign(0.0)
                label.set_margin_start(5)
                label.set_margin_top(5)
                label.set_margin_bottom(5)
                
                row = Gtk.ListBoxRow()
                row.set_child(label)
                self.note_list_box.append(row)

                if keep_selected_title and display_name == keep_selected_title:
                    target_row = row

            if target_row:
                self.note_list_box.select_row(target_row)

        self.note_list_box.connect('row-selected', self.on_note_selected)

    def on_note_selected(self, listbox, row):
        if row is None:
            return
        
        label = row.get_child()
        note_title = label.get_text()
        file_path = os.path.join(self.notes_folder, f"{note_title}.md")

        if self.autosave_timeout_id:
            GLib.source_remove(self.autosave_timeout_id)
            self.autosave_timeout_id = None

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()

            self.loading_note = True
            self.title_entry.set_text(note_title)
            buffer = self.text_view.get_buffer()
            buffer.set_text(content)
            self.loading_note = False

            self.status_label.set_text(f"Loaded '{note_title}' successfully.")
        except Exception as e:
            self.loading_note = False
            self.status_label.set_text(f"Error loading file: {str(e)}")

    def on_save_clicked(self, button):
        title = self.title_entry.get_text().strip()
        if not title:
            title = "Untitled_Note"
            
        buffer = self.text_view.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        content = buffer.get_text(start_iter, end_iter, True)

        file_path = os.path.join(self.notes_folder, f"{title}.md")
        
        try:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)
            
            self.status_label.set_text(f"Saved successfully as '{title}.md'!")
            self.refresh_note_list(keep_selected_title=title)
        except Exception as e:
            self.status_label.set_text(f"Error saving file: {str(e)}")

    def on_new_note_clicked(self, button):
        if self.autosave_timeout_id:
            GLib.source_remove(self.autosave_timeout_id)
            self.autosave_timeout_id = None

        self.loading_note = True
        self.note_list_box.unselect_all()
        self.title_entry.set_text("")
        self.text_view.get_buffer().set_text("")
        self.web_view.load_html("", "file:///")
        self.loading_note = False
        self.status_label.set_text("New note ready.")

    def on_delete_clicked(self, button):
        title = self.title_entry.get_text().strip()
        if not title:
            self.status_label.set_text("No note selected to delete.")
            return

        file_path = os.path.join(self.notes_folder, f"{title}.md")

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                self.status_label.set_text(f"Deleted note '{title}.md' successfully.")
                
                self.loading_note = True
                self.title_entry.set_text("")
                self.text_view.get_buffer().set_text("")
                self.web_view.load_html("", "file:///")
                self.loading_note = False
                
                self.refresh_note_list()
            except Exception as e:
                self.status_label.set_text(f"Error deleting file: {str(e)}")
        else:
            self.status_label.set_text("File does not exist on disk.")

    def reset_autosave_timer(self, widget):
        if self.loading_note:
            return

        if self.autosave_timeout_id:
            GLib.source_remove(self.autosave_timeout_id)
        self.autosave_timeout_id = GLib.timeout_add(1000, self.trigger_autosave)

    def trigger_autosave(self):
        title = self.title_entry.get_text().strip()
        buffer = self.text_view.get_buffer()
        if not title and buffer.get_char_count() == 0:
            self.autosave_timeout_id = None
            return False

        self.on_save_clicked(None)
        self.status_label.set_text(f"Autosaved '{title or 'Untitled_Note'}'...")
        self.autosave_timeout_id = None
        return False


def on_activate(app):
    win = NoteTaker(application=app)
    win.present()

app = Gtk.Application(application_id='org.example.myapp')
app.connect('activate', on_activate)
sys.exit(app.run(sys.argv))