# GitHub Copilot Agent Instructions — InkyPi

These instructions help AI coding agents work productively in InkyPi.

## Big Picture Architecture
- **Server**: Flask app in [src/inkypi.py](src/inkypi.py) boots the web UI and background refresh.
- **Blueprints**: Routes live in [src/blueprints/main.py](src/blueprints/main.py), [src/blueprints/settings.py](src/blueprints/settings.py), [src/blueprints/plugin.py](src/blueprints/plugin.py), [src/blueprints/playlist.py](src/blueprints/playlist.py).
- **Config & State**: `Config` in [src/config.py](src/config.py) loads device config, plugin list, `PlaylistManager`, and `RefreshInfo` from JSON; writes back on changes.
- **Display**: `DisplayManager` in [src/display/display_manager.py](src/display/display_manager.py) selects hardware (`InkyDisplay`, `WaveshareDisplay`) or `MockDisplay` based on `display_type` and performs resize/orientation/enhancement before rendering.
- **Background Refresh**: `RefreshTask` in [src/refresh_task.py](src/refresh_task.py) runs periodically or on demand, picks next plugin via `PlaylistManager`, generates a PIL image, avoids redundant updates using image hashes, and pushes to the display.
- **Plugins**: Loaded via [src/plugins/plugin_registry.py](src/plugins/plugin_registry.py); each plugin subclass implements `generate_image()` and typically renders HTML → image via `BasePlugin.render_image()`.

## Developer Workflow (local, no hardware)
- Run dev server: `python src/inkypi.py --dev` (port 8080). See [docs/development.md](docs/development.md).
- Create venv: `python3 -m venv venv && source venv/bin/activate`.
- Install dev deps: `pip install -r install/requirements-dev.txt`.
- View at `http://localhost:8080`. Rendered output saved by `MockDisplay` to `mock_display_output/latest.png`.
- Edit dev config in [src/config/device_dev.json](src/config/device_dev.json).

## Rendering & Display Pipeline
- Plugins return a `PIL.Image` from `generate_image(settings, device_config)`.
- `DisplayManager.display_image(img, image_settings)` saves to [src/static/images/current_image.png](src/static/images/current_image.png), applies orientation (`horizontal`/`vertical` + optional inversion), resizes to device resolution, and applies per-device enhancements.
- In dev (`display_type=mock`), images are written to `mock_display_output/` by [src/display/mock_display.py](src/display/mock_display.py).
- HTML-based rendering uses Chromium headless: [src/utils/image_utils.py](src/utils/image_utils.py) (`chromium-headless-shell` required via Debian packages).

## Plugins: Structure & Conventions
- Plugin registry reads `plugin-info.json` in each plugin folder and imports `plugins.<id>.<id>`, then instantiates the class named in `plugin-info.json` (`class` field).
- Base class in [src/plugins/base_plugin/base_plugin.py](src/plugins/base_plugin/base_plugin.py):
  - `generate_settings_template()` returns template params (e.g., `settings_template`, `frame_styles`).
  - `render_image(dimensions, html_file, css_file, template_params)` renders Jinja2 templates using Base + plugin `render/` dirs, then screenshots to image.
- Example: [src/plugins/ai_text/ai_text.py](src/plugins/ai_text/ai_text.py) loads `OPEN_AI_SECRET` via `device_config.load_env_key()`, fetches text from OpenAI, and renders `ai_text.html` with `ai_text.css`.
- Plugin instance images are cached under [src/static/images/plugins](src/static/images/plugins) and reused when not scheduled for refresh.

## Configuration & Playlists
- Device config JSON: [src/config/device.json](src/config/device.json) (prod) and [src/config/device_dev.json](src/config/device_dev.json) (dev).
- Important keys: `resolution`, `orientation`, `inverted_image`, `image_settings` (`brightness`,`contrast`,`saturation`,`sharpness`), `plugin_cycle_interval_seconds`, `timezone`, `time_format`, `display_type`.
- `PlaylistManager` and `PluginInstance` in [src/model.py](src/model.py): time-based playlist selection, interval/scheduled refresh, rotation through `plugins` list, and cached `latest_refresh_time`.

## Web API/Blueprints Patterns
- `GET /` renders dashboard ([src/templates/inky.html](src/templates/inky.html)).
- `GET /settings` renders settings ([src/templates/settings.html](src/templates/settings.html)); `POST /save_settings` persists and wakes `RefreshTask` if interval changed.
- `GET /plugin/<plugin_id>` renders plugin config UI, pre-populates instance settings when `?instance=<name>`.
- `POST /update_now` triggers immediate manual update for a plugin (`ManualRefresh`) in dev if background thread not running.
- `POST /display_plugin_instance` forces display of a specific playlist instance (`PlaylistRefresh`).
- `GET /images/<plugin_id>/<filename>` serves plugin static assets safely from plugin folder.

## External Dependencies
- Runtime: Flask, Waitress, Pillow, Pytz, Psutil; device drivers (Inky, Waveshare). Headless rendering via `chromium-headless-shell`.
- AI integrations: `openai`, `google-genai`. API keys loaded through `.env` (see [src/config.py](src/config.py) `load_env_key`).
- Logs: `cysystemd` is optional; `download-logs` gracefully degrades in dev.

## Production (Raspberry Pi)
- Install script: [install/install.sh](install/install.sh) orchestrates system dependencies, venv, systemd service, and optional Waveshare driver download.
- Update/uninstall: [install/update.sh](install/update.sh), [install/uninstall.sh](install/uninstall.sh).
- Service file: [install/inkypi.service](install/inkypi.service); executable shim: [install/inkypi](install/inkypi).

## Agent Tips
- Prefer extending existing patterns (Blueprints, `BasePlugin`, Jinja2 render) rather than introducing new frameworks.
- Use `device_config.get_resolution()` and orientation to set render dimensions; vertical orientation swaps width/height.
- When adding a plugin: create `plugin-info.json`, module file matching folder name, subclass `BasePlugin`, optional `render/` with HTML/CSS.
- For headless HTML rendering, ensure `chromium-headless-shell` present; keep templates self-contained and performant.
