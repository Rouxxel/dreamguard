# Vendored model: i2rt YAM

- Source: https://github.com/google-deepmind/mujoco_menagerie/tree/b0655057a9df2abe39ea7fc989914ba6f248301c/i2rt_yam
- Commit: `b0655057a9df2abe39ea7fc989914ba6f248301c` (2026-10-31)
- License: MIT, Copyright (c) 2025 i2rt robotics (see `LICENSE`)
- Files: `yam.xml`, `assets/*.stl`, `LICENSE`, `README.md`, `CHANGELOG.md`, unmodified.

DreamGuard builds the bimanual scene in `dreamguard/sim/scene.py` by attaching this model twice
(prefixes `right_` / `left_`) and adding a wrist camera to each `link_6`; the files here are not edited.
