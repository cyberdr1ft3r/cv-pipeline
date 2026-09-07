# script/cv_data_finder.py

"""
CV Data Finder Module
Finds and retrieves existing extracted CV JSON data from archives or latest sessions.
Avoids re-extraction when CVs have already been processed.
"""

import os
import json
import yaml
import re
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ================================
# LOAD CONFIG
# ================================
CONFIG_PATH = PROJECT_ROOT / "config" / "config_yaml.yaml"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# Directory paths
# Action 227: data folders resolve under DATA_ROOT via the shared resolver.
try:
    from script.storage_paths import CURRENT_DIR, ARCHIVE_DIR, safe_relpath
except ImportError:
    from storage_paths import CURRENT_DIR, ARCHIVE_DIR, safe_relpath

ARCHIVE_BASE = ARCHIVE_DIR
INTERMEDIARY_BASE = CURRENT_DIR / "intermediary_structured"

# ================================
# DATA CLASSES
# ================================
@dataclass
class CVSource:
    """Represents a source of extracted CV data"""
    session_id: str
    source_type: str  # 'archive' or 'intermediary'
    path: Path
    cv_count: int
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

    def __str__(self):
        return f"{self.source_type}/{self.session_id} ({self.cv_count} CVs)"

# ================================
# SESSION DISCOVERY
# ================================
def find_archived_sessions() -> List[CVSource]:
    """
    Find all archived sessions with extracted CVs.
    
    Returns:
        List of CVSource objects sorted by timestamp (newest first)
    """
    sessions = []
    
    if not ARCHIVE_BASE.exists():
        return sessions
    
    for session_dir in ARCHIVE_BASE.iterdir():
        if not session_dir.is_dir():
            continue
        
        # Check if it's a valid session ID format (14 digits)
        if not re.match(r'\d{14}', session_dir.name):
            continue
        
        # Check for extracted CVs
        extracted_dir = session_dir / "cvs" / "extracted"
        if not extracted_dir.exists():
            continue
        
        cv_files = list(extracted_dir.glob("*.json"))
        if not cv_files:
            continue
        
        # Parse timestamp from session ID
        try:
            timestamp = datetime.strptime(session_dir.name, "%Y%m%d%H%M%S")
        except ValueError:
            continue
        
        # Load metadata if available
        metadata = None
        metadata_path = session_dir / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        sessions.append(CVSource(
            session_id=session_dir.name,
            source_type='archive',
            path=extracted_dir,
            cv_count=len(cv_files),
            timestamp=timestamp,
            metadata=metadata
        ))
    
    # Sort by timestamp (newest first)
    sessions.sort(key=lambda x: x.timestamp, reverse=True)
    return sessions


def find_intermediary_sessions() -> List[CVSource]:
    """
    Find all intermediary sessions with extracted CVs (not yet archived).
    
    Returns:
        List of CVSource objects sorted by timestamp (newest first)
    """
    sessions = []
    
    if not INTERMEDIARY_BASE.exists():
        return sessions
    
    for session_dir in INTERMEDIARY_BASE.iterdir():
        if not session_dir.is_dir():
            continue
        
        # Check if it's a valid session ID format (14 digits)
        if not re.match(r'\d{14}', session_dir.name):
            continue
        
        cv_files = list(session_dir.glob("*.json"))
        if not cv_files:
            continue
        
        # Parse timestamp from session ID
        try:
            timestamp = datetime.strptime(session_dir.name, "%Y%m%d%H%M%S")
        except ValueError:
            continue
        
        sessions.append(CVSource(
            session_id=session_dir.name,
            source_type='intermediary',
            path=session_dir,
            cv_count=len(cv_files),
            timestamp=timestamp
        ))
    
    # Sort by timestamp (newest first)
    sessions.sort(key=lambda x: x.timestamp, reverse=True)
    return sessions


def find_all_cv_sources() -> List[CVSource]:
    """
    Find all available CV sources (both archives and intermediary).
    
    Returns:
        Combined list of CVSource objects sorted by timestamp (newest first)
    """
    archived = find_archived_sessions()
    intermediary = find_intermediary_sessions()
    
    # Combine and sort
    all_sources = archived + intermediary
    all_sources.sort(key=lambda x: x.timestamp, reverse=True)
    
    return all_sources


def get_latest_cv_source() -> Optional[CVSource]:
    """
    Get the most recent CV source (archive or intermediary).
    
    Returns:
        CVSource object or None if no sources found
    """
    sources = find_all_cv_sources()
    return sources[0] if sources else None

# ================================
# CV DATA RETRIEVAL
# ================================
def list_cvs_in_source(source: CVSource) -> List[Path]:
    """
    List all CV JSON files in a source.
    
    Returns:
        List of paths to CV JSON files
    """
    if not source.path.exists():
        return []
    return sorted(source.path.glob("*.json"))


