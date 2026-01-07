"""
Filename parser for extracting media metadata from filenames.

This module provides functions to parse TV show and movie filenames,
extracting information like series names, season/episode numbers, years,
and episode titles for use in media processing and Plex naming.
"""

import re
from pathlib import Path
from typing import Optional, Tuple

from common.constants import SEASON_EPISODE_REGEX, YEAR_REGEX, DATE_REGEXES, QUALITY_FORMATS_REGEX


### Internal helper functions ###
def _normalize_text(text: str) -> str:
    """Normalize text by replacing common separators and removing extra whitespace."""
    separators = r"[._\-\+]"
    text = re.sub(separators, " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _sanitize_filename(text: str) -> str:
    """Remove characters that are problematic in filenames."""
    invalid_chars = r'[<>:"/\\|?*]'
    return re.sub(invalid_chars, "", text).strip()


def _parse_tv_filename(filename: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract season and episode numbers from a TV show filename."""
    match = SEASON_EPISODE_REGEX.search(filename)
    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
        return season, episode
    return None, None


def _parse_date_in_filename(filename: str) -> Tuple[Optional[str], Optional[int]]:
    """Extract date from filename for date-based TV shows."""
    for rx in DATE_REGEXES:
        m = rx.search(filename)
        if m:
            y, mo, d = m.group(1), m.group(2), m.group(3)
            return f"{y}-{mo}-{d}", int(y)
    return None, None


def _extract_year_from_stem(stem: str) -> Optional[int]:
    """Extract the first 4-digit year between 1900-2099 from a filename stem."""
    for match in YEAR_REGEX.finditer(stem):
        if match:
            year = int(match.group(0))
            if 1900 <= year <= 2099:
                return year
    return None


def _guess_title_and_year_from_stem(stem: str) -> Tuple[str, Optional[int]]:
    """
    Extract human-readable title and year from a noisy filename stem.

    Examples:
        "Movie.Title.2024.2160p.WEB-DL" -> ("Movie Title", 2024)
        "Intervention.S01E05.720p" -> ("Intervention", None)
        "Chernobyl Diaries (2012)" -> ("Chernobyl Diaries", 2012)
    """
    # Normalize text
    s = _normalize_text(stem)

    # First try parentheses style: Title (2024) - most common for movies
    year = None
    title_part = s
    m = re.search(r"\((19|20)\d{2}\)", s)
    if m:
        year_match = re.search(r"(19|20)\d{2}", m.group(0))
        if year_match:
            year = int(year_match.group(0))
        title_part = s[: m.start()].strip()
    else:
        # Otherwise pick the last 4-digit year token between 1900-2099
        year = _extract_year_from_stem(s)
        if year:
            # Find the position of year to split the title
            year_match = None
            for match in YEAR_REGEX.finditer(s):
                if int(match.group(0)) == year:
                    year_match = match
                    break
            if year_match:
                title_part = s[: year_match.start()].strip()

    # Remove season/episode patterns from title (for TV shows that fall through)
    title_part = SEASON_EPISODE_REGEX.sub("", title_part)

    # Remove quality/format tags at the end
    title_part = QUALITY_FORMATS_REGEX.sub("", title_part)

    # Remove common noisy patterns
    noisy_patterns = [
        r"\b(S\d{1,2}E\d{1,2})\b",  # Season/episode
        r"\b(1080p|720p|480p|2160p|4k)\b",  # Resolution
        r"\b(WEB[-\s]?DL|BluRay|DVDRip)\b",  # Source
        r"\b(x264|x265|h\.264|h\.265)\b",  # Codec
        r"\b(DDP?\d*\.?\d*|AAC|AC3)\b",  # Audio
        r"\b(AMZN|NF|HBO|HULU)\b",  # Streaming services
        r"\b(NTb|ELiTE)\b",  # Release groups
        r"\[[^\]]+\]",  # Square bracketed tags
        r"\{[^}]+\}",  # Curly bracketed tags
        r"\[.*?\]",  # Generic bracketed content
    ]

    for pattern in noisy_patterns:
        title_part = re.sub(pattern, "", title_part, flags=re.IGNORECASE)

    title_part = re.sub(r"\s+", " ", title_part).strip(" -_()")

    # Convert to title case if all caps
    if title_part.isupper():
        title_part = title_part.title()

    return title_part.strip(), year


def _extract_episode_title_from_filename(stem: str) -> Optional[str]:
    """
    Extract episode title from a TV show filename stem.

    Examples:
        "Intervention - s08e11 - Marquel" -> "Marquel"
        "Ghosts - S01E01 - Pilot" -> "Pilot"
        "The Office - S03E04 - The Coup" -> "The Coup"
    Returns None if no obvious title segment exists.
    """
    s = _normalize_text(stem)

    # Try multiple patterns for episode titles
    patterns = [
        # Standard: Show - SXXEYY - Title
        r"[Ss]\d{1,2}[Ee]\d{1,2}\s*[-_–—]\s*(.+)$",
        # Show SXXEYY Title (no dash)
        r"[Ss]\d{1,2}[Ee]\d{1,2}\s+(.+)$",
        # Title - Show SXXEYY (reversed)
        r"(.+)\s*[-_–—]\s*[Ss]\d{1,2}[Ee]\d{1,2}$",
        # Date-based: Show YYYY-MM-DD - Title
        r".+\s*(\d{4})[-_.]\s*(\d{1,2})[-_.]\s*(\d{1,2})\s*[-_–—]\s*(.+)$",
        # Simple format: Title SXXEYY
        r"(.+)\s*[Ss]\d{1,2}[Ee]\d{1,2}$",
    ]

    for pattern in patterns:
        m = re.search(pattern, s)
        if m:
            title_candidate = m.group(1).strip(" -_")
            # Clean common prefixes/suffixes
            title_candidate = re.sub(r"^(Part|Pt)\s*\d+", "", title_candidate)
            title_candidate = re.sub(r"\[.*?]", "", title_candidate)
            if (
                    title_candidate
                    and not SEASON_EPISODE_REGEX.search(title_candidate)
                    and not QUALITY_FORMATS_REGEX.search(title_candidate)
            ):
                return _sanitize_filename(title_candidate)

    # Fallback: try to extract from segments separated by dashes
    parts = [p.strip() for p in s.split(" - ") if p.strip()]
    for part in parts:
        if part and not SEASON_EPISODE_REGEX.search(part) and not QUALITY_FORMATS_REGEX.search(part):
            # Check if this could be a title (not a number, not season/episode pattern)
            if not re.search(r"^(S\d+E\d+|Season\s+\d+|Episode\s+\d+)", part):
                return _sanitize_filename(part)

    return None


### Public functions ###
def parse_media_file(filepath: Path) -> dict:
    """
    Parse a media file and extract all relevant metadata.

    Returns a dictionary with:
        - content_type: "TV Shows" or "Movies"
        - title: Clean title
        - year: Extracted year (if any)
        - season: Season number (TV only)
        - episode: Episode number (TV only)
        - episode_title: Episode title (TV only, if available)
        - date_str: Date string for date-based shows (if applicable)
    """
    stem = filepath.stem
    filename = filepath.name

    # Check if it's a TV show by looking for season/episode patterns
    season, episode = _parse_tv_filename(filename)

    if season is not None and episode is not None:
        # TV Show - detect directory structure to find proper show name
        current_path = filepath
        show_dir = None

        # Walk up the directory tree to find show folder (not season/episode folder)
        current = current_path.parent
        while current and current.name != current.root:
            # Check if current directory looks like a season/episode folder
            if (
                    SEASON_EPISODE_REGEX.search(current.name)
                    or QUALITY_FORMATS_REGEX.search(current.name)
                    or re.search(r"\[.*?]", current.name)
                    or re.search(r"\.(ELiTE|NTb|EZTV)", current.name)
            ):
                # Skip this, go up one level
                current = current.parent
                continue

            # Check if this might be the show folder
            # Good indicators: contains "TV Shows" or typical show naming
            if (
                    "TV Shows" in str(current.parent)
                    or not SEASON_EPISODE_REGEX.search(current.name)
                    and not QUALITY_FORMATS_REGEX.search(current.name)
                    and not re.search(r"\[.*?]", current.name)
                    and not re.search(r"\.(ELiTE|NTb|EZTV)", current.name)
                    and not current.name.lower().startswith("season ")
            ):
                show_dir = current.name
                break

            current = current.parent

        # Fallback to parent directory name if show folder not found
        if not show_dir:
            show_dir = filepath.parent.name

        # Clean up show directory name (remove things like "(US)" etc.)
        show_title = re.sub(r"\s*\([^)]*\)", "", show_dir).strip()
        # Also clean up brackets and other patterns
        show_title = re.sub(r"\[.*?]", "", show_title).strip()
        # Remove IDs in curly braces (IMDB, TMDB, etc.)
        show_title = re.sub(r"\s*\{[a-z0-9\-:]+}", "", show_title).strip()
        # Clean up quality tags and release groups from show directory
        show_title = QUALITY_FORMATS_REGEX.sub("", show_title)
        show_title = re.sub(r"\.ELiTE.*", "", show_title)
        show_title = re.sub(r"\.NTb.*", "", show_title)
        show_title = re.sub(r"\.EZTV.*", "", show_title)
        show_title = re.sub(r"\.x265.*", "", show_title)
        show_title = re.sub(r"\.1080p.*", "", show_title)
        show_title = show_title.strip()

        # Check if show directory looks like a filename (contains quality tags, etc.)
        show_dir_is_filename = (
                SEASON_EPISODE_REGEX.search(show_dir)
                or QUALITY_FORMATS_REGEX.search(show_dir)
                or re.search(r"\[.*?]", show_dir)  # Brackets
                or re.search(r"\.ELiTE.*", show_dir)
                or re.search(r"\.NTb.*", show_dir)
                or re.search(r"\.EZTV.*", show_dir)
                or re.search(r"\.1080p.*", show_dir)
                or re.search(r"\.x265.*", show_dir)
                or re.search(r"\.S25.", show_dir)  # Season-specific pattern
                or "S25." in show_dir  # Season-specific pattern
        )

        # Use show directory title unless it's clearly a filename pattern or generic
        if show_dir_is_filename or show_title.lower() in ["tv shows", "season", "episodes"]:
            title, year = _guess_title_and_year_from_stem(show_dir)  # Treat as potential filename
        else:
            title, year = show_title, None  # Use directory name as title

        episode_title = _extract_episode_title_from_filename(stem)
        date_str, date_year = _parse_date_in_filename(filename)

        # Use date year if no year found in title
        if year is None and date_year is not None:
            year = date_year

        return {
            "content_type": "TV Shows",
            "title": title,
            "year": year,
            "season": season,
            "episode": episode,
            "episode_title": episode_title,
            "date_str": date_str,
        }
    else:
        # Movie
        title, year = _guess_title_and_year_from_stem(stem)

        return {
            "content_type": "Movies",
            "title": title,
            "year": year,
            "season": None,
            "episode": None,
            "episode_title": None,
            "date_str": None,
        }
