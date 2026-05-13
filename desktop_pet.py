#!/usr/bin/env python3
"""
Codex Pet — desktop companion for Ubuntu/GNOME.
Loads any .codex-pet.zip from ~/pets/ and animates the sprite on your desktop.

Usage:
  desktop_pet.py [pet.codex-pet.zip] [--scale 0.5]
  (no argument = first pet found in ~/pets/)

Controls:
  Left-click     Trigger action animation
  Left-drag      Pick up and move the pet (plays lift/drop animation)
  Right-click    Context menu: change pet · toggle movement · quit
"""

import gi, sys, os, io, json, math, random, time, tempfile, zipfile, shutil
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
import cairo
from PIL import Image

PETS_DIR       = os.path.expanduser("~/pets")
PETS_DIR_ALT   = os.path.expanduser("~/.codex/pets")
TILE_W, TILE_H = 192, 208
COLS, ROWS     = 8, 9

# (spritesheet_row, fps) — frame counts are detected per-pet at load time
ANIM_DEFS = {
    "idle":    (0, 6),
    "walk_r":  (1, 10),
    "walk_l":  (2, 10),
    "action":  (3, 8),
    "jump":    (4, 10),
    "sleep":   (5, 3),
    "walk_d":  (6, 10),
    "idle2":   (7, 6),
    "special": (8, 8),
}

WALK_SPEED  = 0.8   # px/tick at ~60 fps
SLEEP_AFTER = 60.0  # seconds idle before sleeping


# ── Helpers ───────────────────────────────────────────────────────────────────

def list_pets() -> list[str]:
    found = {}
    for d in (PETS_DIR, PETS_DIR_ALT):
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith(".codex-pet.zip"):
                    found.setdefault(f, os.path.join(d, f))
    return sorted(found.values(), key=os.path.basename)


def _count_frames(sheet: Image.Image, row: int) -> int:
    count = 0
    for col in range(COLS):
        tile = sheet.crop((col * TILE_W, row * TILE_H,
                           (col + 1) * TILE_W, (row + 1) * TILE_H))
        if max(px[3] for px in tile.getdata()) > 10:
            count = col + 1
        else:
            break
    return max(count, 1)


def _pil_to_pixbuf(img: Image.Image) -> GdkPixbuf.Pixbuf:
    img = img.convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    loader = GdkPixbuf.PixbufLoader.new_with_type("png")
    loader.write(buf.getvalue())
    loader.close()
    return loader.get_pixbuf()


def _load_pet(zip_path: str, scale: float):
    """Return (display_name, pixbufs[row][frame], anims{name:(row,nf,fps)})."""
    tmp = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        with open(os.path.join(tmp, "pet.json")) as f:
            meta = json.load(f)

        name  = meta.get("displayName", os.path.basename(zip_path))
        sheet = Image.open(
            os.path.join(tmp, meta.get("spritesheetPath", "spritesheet.webp"))
        ).convert("RGBA")

        tw, th     = int(TILE_W * scale), int(TILE_H * scale)
        row_frames = [_count_frames(sheet, r) for r in range(ROWS)]
        anims      = {
            aname: (row, row_frames[row], fps)
            for aname, (row, fps) in ANIM_DEFS.items()
        }
        pixbufs: list[list[GdkPixbuf.Pixbuf]] = []
        for row in range(ROWS):
            row_pbs = []
            for col in range(row_frames[row]):
                tile = sheet.crop((col * TILE_W, row * TILE_H,
                                   (col + 1) * TILE_W, (row + 1) * TILE_H))
                if scale != 1.0:
                    tile = tile.resize((tw, th), Image.LANCZOS)
                row_pbs.append(_pil_to_pixbuf(tile))
            pixbufs.append(row_pbs)

        return name, pixbufs, anims
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── Autostart ─────────────────────────────────────────────────────────────────

AUTOSTART_FILE = os.path.expanduser("~/.config/autostart/codex-pet.desktop")
_SCRIPT        = os.path.abspath(__file__)


def _autostart_enabled() -> bool:
    return os.path.isfile(AUTOSTART_FILE)


def _write_autostart(zip_path: str, scale: float):
    os.makedirs(os.path.dirname(AUTOSTART_FILE), exist_ok=True)
    exec_cmd = f"python3 {_SCRIPT} {zip_path} --scale {scale}"
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Codex Pet\n"
        f"Exec={exec_cmd}\n"
        "Hidden=false\n"
        "NoDisplay=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    with open(AUTOSTART_FILE, "w") as f:
        f.write(content)


def _remove_autostart():
    try:
        os.remove(AUTOSTART_FILE)
    except FileNotFoundError:
        pass


# ── Widget ────────────────────────────────────────────────────────────────────