def load_cv_from_source(source: CVSource, cv_filename: str) -> Optional[Dict[str, Any]]:
    """
    Load a specific CV from a source.
    
    Args:
        source: CVSource object
        cv_filename: Name of the CV JSON file
        
    Returns:
        CV data dict or None
    """
    cv_path = source.path / cv_filename
    if not cv_path.exists():
        return None
    
    try:
        with open(cv_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def load_all_cvs_from_source(source: CVSource) -> Dict[str, Dict[str, Any]]:
    """
    Load all CVs from a source.
    
    Returns:
        Dict mapping filename to CV data
    """
    cvs = {}
    for cv_path in list_cvs_in_source(source):
        try:
            with open(cv_path, 'r', encoding='utf-8') as f:
                cvs[cv_path.name] = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue
    return cvs

# ================================
# CV DATA COPYING
# ================================
def copy_cvs_to_session(source: CVSource, target_session_id: str) -> Tuple[int, Path]:
    """
    Copy CVs from a source to a new session's intermediary directory.
    This allows reusing CVs without re-extraction.
    
    Args:
        source: CVSource to copy from
        target_session_id: Target session ID
        
    Returns:
        (count of CVs copied, target directory path)
    """
    target_dir = INTERMEDIARY_BASE / target_session_id
    os.makedirs(target_dir, exist_ok=True)
    
    copied = 0
    for cv_path in list_cvs_in_source(source):
        target_path = target_dir / cv_path.name
        try:
            shutil.copy2(cv_path, target_path)
            copied += 1
        except IOError as e:
            print(f"   ⚠️  Failed to copy {cv_path.name}: {e}")
    
    return copied, target_dir

# ================================
# UNIQUE CV DETECTION
# ================================
def get_unique_candidates(sources: List[CVSource]) -> Dict[str, Tuple[CVSource, Path]]:
    """
    Get unique candidates across multiple sources (by email).
    Prefers newer sources for duplicates.
    
    Returns:
        Dict mapping candidate email to (source, cv_path)
    """
    unique = {}  # email -> (source, path)
    
    # Sources are already sorted newest first
    for source in sources:
        for cv_path in list_cvs_in_source(source):
            try:
                with open(cv_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                email = data.get("informations_personnelles", {}).get("email", "")
                
                if email and email not in unique:
                    unique[email] = (source, cv_path)
                elif not email:
                    # Use filename as fallback key
                    key = f"__file__{cv_path.name}"
                    if key not in unique:
                        unique[key] = (source, cv_path)
                        
            except (json.JSONDecodeError, IOError):
                continue
    
    return unique

# ================================
# INTERACTIVE DISPLAY
# ================================
def display_cv_sources(sources: List[CVSource]):
    """Display available CV sources in a formatted table"""
    if not sources:
        print("   No CV sources found")
        return
    
    print(f"\n{'#':<4} {'Session ID':<16} {'Type':<14} {'CVs':<6} {'Date':<20}")
    print("-" * 65)
    
    for i, source in enumerate(sources, 1):
        date_str = source.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{i:<4} {source.session_id:<16} {source.source_type:<14} {source.cv_count:<6} {date_str:<20}")
    
    print()


def interactive_select_source() -> Optional[CVSource]:
    """
    Interactive prompt to select a CV source.
    
    Returns:
        Selected CVSource or None
    """
    print("\n" + "=" * 70)
    print("📂 CV DATA FINDER")
    print("=" * 70)
    
    sources = find_all_cv_sources()
    
    if not sources:
        print("\n❌ No extracted CV data found")
        print("   Please run the extraction pipeline first.\n")
        return None
    
    print(f"\n📋 Found {len(sources)} session(s) with extracted CVs:")
    display_cv_sources(sources)
    
    while True:
        user_input = input("→ Select session number (or 'latest' for most recent): ").strip().lower()
        
        if user_input in ['latest', 'l', '']:
            return sources[0]
        
        if user_input in ['exit', 'quit', 'q']:
            return None
        
        try:
            idx = int(user_input) - 1
            if 0 <= idx < len(sources):
                return sources[idx]
            else:
                print(f"   ❌ Invalid selection. Enter 1-{len(sources)}\n")
        except ValueError:
            print("   ❌ Please enter a number or 'latest'\n")


def prompt_for_cv_source(allow_multiple: bool = False) -> Optional[CVSource]:
    """
    Prompt user to select a CV source with options.
    
    Args:
        allow_multiple: If True, allow combining multiple sources
        
    Returns:
        Selected CVSource or None
    """
    sources = find_all_cv_sources()
    
    if not sources:
        return None
    
    if len(sources) == 1:
        # Auto-select if only one source
        print(f"\n✅ Auto-selected CV source: {sources[0]}")
        return sources[0]
    
    return interactive_select_source()

# ================================
# ENTRY POINT
# ================================
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("📂 CV DATA FINDER - Standalone Mode")
    print("=" * 70)
    
    sources = find_all_cv_sources()
    
    if not sources:
        print("\n❌ No CV data found")
        print("   Run the extraction pipeline first to create CV data.\n")
    else:
        print(f"\n✅ Found {len(sources)} session(s) with extracted CVs:")
        display_cv_sources(sources)
        
        # Show details of latest
        latest = sources[0]
        print(f"📋 Latest session: {latest.session_id}")
        print(f"   Type: {latest.source_type}")
        print(f"   Path: {safe_relpath(latest.path)}")
        print(f"   CVs: {latest.cv_count}")
        print()
        
        # List CVs in latest
        print("   Candidates:")
        for cv_path in list_cvs_in_source(latest)[:10]:
            try:
                with open(cv_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                name = data.get("informations_personnelles", {}).get("nom_complet", cv_path.stem)
                print(f"   • {name}")
            except:
                print(f"   • {cv_path.stem}")
        
        if latest.cv_count > 10:
            print(f"   ... and {latest.cv_count - 10} more")
        print()
