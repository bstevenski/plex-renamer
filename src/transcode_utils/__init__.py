"""
Transcode utilities package for Plex Media Tool.

This package contains utilities specific to media transcoding process.
"""

from .transcoder import (
    VideoInfo,
    cleanup_all_processes,
    cleanup_transcoding_artifacts,
    get_transcode_output_path,
    needs_transcoding,
    transcode_video,
    validate_transcoded_file,
)

__all__ = [
    "VideoInfo",
    "cleanup_all_processes",
    "cleanup_transcoding_artifacts",
    "get_transcode_output_path",
    "needs_transcoding",
    "transcode_video",
    "validate_transcoded_file",
]