class DesktopPet(Gtk.Window):
    def __init__(self, zip_path: str, scale: float = 0.5):
        super().__init__(title="DesktopPet")
        self._scale    = scale
        self._moving   = False
        self._zip_path = zip_path

        # ── Window (created once) ─────────────────────────────────
        screen = self.get_screen()
        vis = screen.get_rgba_visual()
        if vis:
            self.set_visual(vis)
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_resizable(False)

        monitor = screen.get_display().get_primary_monitor()
        if monitor:
            geo = monitor.get_geometry()
            self._sw, self._sh = geo.width, geo.height
        else:
            self._sw, self._sh = screen.get_width(), screen.get_height()

        self._tw = int(TILE_W * scale)
        self._th = int(TILE_H * scale)
        self._load(zip_path)

        self._x = float(self._sw - self._tw - 120)
        self._y = float(self._sh - self._th - 80)
        self.set_default_size(self._tw, self._th)
        self.move(int(self._x), int(self._y))

        # ── Animation state ───────────────────────────────────────
        self._anim    = "idle"
        self._fidx    = 0
        self._ftimer  = 0.0
        self._state   = "idle"
        self._stimer  = random.uniform(4.0, 8.0)
        self._target_x = self._x
        self._target_y = self._y
        self._last_interact = time.monotonic()

        # ── Drag state ────────────────────────────────────────────
        self._dragging    = False
        self._drag_root_x = 0.0
        self._drag_root_y = 0.0
        self._drag_win_x  = 0
        self._drag_win_y  = 0

        # ── Widgets ───────────────────────────────────────────────
        area = Gtk.DrawingArea()
        area.connect("draw", self._on_draw)
        self.add(area)

        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.connect("button-press-event",   self._on_press)
        self.connect("button-release-event", self._on_release)
        self.connect("motion-notify-event",  self._on_motion)
        self.connect("destroy", Gtk.main_quit)

        GLib.timeout_add(16, self._tick)
        self.show_all()

    # ── Pet loading ───────────────────────────────────────────────────────────

    def _load(self, zip_path: str):
        self._zip_path = zip_path
        self._name, self._pixbufs, self._anims = _load_pet(zip_path, self._scale)

    def _switch_pet(self, zip_path: str):
        self._load(zip_path)
        self._anim   = "idle"
        self._fidx   = 0
        self._ftimer = 0.0
        self._state  = "idle"
        self._stimer = random.uniform(4.0, 8.0)
        self.queue_draw()

    # ── Context menu ──────────────────────────────────────────────────────────

    def _show_menu(self, ev):
        menu = Gtk.Menu()

        pets = list_pets()
        if pets:
            pets_item = Gtk.MenuItem(label="Change pet")
            pets_sub  = Gtk.Menu()
            for path in pets:
                try:
                    with zipfile.ZipFile(path) as z:
                        label = json.loads(z.read("pet.json")).get(
                            "displayName",
                            os.path.basename(path).replace(".codex-pet.zip", "")
                        )
                except Exception:
                    label = os.path.basename(path).replace(".codex-pet.zip", "")
                item = Gtk.CheckMenuItem(label=("★ " if path == self._zip_path else "") + label)
                item.set_draw_as_radio(True)
                item.set_active(path == self._zip_path)
                item.connect("activate", lambda _, p=path: self._switch_pet(p))
                pets_sub.append(item)
            pets_item.set_submenu(pets_sub)
            menu.append(pets_item)
            menu.append(Gtk.SeparatorMenuItem())

        move_item = Gtk.CheckMenuItem(label="Enable movement")
        move_item.set_active(self._moving)
        move_item.connect("toggled", self._on_toggle_move)
        menu.append(move_item)

        startup_item = Gtk.CheckMenuItem(label="Run on startup")
        startup_item.set_active(_autostart_enabled())
        startup_item.connect("toggled", self._on_toggle_startup)
        menu.append(startup_item)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _: Gtk.main_quit())
        menu.append(quit_item)

        menu.show_all()
        menu.popup_at_pointer(ev)

    def _on_toggle_move(self, item):
        self._moving = item.get_active()
        if self._moving and self._state == "idle":
            self._enter("walking")
        elif not self._moving and self._state == "walking":
            self._enter("idle")

    def _on_toggle_startup(self, item):
        if item.get_active():
            _write_autostart(self._zip_path, self._scale)
        else:
            _remove_autostart()

    # ── Input ─────────────────────────────────────────────────────────────────

    def _on_press(self, _, ev):
        if ev.button == 3:
            self._show_menu(ev)
            return
        self._drag_root_x = ev.x_root
        self._drag_root_y = ev.y_root
        self._drag_win_x, self._drag_win_y = self.get_position()
        self._dragging = False

    def _on_release(self, _, ev):
        if ev.button != 1:
            return
        was_dragging   = self._dragging
        self._dragging = False
        self._last_interact = time.monotonic()
        # Drop or click → play action, then resume state machine
        self._enter("action")
        if was_dragging:
            # After landing, go idle (action's stimer will expire naturally)
            self._state = "action"

    def _on_motion(self, _, ev):
        if not (ev.state & Gdk.ModifierType.BUTTON1_MASK):
            return
        dx = ev.x_root - self._drag_root_x
        dy = ev.y_root - self._drag_root_y
        if abs(dx) > 4 or abs(dy) > 4:
            if not self._dragging:
                # Start of drag — switch to lift animation
                self._dragging = True
                self._anim     = "jump"
                self._fidx     = 0
                self._ftimer   = 0.0
            nx = int(self._drag_win_x + dx)
            ny = int(self._drag_win_y + dy)
            self._x, self._y = float(nx), float(ny)
            self.move(nx, ny)

    # ── State machine ─────────────────────────────────────────────────────────

    def _enter(self, state: str):
        self._state  = state
        self._fidx   = 0
        self._ftimer = 0.0

        if state == "idle":
            self._anim   = random.choice(["idle", "idle2"])
            self._stimer = random.uniform(4.0, 10.0)

        elif state == "walking":
            margin = 80
            self._target_x = random.uniform(margin, self._sw - self._tw - margin)
            self._target_y = random.uniform(margin, self._sh - self._th - margin)
            dx = self._target_x - self._x
            dy = self._target_y - self._y
            self._anim   = ("walk_r" if dx >= 0 else "walk_l") if abs(dx) >= abs(dy) else "walk_d"
            self._stimer = 999.0

        elif state == "sleeping":
            self._anim   = "sleep"
            self._stimer = random.uniform(10.0, 20.0)

        elif state == "action":
            self._anim   = "action"
            self._stimer = 2.0

        elif state == "jump":
            self._anim   = "jump"
            self._stimer = 1.5

        elif state == "special":
            self._anim   = "special"
            self._stimer = 2.5

    def _pick_next(self):
        if time.monotonic() - self._last_interact > SLEEP_AFTER:
            self._enter("sleeping")
            return
        r = random.random()
        if self._moving:
            # With movement: 55% walk, 35% idle, rest other
            if   r < 0.55: self._enter("walking")
            elif r < 0.90: self._enter("idle")
            elif r < 0.95: self._enter("action")
            elif r < 0.98: self._enter("jump")
            else:          self._enter("special")
        else:
            # Without movement: 90% idle, 10% other
            if   r < 0.90: self._enter("idle")
            elif r < 0.96: self._enter("action")
            elif r < 0.98: self._enter("jump")
            else:          self._enter("special")

    # ── Tick ──────────────────────────────────────────────────────────────────

    def _tick(self) -> bool:
        dt = 0.016

        # Always advance animation frame
        _, nf, fps = self._anims[self._anim]
        self._ftimer += dt
        if self._ftimer >= 1.0 / fps:
            self._ftimer = 0.0
            self._fidx   = (self._fidx + 1) % nf

        # Freeze state machine while being dragged
        if self._dragging:
            self.queue_draw()
            return True

        self._stimer -= dt

        if self._state == "walking":
            dx   = self._target_x - self._x
            dy   = self._target_y - self._y
            dist = math.hypot(dx, dy)
            if dist < WALK_SPEED * 2:
                self._enter("idle")
            else:
                self._x += dx / dist * WALK_SPEED
                self._y += dy / dist * WALK_SPEED
                self._x  = max(0.0, min(float(self._sw - self._tw), self._x))
                self._y  = max(0.0, min(float(self._sh - self._th), self._y))
                self.move(int(self._x), int(self._y))
        elif self._stimer <= 0:
            self._pick_next()

        self.queue_draw()
        return True

    # ── Draw ──────────────────────────────────────────────────────────────────

    def _on_draw(self, widget, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        row = self._anims[self._anim][0]
        Gdk.cairo_set_source_pixbuf(cr, self._pixbufs[row][self._fidx], 0, 0)
        cr.paint()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    args  = sys.argv[1:]
    scale = 0.5
    if "--scale" in args:
        try:
            scale = float(args[args.index("--scale") + 1])
        except (IndexError, ValueError):
            pass

    zip_path = next(
        (os.path.abspath(a) for a in args if a.endswith(".zip") and not a.startswith("--")),
        None
    )
    if not zip_path:
        pets = list_pets()
        if not pets:
            print(f"No .codex-pet.zip files found in {PETS_DIR}")
            print("Download pets from codex-pets.net and drop them into ~/pets/")
            sys.exit(1)
        zip_path = pets[0]

    if not os.path.exists(zip_path):
        print(f"File not found: {zip_path}")
        sys.exit(1)

    os.makedirs(PETS_DIR, exist_ok=True)
    DesktopPet(zip_path, scale=scale)
    Gtk.main()


if __name__ == "__main__":
    main()
