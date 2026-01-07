"""
Common utilities package for Plex Media Tool.

This package contains shared utilities used across all media processing scripts.
"""

from .constants import (
    # Constants
    CONTENT_TYPE_MOVIES,
    CONTENT_TYPE_TV,
    DEFAULT_LOG_LEVEL,
    ERROR_FOLDER,
    LOG_DIR,
    MEDIA_BASE_FOLDER,
    RENAME_FOLDER,
    TRANSCODE_FOLDER,
    UPLOAD_FOLDER,
    VIDEO_EXTENSIONS,
    WORKERS,
    TMDB_API_KEY,
    TMDB_BASE_URL,
    TMDB_IMAGE_BASE_URL,
    TRANSCODE_SETTINGS,
)
from .file_manager import (
    FileOperationError,
    create_error_directory,
    ensure_directory_exists,
    safe_move_with_backup,
    scan_media_files,
)
from .logger import setup_logging

__all__ = [
    # Constants
    "CONTENT_TYPE_MOVIES",
    "CONTENT_TYPE_TV",
    "DEFAULT_LOG_LEVEL",
    "ERROR_FOLDER",
    "LOG_DIR",
    "MEDIA_BASE_FOLDER",
    "RENAME_FOLDER",
    "TRANSCODE_FOLDER",
    "TRANSCODE_SETTINGS",
    "UPLOAD_FOLDER",
    "VIDEO_EXTENSIONS",
    "WORKERS",
    # File manager
    "FileOperationError",
    "create_error_directory",
    "ensure_directory_exists",
    "safe_move_with_backup",
    "scan_media_files",
    # Logger
    "setup_logging",
]
