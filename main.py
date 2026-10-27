import sys
import os
import gi
import shutil

# Require GTK 4 and WebKitGTK 6.0
gi.require_version('Gtk', '4.0')
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk, Gdk, GLib, WebKit
import markdown


def parse_frontmatter(content):
    """Parses YAML frontmatter and returns metadata dict and body text."""
    metadata = {"category": "General", "folder": "General", "priority": "Medium"}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            body = parts[2].strip()
            for line in fm_text.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    metadata[key.strip().lower()] = val.strip()
                    
    return metadata, body


def serialize_frontmatter(metadata, body):
    """Combines metadata dictionary and body text into frontmatter markdown format."""
    fm_text = "---\n"
    for key, val in metadata.items():
        fm_text += f"{key}: {val}\n"
    fm_text += "---\n\n"
    return fm_text + body


def md_to_html(md_text, scroll_pos=0):
    """Converts Markdown to HTML with Highlight.js syntax highlighting."""
    if not md_text:
        return ""

    _, body = parse_frontmatter(md_text)
    raw_html = markdown.markdown(
        body, 
        extensions=['fenced_code', 'tables', 'extra', 'sane_lists']
    )

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
        <script>
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
        
        self.set_title("Markdown Note Taker (Hierarchical Folders)")
        self.set_default_size(1100, 700) 

        self.autosave_timeout_id = None
        self.loading_note = False
        self.current_file_path = None  # Tracks open file for updates/moves
        
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.notes_folder = os.path.join(self.script_dir, "Sidebar")
        if not os.path.exists(self.notes_folder):
            os.makedirs(self.notes_folder)

        # Default initial category and folder structure
        self.ensure_default_structure()

        self.images_folder = os.path.join(self.notes_folder, "images")
        if not os.path.exists(self.images_folder):
            os.makedirs(self.images_folder)

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

        # -------------------------- Sidebar Layout (Tree Hierarchy)
        self.sidebar_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.sidebar_layout.set_size_request(240, -1)

        sidebar_title = Gtk.Label(label="<b>Categories & Folders</b>")
        sidebar_title.set_use_markup(True)
        sidebar_title.set_halign(0.0)
        self.sidebar_layout.append(sidebar_title)

        # Search
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search notes...")
        self.search_entry.connect('search-changed', self.on_search_changed)
        self.sidebar_layout.append(self.search_entry)

        # Tree Scroll Window
        self.tree_scroll = Gtk.ScrolledWindow()
        self.tree_scroll.set_vexpand(True)
        
        # Container holding category expanders
        self.sidebar_tree_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.tree_scroll.set_child(self.sidebar_tree_box)
        self.sidebar_layout.append(self.tree_scroll)
        
        # Action Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        
        self.new_cat_btn = Gtk.Button(label="+ Cat")
        self.new_cat_btn.set_tooltip_text("Create New Category")
        self.new_cat_btn.connect('clicked', self.on_new_category_clicked)
        btn_box.append(self.new_cat_btn)

        self.new_folder_btn = Gtk.Button(label="+ Folder")
        self.new_folder_btn.set_tooltip_text("Create New Folder")
        self.new_folder_btn.connect('clicked', self.on_new_folder_clicked)
        btn_box.append(self.new_folder_btn)

        self.new_note_btn = Gtk.Button(label="+ Note")
        self.new_note_btn.set_tooltip_text("Create New Note")
        self.new_note_btn.connect('clicked', self.on_new_note_clicked)
        btn_box.append(self.new_note_btn)

        self.sidebar_layout.append(btn_box)
        self.base_layout.append(self.sidebar_layout)

        # -------------------------- Right Panel Layout
        self.editor_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.editor_layout.set_hexpand(True)

        # Top Meta Bar (Title, Category, Folder, Priority)
        self.meta_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.title_entry = Gtk.Entry()
        self.title_entry.set_placeholder_text("Enter note title here...")
        self.title_entry.set_hexpand(True)
        self.title_entry.connect('changed', self.reset_autosave_timer)
        self.meta_bar.append(self.title_entry)

        # Category Dropdown
        cat_lbl = Gtk.Label(label="Cat:")
        self.meta_bar.append(cat_lbl)
        self.cat_dropdown = Gtk.DropDown()
        self.cat_dropdown.connect("notify::selected", self.on_meta_dropdown_changed)
        self.meta_bar.append(self.cat_dropdown)

        # Folder Dropdown
        folder_lbl = Gtk.Label(label="Folder:")
        self.meta_bar.append(folder_lbl)
        self.folder_dropdown = Gtk.DropDown()
        self.folder_dropdown.connect("notify::selected", self.reset_autosave_timer)
        self.meta_bar.append(self.folder_dropdown)

        # Priority Selector
        priority_lbl = Gtk.Label(label="Priority:")
        self.meta_bar.append(priority_lbl)
        self.priority_dropdown = Gtk.DropDown.new_from_strings(["High", "Medium", "Low"])
        self.priority_dropdown.set_selected(1)
        self.priority_dropdown.connect("notify::selected", self.reset_autosave_timer)
        self.meta_bar.append(self.priority_dropdown)

        self.editor_layout.append(self.meta_bar)

        # Paned Split View Setup
        self.content_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.content_paned.set_vexpand(True)
        self.content_paned.set_wide_handle(True)

        # Left Side: Text Editor Window
        self.scrolled_editor = Gtk.ScrolledWindow()
        self.scrolled_editor.set_hexpand(True)
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.get_buffer().connect('changed', self.on_text_changed)
        self.text_view.connect("paste-clipboard", self.on_paste_clipboard)
        
        self.scrolled_editor.set_child(self.text_view)

        # Right Side: WebKit Renderer
        self.web_view = WebKit.WebView()
        self.web_view.set_hexpand(True)

        self.content_paned.set_start_child(self.scrolled_editor)
        self.content_paned.set_end_child(self.web_view)
        self.content_paned.set_shrink_start_child(False)
        self.content_paned.set_shrink_end_child(False)
        self.content_paned.set_position(420)

        self.editor_layout.append(self.content_paned)

        # Status Tracking Bar & Controls
        self.status_label = Gtk.Label(label="Ready to write.")
        self.status_label.set_halign(0.0)
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
        self.refresh_sidebar()

    def ensure_default_structure(self):
        default_cat = os.path.join(self.notes_folder, "General")
        default_sub = os.path.join(default_cat, "Notes")
        if not os.path.exists(default_sub):
            os.makedirs(default_sub)

    def get_categories(self):
        if not os.path.exists(self.notes_folder):
            return ["General"]
        cats = [d for d in os.listdir(self.notes_folder) if os.path.isdir(os.path.join(self.notes_folder, d)) and d != "images"]
        return sorted(cats) if cats else ["General"]

    def get_folders_for_category(self, cat_name):
        cat_path = os.path.join(self.notes_folder, cat_name)
        if not os.path.exists(cat_path):
            return ["General"]
        folders = [d for d in os.listdir(cat_path) if os.path.isdir(os.path.join(cat_path, d))]
        return sorted(folders) if folders else ["General"]

    def update_cat_dropdown(self, selected_cat=None):
        cats = self.get_categories()
        
        # If no category was explicitly passed, remember the one currently selected
        if selected_cat is None:
            current_idx = self.cat_dropdown.get_selected()
            model = self.cat_dropdown.get_model()
            if model and current_idx < model.get_n_items():
                selected_cat = model.get_string(current_idx)

        self.cat_dropdown.set_model(Gtk.StringList.new(cats))
        
        if selected_cat in cats:
            idx = cats.index(selected_cat)
            self.cat_dropdown.set_selected(idx)
        else:
            self.cat_dropdown.set_selected(0)
        
        self.update_folder_dropdown()

    def update_folder_dropdown(self, selected_folder=None):
        cat_idx = self.cat_dropdown.get_selected()
        model = self.cat_dropdown.get_model()
        if not model or cat_idx >= model.get_n_items():
            return
        cat_name = model.get_string(cat_idx)
        folders = self.get_folders_for_category(cat_name)
        
        # If no folder was explicitly passed, preserve the currently selected one if it exists in the new list
        if selected_folder is None:
            curr_idx = self.folder_dropdown.get_selected()
            curr_model = self.folder_dropdown.get_model()
            if curr_model and curr_idx < curr_model.get_n_items():
                candidate = curr_model.get_string(curr_idx)
                if candidate in folders:
                    selected_folder = candidate

        self.folder_dropdown.set_model(Gtk.StringList.new(folders))
        
        if selected_folder in folders:
            idx = folders.index(selected_folder)
            self.folder_dropdown.set_selected(idx)
        else:
            self.folder_dropdown.set_selected(0)

    def on_meta_dropdown_changed(self, dropdown, pspec):
        self.update_folder_dropdown()

    def refresh_sidebar(self, keep_selected_path=None):
        # Clear sidebar tree box
        while True:
            child = self.sidebar_tree_box.get_first_child()
            if child is None:
                break
            self.sidebar_tree_box.remove(child)

        query = self.search_entry.get_text().strip().lower()

        categories = self.get_categories()
        for cat in categories:
            cat_path = os.path.join(self.notes_folder, cat)
            if not os.path.exists(cat_path):
                continue

            cat_expander = Gtk.Expander(label=f"📁 {cat}")
            cat_expander.set_expanded(True)

            # Add right-click context menu for Category
            cat_click = Gtk.GestureClick(button=3)
            cat_click.connect("pressed", lambda g, n, x, y, c=cat: self.on_category_right_click(x, y, c))
            cat_expander.add_controller(cat_click)

            cat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            cat_box.set_margin_start(14)

            folders = self.get_folders_for_category(cat)
            has_matching_content = False

            for folder in folders:
                folder_path = os.path.join(cat_path, folder)
                if not os.path.exists(folder_path):
                    continue

                folder_expander = Gtk.Expander(label=f"📂 {folder}")
                folder_expander.set_expanded(True)

                # Add right-click context menu for Folder
                folder_click = Gtk.GestureClick(button=3)
                folder_click.connect("pressed", lambda g, n, x, y, c=cat, f=folder: self.on_folder_right_click(x, y, c, f))
                folder_expander.add_controller(folder_click)

                note_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                note_box.set_margin_start(14)

                files = [f for f in os.listdir(folder_path) if f.endswith('.md')]
                folder_has_notes = False

                note_items = []
                for filename in files:
                    file_path = os.path.join(folder_path, filename)
                    display_name = os.path.splitext(filename)[0]

                    priority = "Medium"
                    body_content = ""
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            meta, body_content = parse_frontmatter(f.read())
                            priority = meta.get("priority", "Medium")
                    except Exception:
                        pass

                    # Assign weight: High (0), Medium (1), Low (2)
                    p_lower = priority.lower()
                    if p_lower == "high":
                        weight = 0
                    elif p_lower == "low":
                        weight = 2
                    else:
                        weight = 1

                    note_items.append({
                        "weight": weight,
                        "display_name": display_name,
                        "file_path": file_path,
                        "priority": priority,
                        "body_content": body_content
                    })

                # Sort by priority weight (High -> Medium -> Low), then alphabetically by name for ties
                note_items.sort(key=lambda x: (x["weight"], x["display_name"].lower()))

                for item in note_items:
                    display_name = item["display_name"]
                    file_path = item["file_path"]
                    priority = item["priority"]
                    body_content = item["body_content"]

                    # Search filtering
                    if query and query not in display_name.lower() and query not in body_content.lower():
                        continue

                    badge = "🟡"
                    if priority.lower() == "high":
                        badge = "🔴"
                    elif priority.lower() == "low":
                        badge = "🟢"

                    note_btn = Gtk.Button(label=f"{badge} {display_name}")
                    note_btn.set_has_frame(False)
                    note_btn.set_halign(Gtk.Align.START)
                    note_btn.file_path = file_path
                    note_btn.connect('clicked', self.on_sidebar_note_clicked)
                    
                    if keep_selected_path and file_path == keep_selected_path:
                        note_btn.add_css_class("suggested-action")

                    note_box.append(note_btn)
                    folder_has_notes = True
                    has_matching_content = True

                folder_expander.set_child(note_box)
                if folder_has_notes or not query:
                    cat_box.append(folder_expander)

            cat_expander.set_child(cat_box)
            if has_matching_content or not query:
                self.sidebar_tree_box.append(cat_expander)

        self.update_cat_dropdown()
        
    def on_sidebar_note_clicked(self, button):
        file_path = getattr(button, 'file_path', None)
        if not file_path or not os.path.exists(file_path):
            return

        if self.autosave_timeout_id:
            GLib.source_remove(self.autosave_timeout_id)
            self.autosave_timeout_id = None

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                raw_content = file.read()

            metadata, body = parse_frontmatter(raw_content)
            note_title = os.path.splitext(os.path.basename(file_path))[0]

            self.loading_note = True
            self.current_file_path = file_path
            self.title_entry.set_text(note_title)
            
            cat = metadata.get("category", "General")
            folder = metadata.get("folder", "General")
            priority = metadata.get("priority", "Medium")

            self.update_cat_dropdown(cat)
            self.update_folder_dropdown(folder)
            
            model = self.priority_dropdown.get_model()
            for i in range(model.get_n_items()):
                if model.get_string(i).lower() == priority.lower():
                    self.priority_dropdown.set_selected(i)
                    break

            buffer = self.text_view.get_buffer()
            buffer.set_text(body)
            self.loading_note = False

            self.status_label.set_text(f"Loaded '{note_title}' successfully.")
            self.refresh_sidebar(keep_selected_path=file_path)
        except Exception as e:
            self.loading_note = False
            self.status_label.set_text(f"Error loading file: {str(e)}")

    def on_new_category_clicked(self, button):
        dialog = Gtk.Dialog(title="New Category", transient_for=self, modal=True)
        dialog.set_default_size(300, 120)
        
        content_area = dialog.get_content_area()
        content_area.set_margin_top(15)
        content_area.set_margin_bottom(15)
        content_area.set_margin_start(15)
        content_area.set_margin_end(15)
        
        entry = Gtk.Entry()
        entry.set_placeholder_text("Category name...")
        content_area.append(entry)
        
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Create", Gtk.ResponseType.OK)
        
        def on_response(dlg, response_id):
            if response_id == Gtk.ResponseType.OK:
                cat_name = entry.get_text().strip()
                if cat_name:
                    new_path = os.path.join(self.notes_folder, cat_name, "General")
                    os.makedirs(new_path, exist_ok=True)
                    self.refresh_sidebar()
                    self.status_label.set_text(f"Created category '{cat_name}'.")
            dlg.destroy()

        dialog.connect("response", on_response)
        dialog.present()

    def on_new_folder_clicked(self, button):
        cats = self.get_categories()
        dialog = Gtk.Dialog(title="New Folder", transient_for=self, modal=True)
        dialog.set_default_size(320, 160)
        
        content_area = dialog.get_content_area()
        content_area.set_margin_top(15)
        content_area.set_margin_bottom(15)
        content_area.set_margin_start(15)
        content_area.set_margin_end(15)
        
        content_area.append(Gtk.Label(label="Select Category:"))
        cat_dropdown = Gtk.DropDown.new_from_strings(cats)
        content_area.append(cat_dropdown)
        
        content_area.append(Gtk.Label(label="Folder Name:"))
        entry = Gtk.Entry()
        entry.set_placeholder_text("Folder name...")
        content_area.append(entry)
        
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Create", Gtk.ResponseType.OK)
        
        def on_response(dlg, response_id):
            if response_id == Gtk.ResponseType.OK:
                folder_name = entry.get_text().strip()
                model = cat_dropdown.get_model()
                selected_idx = cat_dropdown.get_selected()
                if folder_name and model and selected_idx < model.get_n_items():
                    cat_name = model.get_string(selected_idx)
                    folder_path = os.path.join(self.notes_folder, cat_name, folder_name)
                    os.makedirs(folder_path, exist_ok=True)
                    self.refresh_sidebar()
                    self.status_label.set_text(f"Created folder '{folder_name}' in [{cat_name}].")
            dlg.destroy()

        dialog.connect("response", on_response)
        dialog.present()

    def on_save_clicked(self, button):
        title = self.title_entry.get_text().strip()
        if not title:
            title = "Untitled_Note"
            
        cat_idx = self.cat_dropdown.get_selected()
        cat_model = self.cat_dropdown.get_model()
        category = cat_model.get_string(cat_idx) if cat_model and cat_idx < cat_model.get_n_items() else "General"

        folder_idx = self.folder_dropdown.get_selected()
        folder_model = self.folder_dropdown.get_model()
        folder = folder_model.get_string(folder_idx) if folder_model and folder_idx < folder_model.get_n_items() else "General"

        priority_idx = self.priority_dropdown.get_selected()
        priority_model = self.priority_dropdown.get_model()
        priority = priority_model.get_string(priority_idx) if priority_model and priority_idx < priority_model.get_n_items() else "Medium"

        target_dir = os.path.join(self.notes_folder, category, folder)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        buffer = self.text_view.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        body_content = buffer.get_text(start_iter, end_iter, True)

        metadata = {
            "category": category,
            "folder": folder,
            "priority": priority
        }
        
        full_content = serialize_frontmatter(metadata, body_content)
        new_file_path = os.path.join(target_dir, f"{title}.md")
        
        try:
            # If path changed (e.g., moved category/folder or renamed), remove old file
            if self.current_file_path and self.current_file_path != new_file_path:
                if os.path.exists(self.current_file_path):
                    os.remove(self.current_file_path)

            with open(new_file_path, "w", encoding="utf-8") as file:
                file.write(full_content)
            
            self.current_file_path = new_file_path
            self.status_label.set_text(f"Saved successfully as '{title}.md' [{category} / {folder}]!")
            self.refresh_sidebar(keep_selected_path=new_file_path)
        except Exception as e:
            self.status_label.set_text(f"Error saving file: {str(e)}")

    def on_new_note_clicked(self, button):
        if self.autosave_timeout_id:
            GLib.source_remove(self.autosave_timeout_id)
            self.autosave_timeout_id = None

        self.loading_note = True
        self.current_file_path = None
        self.title_entry.set_text("")
        self.text_view.get_buffer().set_text("")
        base_uri = f"file://{self.notes_folder}/"
        self.web_view.load_html("", base_uri)
        self.loading_note = False
        self.status_label.set_text("New note ready.")
        self.refresh_sidebar()

    def on_delete_clicked(self, button):
        if not self.current_file_path or not os.path.exists(self.current_file_path):
            self.status_label.set_text("No note selected to delete.")
            return

        try:
            os.remove(self.current_file_path)
            self.status_label.set_text("Deleted note successfully.")
            
            self.loading_note = True
            self.current_file_path = None
            self.title_entry.set_text("")
            self.text_view.get_buffer().set_text("")
            base_uri = f"file://{self.notes_folder}/"
            self.web_view.load_html("", base_uri)
            self.loading_note = False
            
            self.refresh_sidebar()
        except Exception as e:
            self.status_label.set_text(f"Error deleting file: {str(e)}")

    def reset_autosave_timer(self, widget, *args):
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

        self.on_save_silent()
        self.autosave_timeout_id = None
        return False

    def on_save_silent(self):
        """Saves content without resetting the sidebar UI tree (prevents typing glitches)."""
        title = self.title_entry.get_text().strip()
        if not title:
            title = "Untitled_Note"
            
        cat_idx = self.cat_dropdown.get_selected()
        cat_model = self.cat_dropdown.get_model()
        category = cat_model.get_string(cat_idx) if cat_model and cat_idx < cat_model.get_n_items() else "General"

        folder_idx = self.folder_dropdown.get_selected()
        folder_model = self.folder_dropdown.get_model()
        folder = folder_model.get_string(folder_idx) if folder_model and folder_idx < folder_model.get_n_items() else "General"

        priority_idx = self.priority_dropdown.get_selected()
        priority_model = self.priority_dropdown.get_model()
        priority = priority_model.get_string(priority_idx) if priority_model and priority_idx < priority_model.get_n_items() else "Medium"

        target_dir = os.path.join(self.notes_folder, category, folder)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        buffer = self.text_view.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        body_content = buffer.get_text(start_iter, end_iter, True)

        metadata = {"category": category, "folder": folder, "priority": priority}
        full_content = serialize_frontmatter(metadata, body_content)
        new_file_path = os.path.join(target_dir, f"{title}.md")
        
        try:
            if self.current_file_path and self.current_file_path != new_file_path:
                if os.path.exists(self.current_file_path):
                    os.remove(self.current_file_path)

            with open(new_file_path, "w", encoding="utf-8") as file:
                file.write(full_content)
            
            self.current_file_path = new_file_path
            self.status_label.set_text(f"Autosaved '{title}'...")
        except Exception as e:
            self.status_label.set_text(f"Error autosaving: {str(e)}")

    def on_search_changed(self, search_entry):
        if self.loading_note:
            return
        self.refresh_sidebar()

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

    def on_text_changed(self, buffer):
        self.reset_autosave_timer(buffer)
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        raw_text = buffer.get_text(start_iter, end_iter, True)
        
        self.web_view.evaluate_javascript(
            "window.scrollY;", -1, None, None, None, 
            self._on_scroll_pos_retrieved, raw_text
        )

    def _on_scroll_pos_retrieved(self, web_view, result, raw_text):
        try:
            js_value = web_view.evaluate_javascript_finish(result)
            scroll_pos = js_value.to_double() if js_value else 0
        except Exception:
            scroll_pos = 0
            
        html_content = md_to_html(raw_text, scroll_pos=scroll_pos)
        base_uri = f"file://{self.notes_folder}/"
        self.web_view.load_html(html_content, base_uri)

    def on_paste_clipboard(self, text_view):
        display = Gdk.Display.get_default()
        if not display:
            return False

        clipboard = display.get_clipboard()
        formats = clipboard.get_formats()
        
        has_image = False
        if formats:
            if formats.contain_gtype(Gdk.Texture.__gtype__):
                has_image = True
            else:
                for mime in formats.get_mime_types():
                    if mime.startswith("image/"):
                        has_image = True
                        break

        if has_image:
            clipboard.read_texture_async(None, self._on_texture_read_finish, None)
            return True

        return False

    def _on_texture_read_finish(self, clipboard, result, user_data):
        try:
            texture = clipboard.read_texture_finish(result)
            if isinstance(texture, Gdk.Texture):
                import time
                filename = f"img_{int(time.time() * 1000)}.png"
                file_path = os.path.join(self.images_folder, filename)
                
                success = texture.save_to_png(file_path)
                if success:
                    relative_path = f"images/{filename}"
                    markdown_syntax = f"\n![Pasted Image]({relative_path})\n"
                    
                    buffer = self.text_view.get_buffer()
                    if buffer.get_has_selection():
                        buffer.delete_selection(True, self.text_view.get_editable())
                    
                    cursor_iter = buffer.get_iter_at_mark(buffer.get_insert())
                    buffer.insert(cursor_iter, markdown_syntax)
                    
                    self.status_label.set_text(f"Pasted image successfully: {relative_path}")
        except Exception as e:
            self.status_label.set_text(f"Paste image error: {str(e)}")

    def on_category_right_click(self, x, y, category_name):
        """Shows a context menu when right-clicking a category."""
        menu = Gtk.PopoverMenu()
        
        # Create a simple box with a delete button inside the popover
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        
        del_btn = Gtk.Button(label=f"Delete Category '{category_name}'")
        del_btn.add_css_class("error") # GTK error styling (usually red)
        del_btn.connect("clicked", lambda b: (menu.popdown(), self.confirm_delete_category(category_name)))
        box.append(del_btn)
        
        menu.set_child(box)
        menu.set_pointing_to(None)
        
        # Attach menu to main window or widget popup
        menu.set_parent(self.sidebar_tree_box)
        menu.popup()

    def on_folder_right_click(self, x, y, category_name, folder_name):
        """Shows a context menu when right-clicking a subfolder."""
        menu = Gtk.PopoverMenu()
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        
        del_btn = Gtk.Button(label=f"Delete Folder '{folder_name}'")
        del_btn.add_css_class("error")
        del_btn.connect("clicked", lambda b: (menu.popdown(), self.confirm_delete_folder(category_name, folder_name)))
        box.append(del_btn)
        
        menu.set_child(box)
        menu.set_parent(self.sidebar_tree_box)
        menu.popup()

    def confirm_delete_category(self, category_name):
        """Confirmation dialog before deleting an entire category."""
        dialog = Gtk.Dialog(title="Delete Category?", transient_for=self, modal=True)
        dialog.set_default_size(320, 140)
        
        content = dialog.get_content_area()
        content.set_margin_top(15)
        content.set_margin_start(15)
        content.set_margin_end(15)
        content.append(Gtk.Label(label=f"Are you sure you want to delete category '{category_name}'?\nThis will delete ALL folders and notes inside it!"))
        
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Delete", Gtk.ResponseType.OK)
        
        def on_response(dlg, response_id):
            if response_id == Gtk.ResponseType.OK:
                cat_path = os.path.join(self.notes_folder, category_name)
                if os.path.exists(cat_path):
                    try:
                        shutil.rmtree(cat_path)
                        self.status_label.set_text(f"Deleted category '{category_name}'.")
                        # Clear editor if current note was in this category
                        if self.current_file_path and category_name in self.current_file_path:
                            self.current_file_path = None
                            self.title_entry.set_text("")
                            self.text_view.get_buffer().set_text("")
                            self.web_view.load_html("", f"file://{self.notes_folder}/")
                        self.refresh_sidebar()
                    except Exception as e:
                        self.status_label.set_text(f"Error deleting category: {str(e)}")
            dlg.destroy()

        dialog.connect("response", on_response)
        dialog.present()

    def confirm_delete_folder(self, category_name, folder_name):
        """Confirmation dialog before deleting a folder."""
        dialog = Gtk.Dialog(title="Delete Folder?", transient_for=self, modal=True)
        dialog.set_default_size(320, 140)
        
        content = dialog.get_content_area()
        content.set_margin_top(15)
        content.set_margin_start(15)
        content.set_margin_end(15)
        content.append(Gtk.Label(label=f"Are you sure you want to delete folder '{folder_name}'?\nThis will delete ALL notes inside it!"))
        
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Delete", Gtk.ResponseType.OK)
        
        def on_response(dlg, response_id):
            if response_id == Gtk.ResponseType.OK:
                folder_path = os.path.join(self.notes_folder, category_name, folder_name)
                if os.path.exists(folder_path):
                    try:
                        shutil.rmtree(folder_path)
                        self.status_label.set_text(f"Deleted folder '{folder_name}'.")
                        if self.current_file_path and folder_name in self.current_file_path:
                            self.current_file_path = None
                            self.title_entry.set_text("")
                            self.text_view.get_buffer().set_text("")
                            self.web_view.load_html("", f"file://{self.notes_folder}/")
                        self.refresh_sidebar()
                    except Exception as e:
                        self.status_label.set_text(f"Error deleting folder: {str(e)}")
            dlg.destroy()

        dialog.connect("response", on_response)
        dialog.present()


def on_activate(app):
    win = NoteTaker(application=app)
    win.present()


app = Gtk.Application(application_id='org.example.noteapp')
app.connect('activate', on_activate)
sys.exit(app.run(sys.argv))