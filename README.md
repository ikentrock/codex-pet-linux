# Codex Pet for Linux

Run your [codex-pets.net](https://codex-pets.net) desktop companions on Ubuntu/GNOME.

Loads any `.codex-pet.zip` file and animates the sprite on your desktop — transparent, always-on-top, wandering around your screen.

![Grogu demo](https://raw.githubusercontent.com/luisenramos/codex-pet-linux/main/screenshot.png)

## Requirements

- Ubuntu 20.04+ (or any Linux with GTK3 + a compositor)
- Python 3.10+
- `python3-gi` (GTK3 bindings)
- `python3-pil` (Pillow — WebP spritesheet loading)

## Install

```bash
git clone https://github.com/luisenramos/codex-pet-linux
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

1. Download any `.codex-pet.zip` from [codex-pets.net](https://codex-pets.net)
2. Drop the file into `~/pets/`
3. It will appear automatically in the **Change pet** menu

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
| **Left-click** | Trigger action animation |
| **Left-drag** | Pick up and move the pet (plays lift/drop animation) |
| **Right-click** | Context menu |

### Context menu

- **Change pet** — switch between all pets in `~/pets/` instantly
- **Enable movement** — when checked, the pet wanders slowly around your screen
- **Quit**

## Autostart

To launch automatically on login:

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

| Row | Animation |
|-----|-----------|
| 0 | Idle |
| 1 | Walk right |
| 2 | Walk left |
| 3 | Action |
| 4 | Jump / lifted |
| 5 | Sleep |
| 6 | Walk down |
| 7 | Idle variant |
| 8 | Special |

Blank frames at the end of each row are detected and skipped automatically.
