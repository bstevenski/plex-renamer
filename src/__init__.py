"""
Plex Media Tool - Automated Plex media file processing pipeline.

This package provides tools for processing media files downloaded from torrent
clients and preparing them for Plex, including filename parsing, TMDb metadata
lookup, file renaming, and video transcoding.
"""

__version__ = "1.0.0"
__author__ = "Bri Stevenski"

# Common utilities (for external use)
from .common import (
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
    # File operations
    scan_media_files,
    ensure_directory_exists,
    safe_move_with_backup,
    # Logging
    setup_logging,
)
# Main script entry points
from .rename_media_files import main as rename_main
# Rename utilities (for external use)
from .rename_utils import (
    construct_movie_path,
    construct_tv_show_path,
    parse_media_file,
    TMDbClient,
)
from .transcode_media_files import main as transcode_main
# Transcode utilities (for external use)
from .transcode_utils import (
    VideoInfo,
    needs_transcoding,
    transcode_video,
    validate_transcoded_file,
)

__all__ = [
    # Package info
    "__version__",
    "__author__",
    # Main entry points
    "rename_main",
    "transcode_main",
    # Common utilities
    "CONTENT_TYPE_MOVIES",
    "CONTENT_TYPE_TV",
    "DEFAULT_LOG_LEVEL",
    "ERROR_FOLDER",
    "LOG_DIR",
    "MEDIA_BASE_FOLDER",
    "RENAME_FOLDER",
    "TRANSCODE_FOLDER",
    "UPLOAD_FOLDER",
    "VIDEO_EXTENSIONS",
    "WORKERS",
    "scan_media_files",
    "ensure_directory_exists",
    "safe_move_with_backup",
    "setup_logging",
    # Rename utilities
    "construct_movie_path",
    "construct_tv_show_path",
    "parse_media_file",
    "TMDbClient",
    # Transcode utilities
    "VideoInfo",
    "needs_transcoding",
    "transcode_video",
    "validate_transcoded_file",
]
