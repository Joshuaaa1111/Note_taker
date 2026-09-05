import gi
import math
import random
# Enforce GTK 4.0 
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        # Give random initial vector velocity
        self.vx = random.uniform(-4, 4)
        self.vy = random.uniform(-8, -2)
        self.radius = random.uniform(3, 7)
        # Select from a modern neon cyberpunk palette
        self.color = random.choice([
            (0.0, 1.0, 0.8),  # Neon Cyan
            (1.0, 0.0, 0.5),  # Cyber Pink
            (0.6, 0.0, 1.0),  # Acid Purple
            (1.0, 0.8, 0.0)   # Laser Yellow
        ])
        self.alpha = 1.0

class ParticleSandbox(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_title("GTK4 Kinetic Quantum Sandbox")
        self.set_default_size(800, 600)

        # Simulation physics state variables
        self.particles = []
        self.gravity = 0.3
        self.bounce_friction = 0.75
        self.mouse_x = 0
        self.mouse_y = 0
        self.is_dragging = False

        # --- User Interface Layout Structure ---
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(main_box)

        # 1. Quantum Vector Drawing Canvas Frame
        self.canvas = Gtk.DrawingArea()
        self.canvas.set_vexpand(True)
        self.canvas.set_hexpand(True)
        # Setup modern GTK4 rendering hook
        self.canvas.set_draw_func(self.on_draw_canvas)
        main_box.append(self.canvas)

        # Add mouse/pointer gestures to canvas frame
        drag_gesture = Gtk.GestureDrag.new()
        drag_gesture.connect("drag-begin", self.on_drag_begin)
        drag_gesture.connect("drag-update", self.on_drag_update)
        drag_gesture.connect("drag-end", self.on_drag_end)
        self.canvas.add_controller(drag_gesture)

        # 2. Futuristic Control Dashboard Bottom Panel
        control_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        control_panel.set_margin_top(15)
        control_panel.set_margin_bottom(15)
        control_panel.set_margin_start(20)
        control_panel.set_margin_end(20)
        main_box.append(control_panel)

        # Gravity control system slider
        grav_label = Gtk.Label(label="Gravity Matrix:")
        control_panel.append(grav_label)
        
        # Scale range: 0.0 (Zero-G) to 1.5 (High Gravity)
        self.grav_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.5, 0.05)
        self.grav_slider.set_value(self.gravity)
        self.grav_slider.set_hexpand(True)
        self.grav_slider.connect("value-changed", self.on_gravity_changed)
        control_panel.append(self.grav_slider)

        # Action Trigger Buttons
        spawn_btn = Gtk.Button(label="💥 Burst 100 Particles")
        spawn_btn.connect("clicked", self.spawn_burst)
        control_panel.append(spawn_btn)

        clear_btn = Gtk.Button(label="🗑️ Wipe Field")
        clear_btn.connect("clicked", self.clear_field)
        control_panel.append(clear_btn)

        # Initialize thousands of initial test items
        self.generate_particles(400, 300, 150)

        # Start microsecond simulation graphics frame clock loop (60 FPS ~ 16ms updates)
        GLib.timeout_add(16, self.update_physics_loop)

    def generate_particles(self, x, y, count):
        for _ in range(count):
            self.particles.append(Particle(x, y))

    # --- Physics Engine & Framework Updates ---
    def update_physics_loop(self):
        width = self.canvas.get_width()
        height = self.canvas.get_height()

        # Handle mouse drag vortex forces
        if self.is_dragging:
            self.generate_particles(self.mouse_x, self.mouse_y, 4)

        for p in self.particles[:]:
            # Apply gravitational force configurations
            p.vy += self.gravity
            p.x += p.vx
            p.y += p.vy

            # Rigid bottom floor boundary calculations
            if p.y + p.radius > height:
                p.y = height - p.radius
                p.vy = -p.vy * self.bounce_friction
                # Introduce slight side rolling slide dispersion drag
                p.vx *= 0.98 

            # Left/Right wall bounce parameters
            if p.x - p.radius < 0:
                p.x = p.radius
                p.vx = -p.vx * self.bounce_friction
            elif p.x + p.radius > width:
                p.x = width - p.radius
                p.vx = -p.vx * self.bounce_friction

            # Gradually apply life fade out values to avoid GPU memory leakage
            p.alpha -= 0.002
            if p.alpha <= 0:
                self.particles.remove(p)

        # Request GTK canvas pipeline redrawing event immediately 
        self.canvas.queue_draw()
        return True

    # --- Cairo Canvas Graphics Draw Functions ---
    def on_draw_canvas(self, area, cr, width, height):  
        cr.set_source_rgb(0.05, 0.05, 0.08)
        cr.paint()

        # Render all vectors onto hardware frame buffers
        for p in self.particles:
            r, g, b = p.color
            cr.set_source_rgba(r, g, b, p.alpha)
            cr.arc(p.x, p.y, p.radius, 0, 2 * math.pi)
            cr.fill()

    # --- Mouse & Interaction Signal Events ---
    def on_drag_begin(self, gesture, start_x, start_y):
        self.is_dragging = True
        self.mouse_x = start_x
        self.mouse_y = start_y

    def on_drag_update(self, gesture, offset_x, offset_y):
        start_x, start_y = gesture.get_start_point()
        self.mouse_x = start_x + offset_x
        self.mouse_y = start_y + offset_y

    def on_drag_end(self, gesture, offset_x, offset_y):
        self.is_dragging = False

    def on_gravity_changed(self, scale):
        self.gravity = scale.get_value()

    def spawn_burst(self, button):
        width = max(self.canvas.get_width(), 100)
        height = max(self.canvas.get_height(), 100)
        self.generate_particles(width / 2, height / 3, 100)

    def clear_field(self, button):
        self.particles.clear()

class SandboxApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.quantum.sandbox")

    def do_activate(self):
        win = ParticleSandbox(application=self)
        win.present()

if __name__ == "__main__":
    app = SandboxApplication()
    app.run(None)
