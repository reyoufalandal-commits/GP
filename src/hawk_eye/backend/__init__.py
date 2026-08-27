"""
SQLite, routes, and HTTP app live under this package.

Do not import ``create_app`` here: importing ``hawk_eye.backend`` must stay lightweight
so scripts (e.g. ``apply_lab_stream_config``) can use ``db`` / ``detection_settings_repo``
without installing FastAPI. Use ``from hawk_eye.backend.app import create_app`` instead.
"""
