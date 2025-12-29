#!/usr/bin/env python3
"""
Plex Media Transcoder: Handles video transcoding and file organization.

This script processes media files by:
- Scanning for non-MP4 files in transcode folder
- Analyzing files for transcoding needs
- Transcoding files to MP4 format for compatibility
- Moving completed files to upload folder
- Handling errors gracefully
"""

import argparse
import concurrent.futures
import signal
import sys
from pathlib import Path

# Add src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from common import (
    CONTENT_TYPE_MOVIES,
    CONTENT_TYPE_TV,
    DEFAULT_LOG_LEVEL,
    ERROR_FOLDER,
    TRANSCODE_FOLDER,
    UPLOAD_FOLDER,
    LOG_DIR,
    WORKERS,
    create_error_directory,
    ensure_directory_exists,
    safe_move_with_backup,
    scan_media_files,
    setup_logging,
)
from transcode_utils import (
    VideoInfo,
    cleanup_all_processes,
    cleanup_transcoding_artifacts,
    get_transcode_output_path,
    needs_transcoding,
    transcode_video,
    validate_transcoded_file,
)


class MediaTranscoder:
    """Handles video transcoding and file organization."""

    def __init__(
            self,
            dry_run: bool = False,
            log_level: str = DEFAULT_LOG_LEVEL,
            workers: int = WORKERS,
    ):
        """
        Initialize the Media Transcoder.

        Args:
            dry_run: Preview changes without making modifications
            log_level: Logging level
            workers: Number of worker processes
        """
        self.dry_run = dry_run
        self.log_level = log_level
        self.workers = workers

        # Set up logging
        self.logger = setup_logging(
            log_level=log_level,
            log_dir=Path(LOG_DIR),
            enable_console=True,
        )

        # Set up signal handlers for graceful shutdown
        self.running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
        except (AttributeError, OSError):
            pass

        self.logger.info("Media Transcoder initialized", dry_run=dry_run, workers=workers)

    def _signal_handler(self, signum, _frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

        # Clean up all active subprocesses
        cleanup_all_processes()

    def run(self, source_dir: str | None = None) -> None:
        """Run the main transcoding pipeline."""
        if source_dir:
            transcode_dir = Path(source_dir).resolve()
        else:
            transcode_dir = Path(TRANSCODE_FOLDER).resolve()

        self.logger.info(f"Starting media transcoding from: {transcode_dir}")

        # Ensure all required directories exist
        self._setup_directories()

        # Initialize counters for final summary
        files_attempted = 0
        files_moved_successfully = 0
        files_failed_to_move = 0
        files_actually_transcoded = 0
        files_that_didnt_need_transcoding = 0

        try:
            # Phase 1: Scan and analyze transcoding needs
            files_to_process, analysis_errors = self._scan_and_analyze(transcode_dir)

            if not files_to_process:
                self.logger.info("No files to process")
                return

            self.logger.info(f"Found {len(files_to_process)} files to process")
            self.logger.info(f"Analysis errors: {analysis_errors}")

            # Phase 2: Transcode files in parallel
            self._parallel_transcode(files_to_process)

            # Phase 3: Move all files to upload folder
            for file_info in files_to_process:
                if not self.running:
                    break

                files_attempted += 1
                try:
                    success = self._move_to_upload_folder(file_info)
                    if success:
                        files_moved_successfully += 1
                        if file_info.get("transcoded", False):
                            files_actually_transcoded += 1
                        else:
                            files_that_didnt_need_transcoding += 1
                    else:
                        files_failed_to_move += 1

                except Exception as e:
                    self.logger.error(f"Failed to move file {file_info['path']}: {e}")
                    self._handle_error(file_info["path"], str(e))
                    files_failed_to_move += 1

        except KeyboardInterrupt:
            self.logger.info("Processing interrupted by user")
        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            raise
        finally:
            self.logger.info(
                f"Media transcoding completed - "
                f"Files attempted: {files_attempted}, "
                f"Successfully moved: {files_moved_successfully}, "
                f"Failed to move: {files_failed_to_move}, "
                f"Actually transcoded: {files_actually_transcoded}, "
                f"Didn't need transcoding: {files_that_didnt_need_transcoding}"
            )

    def _setup_directories(self) -> None:
        """Ensure all required directories exist."""
        directories = [
            Path(UPLOAD_FOLDER) / CONTENT_TYPE_MOVIES,
            Path(UPLOAD_FOLDER) / CONTENT_TYPE_TV,
            Path(ERROR_FOLDER),
        ]

        for directory in directories:
            ensure_directory_exists(directory)
            self.logger.debug(f"Ensured directory exists: {directory}")

    def _scan_and_analyze(self, transcode_dir: Path) -> tuple[list[dict], int]:
        """Scan for files and analyze transcoding needs."""
        files_to_process = []
        analysis_errors = 0

        for content_type in [CONTENT_TYPE_MOVIES, CONTENT_TYPE_TV]:
            content_dir = transcode_dir / content_type

            if not content_dir.exists():
                self.logger.debug(f"Transcode directory does not exist: {content_dir}")
                continue

            self.logger.info(f"Scanning {content_type} from: {content_dir}")

            for filepath in scan_media_files(content_dir):
                if not self.running:
                    break

                try:
                    file_info = self._analyze_file(filepath, content_type)
                    if file_info:
                        files_to_process.append(file_info)
                    else:
                        analysis_errors += 1

                except Exception as e:
                    self.logger.error(f"Failed to analyze file {filepath}: {e}")
                    analysis_errors += 1

        return files_to_process, analysis_errors

    def _analyze_file(self, filepath: Path, content_type: str) -> dict | None:
        """Analyze a single file for transcoding needs."""
        try:
            # Check file extension
            extension = filepath.suffix.lower()
            if extension == ".mp4":
                # MP4 files don't need transcoding
                self.logger.debug(f"MP4 file, no transcoding needed: {filepath.name}")
                return {
                    "path": filepath,
                    "content_type": content_type,
                    "needs_transcoding": False,
                    "transcoded": False,
                }

            # Analyze non-MP4 files for transcoding needs
            video_info = VideoInfo(filepath)
            needs_trans = needs_transcoding(video_info)

            self.logger.debug(f"File {filepath.name} needs transcoding: {needs_trans}")

            return {
                "path": filepath,
                "content_type": content_type,
                "needs_transcoding": needs_trans,
                "transcoded": False,
                "video_info": video_info if needs_trans else None,
            }

        except Exception as e:
            self.logger.error(f"Error analyzing file {filepath}: {e}")
            return None

    def _parallel_transcode(self, files_to_process: list[dict]) -> None:
        """Transcode files in parallel using workers."""
        # Filter files that need transcoding
        files_to_transcode = [f for f in files_to_process if f["needs_transcoding"]]

        if not files_to_transcode:
            self.logger.info("No files need transcoding")
            return

        self.logger.info(f"Transcoding {len(files_to_transcode)} files with {self.workers} workers")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            # Submit all transcoding jobs
            future_to_file = {
                executor.submit(self._transcode_file, file_info): file_info for file_info in files_to_transcode
            }

            # Process completed jobs
            completed = 0
            for future in concurrent.futures.as_completed(future_to_file):
                file_info = future_to_file[future]
                completed += 1

                try:
                    transcoded_path = future.result()
                    if transcoded_path:
                        file_info["transcoded_path"] = transcoded_path
                        file_info["transcoded"] = True
                        self.logger.info(
                            f"[{completed}/{len(files_to_transcode)}] Transcoded: {file_info['path'].name}"
                        )
                    else:
                        self.logger.error(
                            f"[{completed}/{len(files_to_transcode)}] Failed to transcode: {file_info['path'].name}"
                        )

                except Exception as e:
                    self.logger.error(f"Transcoding error for {file_info['path'].name}: {e}")

    def _transcode_file(self, file_info: dict) -> Path | None:
        """Transcode a single file."""
        filepath = file_info["path"]

        if self.dry_run:
            self.logger.info(f"DRY RUN: Would transcode {filepath}")
            return None

        try:
            # Determine output path
            output_path = get_transcode_output_path(filepath)

            # Transcode
            success = transcode_video(filepath, output_path)

            if success and validate_transcoded_file(filepath, output_path):
                # Clean up original file
                cleanup_transcoding_artifacts(filepath)
                return output_path
            else:
                # Remove failed transcoding attempt
                if output_path.exists():
                    output_path.unlink()
                return None

        except Exception as e:
            self.logger.error(f"Transcoding failed for {filepath}: {e}")
            return None

    def _move_to_upload_folder(self, file_info: dict) -> bool:
        """Move processed file to upload folder."""
        # Determine final path (either original or transcoded)
        if file_info.get("transcoded_path"):
            final_path = file_info["transcoded_path"]
        else:
            final_path = file_info["path"]

        content_type = file_info["content_type"]
        upload_dir = Path(UPLOAD_FOLDER) / content_type

        # Check if the file still exists
        if not final_path.exists():
            self.logger.warning(f"File not found, skipping: {final_path}")
            return False

        # Construct destination path maintaining the directory structure
        try:
            # Try to get relative path from transcode folder
            transcode_base = Path(TRANSCODE_FOLDER) / content_type
            relative_path = final_path.relative_to(transcode_base)
        except ValueError:
            # Fallback to just the filename
            relative_path = Path(final_path.name)

        destination_path = upload_dir / relative_path

        if self.dry_run:
            self.logger.info(f"DRY RUN: Would move {final_path} to {destination_path}")
            return True

        error_dir = create_error_directory(Path(ERROR_FOLDER), "upload_errors")
        success = safe_move_with_backup(final_path, destination_path, error_dir)

        if success:
            self.logger.info(f"Successfully moved to upload: {relative_path}")
        else:
            self.logger.error(f"Failed to move to upload: {final_path.name}")

        return success

    def _handle_error(self, filepath: Path, error_message: str) -> bool:
        """Handle processing errors by moving file to error directory."""
        self.logger.error(f"Handling error for {filepath}: {error_message}")

        if self.dry_run:
            self.logger.info(f"DRY RUN: Would move {filepath} to error directory")
            return False

        error_dir = create_error_directory(Path(ERROR_FOLDER), "transcoding_errors")
        error_destination = error_dir / filepath.name

        try:
            safe_move_with_backup(filepath, error_destination)
            return False
        except Exception as e:
            self.logger.error(f"Failed to move error file: {e}")
            return False


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Plex media file transcoder - handles video transcoding and file organization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
 Examples:
   %(prog)s                                    # Process from default transcode directory
   %(prog)s /path/to/media                    # Process from custom directory
   %(prog)s --workers 8                       # Use 8 parallel workers for transcoding
   %(prog)s --dry-run                         # Preview changes without modifications

   %(prog)s --log-level DEBUG                 # Enable debug logging
        """,
    )

    parser.add_argument(
        "source_dir",
        nargs="?",
        help="Source directory containing media files to transcode (default: ../.media/ready-to-transcode)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making modifications",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        default=DEFAULT_LOG_LEVEL,
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=WORKERS,
        help=f"Number of worker processes for transcoding (default: {WORKERS})",
    )

    args = parser.parse_args()

    # Create and run the media transcoder
    transcoder = MediaTranscoder(
        dry_run=args.dry_run,
        log_level=args.log_level,
        workers=args.workers,
    )

    try:
        transcoder.run(args.source_dir)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
