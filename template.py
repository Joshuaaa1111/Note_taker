import sys
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 1. WINDOW SETUP
        self.set_title("My App Template")
        self.set_default_size(600, 400)
        
        # 2. LAYOUT CONTAINER (Holds multiple widgets)
        # Gtk.Orientation.VERTICAL stacks items top-to-bottom. Spacing is 10 pixels.
        self.main_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_layout.set_margin_top(15)
        self.main_layout.set_margin_bottom(15)
        self.main_layout.set_margin_start(15)
        self.main_layout.set_margin_end(15)
        
        # 3. ADD YOUR WIDGETS HERE
        # (This is where your actual app UI logic goes)
        
        # 4. ATTACH LAYOUT TO WINDOW
        self.set_child(self.main_layout)


def on_activate(app):
    # This function triggers when the OS tells the app to start
    win = MainWindow(application=app)
    win.present()


# 5. OS LIFECYCLE ENGINE
# Change 'com.yourname.appname' to a unique reverse-domain name
app = Gtk.Application(application_id='com.yourname.appname')
app.connect('activate', on_activate)

# Starts the loop and safely returns the exit code to the terminal when closed
sys.exit(app.run(sys.argv))
