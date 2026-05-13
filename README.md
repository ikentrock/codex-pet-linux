# Codex Pet for Linux

Run your [codex-pets.net](https://codex-pets.net) desktop companions on Ubuntu/GNOME.

Loads any `.codex-pet.zip` file and animates the sprite on your desktop — transparent, always-on-top, wandering around your screen.

## Requirements

- Ubuntu 20.04+ (or any Linux with GTK3 + a compositor)
- Python 3.10+
- `python3-gi` (GTK3 bindings)
- `python3-pil` (Pillow — WebP spritesheet loading)

> **Wayland note:** The app forces the X11 GDK backend (`GDK_BACKEND=x11`) so window positioning works correctly under XWayland. This is handled automatically — no extra configuration needed.

## Install

```bash
git clone https://github.com/ikentrock/codex-pet-linux
cd codex-pet-linux
./install.sh
```

Or manually:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-pil
mkdir -p ~/pets
cp desktop_pet.py ~/.local/bin/codex-pet
chmod +x ~/.local/bin/codex-pet
```

## Getting pets

Pets are loaded from two directories (both are optional):

| Directory | Notes |
|-----------|-------|
| `~/pets/` | Primary library |
| `~/.codex/pets/` | Secondary library (scanned if it exists) |

1. Download any `.codex-pet.zip` from [codex-pets.net](https://codex-pets.net)
2. Drop the file into `~/pets/`
3. It will appear automatically in the right-click menu

## Usage

```bash
# Launch with the first pet found in ~/pets/
codex-pet

# Launch a specific pet
codex-pet ~/pets/grogu-kid.codex-pet.zip

# Larger size (default scale is 0.5)
codex-pet --scale 0.75
```

## Controls

| Action | Result |
|--------|--------|
| **Left-click** | Trigger waving animation |
| **Left-drag** | Pick up and move the pet (plays jumping animation) |
| **Right-click** | Context menu |

### Context menu

- **Pet list** — switch instantly between all pets in your library
- **☑ Enable movement** — pet wanders around the screen using Run Right / Run Left animations
- **☑ Run on startup** — creates/removes `~/.config/autostart/codex-pet.desktop`
- **Quit**

## Autostart

Toggle **Run on startup** from the right-click menu, or create the entry manually:

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/codex-pet.desktop << EOF
[Desktop Entry]
Type=Application
Name=Codex Pet
Exec=codex-pet
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
```

## Pet format

The `.codex-pet.zip` format from codex-pets.net contains:

```
pet.json          # metadata: id, displayName, spritesheetPath
spritesheet.webp  # RGBA spritesheet: 192×208px tiles, 8 cols × 9 rows
```

| Row | Animation | When used |
|-----|-----------|-----------|
| 0 | Idle | Standing still |
| 1 | Run Right | Moving right |
| 2 | Run Left | Moving left |
| 3 | Waving | Left-click / drop |
| 4 | Jumping | Dragging |
| 5 | Failed | Sleeping (after 60 s idle) |
| 6 | Waiting | Moving vertically |
| 7 | Running | *(reserved)* |
| 8 | Review | Rare special event |

Blank frames at the end of each row are detected and skipped automatically.
