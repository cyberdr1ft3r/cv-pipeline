# script/archiver.py

"""
Session Archiver Module
Consolidates all session data into a single archive directory and cleans up original files.
"""

import os
import json
import yaml
import shutil
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# ================================
# PATHS SETUP
# ================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = PROJECT_ROOT / "config" / "config_yaml.yaml"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# Directory paths
# Action 227: data folders resolve under DATA_ROOT via the shared resolver.
try:
    from script.storage_paths import CURRENT_DIR, ARCHIVE_DIR, read_cv_source_marker
except ImportError:
    from storage_paths import CURRENT_DIR, ARCHIVE_DIR, read_cv_source_marker

MATCHING_RESULTS_BASE = CURRENT_DIR / "matching_results"
FINAL_RESULT_BASE = CURRENT_DIR / "final_result"
LOG_DIR_BASE = CURRENT_DIR / "logs"
OFFER_DIR_BASE = CURRENT_DIR / "offer"
ARCHIVE_DIR_BASE = ARCHIVE_DIR
INTERMEDIARY_DIR_BASE = CURRENT_DIR / "intermediary_structured"
FAILED_DIR_BASE = CURRENT_DIR / "failed"
TESTS_DIR_BASE = CURRENT_DIR / "tests"
FORMATTED_CV_DIR_BASE = CURRENT_DIR / "formatted_cv"


# ================================
# SESSION DISCOVERY
# ================================
def get_offer_name_for_session(session_id: str) -> Optional[str]:
    """Get the offer name for a session by reading the offer file"""
    offer_dir = OFFER_DIR_BASE / session_id
    if not offer_dir.exists():
        return None
    
    for file in offer_dir.iterdir():
        if file.is_file() and file.suffix in ['.txt', '.pdf', '.docx']:
            return file.stem
    return None


def find_available_sessions() -> List[Tuple[str, Optional[str]]]:
    """
    Find all available session IDs across all data directories.
    
    Returns:
        List of tuples (session_id, offer_name)
    """
    sessions_set = set()
    
    # Check multiple directories for session IDs
    directories_to_check = [
        MATCHING_RESULTS_BASE,
        FINAL_RESULT_BASE,
        INTERMEDIARY_DIR_BASE,
        OFFER_DIR_BASE,
        LOG_DIR_BASE
    ]
    
    for base_dir in directories_to_check:
        if base_dir.exists():
            for item in base_dir.iterdir():
                if item.is_dir() and re.match(r'\d{14}', item.name):
                    sessions_set.add(item.name)
    
    # Build list with offer names
    sessions = []
    for session_id in sessions_set:
        # Skip if already archived
        archive_dir = ARCHIVE_DIR_BASE / session_id
        if archive_dir.exists() and (archive_dir / "metadata.json").exists():
            continue  # Already archived
        offer_name = get_offer_name_for_session(session_id)
        sessions.append((session_id, offer_name))
    
    return sorted(sessions, key=lambda x: x[0], reverse=True)


def find_archived_sessions() -> List[Tuple[str, Optional[str], str]]:
    """
    Find all already archived sessions.
    
    Returns:
        List of tuples (session_id, offer_name, archived_at)
    """
    sessions = []
    
    if ARCHIVE_DIR_BASE.exists():
        for item in ARCHIVE_DIR_BASE.iterdir():
            if item.is_dir() and re.match(r'\d{14}', item.name):
                metadata_file = item / "metadata.json"
                offer_name = None
                archived_at = "Unknown"
                
                if metadata_file.exists():
                    try:
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                            offer_name = metadata.get("offer_name")
                            archived_at = metadata.get("archived_at", "Unknown")
                    except:
                        pass
                
                sessions.append((item.name, offer_name, archived_at))
    
    return sorted(sessions, key=lambda x: x[0], reverse=True)


# ================================
# ARCHIVE FUNCTION
# ================================
def archive_session(
    session_id: str, 
    test_scores_path: Optional[Path] = None,
    cleanup: bool = True,
    verbose: bool = True
) -> bool:
    """
    Archive all session data to a consolidated archive directory.
    
    Creates structure:
        data/archive/{session_id}/
            ├── offer/              - Job offer files
            ├── cvs/
            │   ├── originals/      - Original CV files (from archive_cv)
            │   └── extracted/      - Extracted JSON files
            ├── matching/           - Matching result files
            ├── tests/              - Test scores file
            ├── final/              - Final result files
            ├── logs/               - Log files
            └── metadata.json       - Archive metadata
    
    Args:
        session_id: The session ID to archive
        test_scores_path: Optional path to test scores file
        cleanup: If True, remove original files after successful archiving
        verbose: If True, print progress messages
        
    Returns:
        True if successful, False otherwise
    """
    def log(msg: str):
        if verbose:
            print(msg)
    
    log("📦 Archiving session...")
    log(f"   🆔 Session ID: {session_id}")
    
    try:
        archive_base = ARCHIVE_DIR_BASE / session_id
        
        # Create archive subdirectories
        subdirs = [
            archive_base / "offer",
            archive_base / "cvs" / "originals",
            archive_base / "cvs" / "extracted",
            archive_base / "cvs" / "formatted",
            archive_base / "matching",
            archive_base / "tests",
            archive_base / "final",
            archive_base / "logs"
        ]
        
        for subdir in subdirs:
            os.makedirs(subdir, exist_ok=True)
        
        files_archived = 0
        dirs_to_cleanup = []
        
        # 1. Archive offer files
        offer_dir = OFFER_DIR_BASE / session_id
        if offer_dir.exists():
            for file in offer_dir.iterdir():
                if file.is_file():
                    shutil.copy2(file, archive_base / "offer" / file.name)
                    files_archived += 1
            dirs_to_cleanup.append(offer_dir)
            log(f"   ✅ Offer files archived")
        
        # 2. Check for original CVs in archive_cv location (from extraction)
        # The extraction script archives originals to archive/{session_id}/cvs/originals/
        # If they exist there already, we don't need to copy again
        originals_in_archive = archive_base / "cvs" / "originals"
        if originals_in_archive.exists() and any(originals_in_archive.iterdir()):
            log(f"   ✅ Original CVs already in archive")
        
        # 3. Archive extracted CV JSON files
        intermediary_dir = INTERMEDIARY_DIR_BASE / session_id
        cv_source_dir = None
        if intermediary_dir.exists() and any(intermediary_dir.glob("*.json")):
            cv_source_dir = intermediary_dir
        else:
            marker_dir = read_cv_source_marker(session_id)
            if marker_dir and marker_dir.exists():
                cv_source_dir = marker_dir
                log(f"   📂 CV source from marker: {marker_dir}")

        if cv_source_dir:
            for file in cv_source_dir.iterdir():
                if file.is_file() and file.suffix == '.json':
                    shutil.copy2(file, archive_base / "cvs" / "extracted" / file.name)
                    files_archived += 1
            if cv_source_dir == intermediary_dir:
                dirs_to_cleanup.append(intermediary_dir)
            log(f"   ✅ Extracted CVs archived")
        
        # 3b. Archive formatted CVs (HTML + PDF)
        formatted_cv_dir = FORMATTED_CV_DIR_BASE / session_id
        if formatted_cv_dir.exists():
            for file in formatted_cv_dir.iterdir():
                if file.is_file() and file.suffix in ['.html', '.pdf']:
                    shutil.copy2(file, archive_base / "cvs" / "formatted" / file.name)
                    files_archived += 1
            dirs_to_cleanup.append(formatted_cv_dir)
            log(f"   ✅ Formatted CVs archived")
        
        # 4. Archive matching results
        matching_dir = MATCHING_RESULTS_BASE / session_id
        if matching_dir.exists():
            for file in matching_dir.iterdir():
                if file.is_file():
                    shutil.copy2(file, archive_base / "matching" / file.name)
                    files_archived += 1
            dirs_to_cleanup.append(matching_dir)
            log(f"   ✅ Matching results archived")
        
        # 5. Archive test scores file (from data/tests/{session_id}/ or provided path)
        tests_dir = TESTS_DIR_BASE / session_id
        if tests_dir.exists() and any(tests_dir.iterdir()):
            # Auto-detect test scores from session directory
            for file in tests_dir.iterdir():
                if file.is_file():
                    shutil.copy2(file, archive_base / "tests" / file.name)
                    files_archived += 1
            dirs_to_cleanup.append(tests_dir)
            log(f"   ✅ Test scores archived (from session directory)")
        elif test_scores_path and test_scores_path.exists():
            # Fallback to provided path
            shutil.copy2(test_scores_path, archive_base / "tests" / test_scores_path.name)
            files_archived += 1
            log(f"   ✅ Test scores archived")
        
        # 6. Archive final results
        final_dir = FINAL_RESULT_BASE / session_id
        if final_dir.exists():
            for file in final_dir.iterdir():
                if file.is_file():
                    shutil.copy2(file, archive_base / "final" / file.name)
                    files_archived += 1
            dirs_to_cleanup.append(final_dir)
            log(f"   ✅ Final results archived")
        
        # 7. Archive log files
        log_dir = LOG_DIR_BASE / session_id
        if log_dir.exists():
            for file in log_dir.iterdir():
                if file.is_file():
                    shutil.copy2(file, archive_base / "logs" / file.name)
                    files_archived += 1
            dirs_to_cleanup.append(log_dir)
            log(f"   ✅ Log files archived")
        
        # 8. Archive failed files if any
        failed_dir = FAILED_DIR_BASE / session_id
        if failed_dir.exists() and any(failed_dir.iterdir()):
            failed_archive = archive_base / "failed"
            os.makedirs(failed_archive, exist_ok=True)
            for file in failed_dir.iterdir():
                if file.is_file():
                    shutil.copy2(file, failed_archive / file.name)
                    files_archived += 1
            dirs_to_cleanup.append(failed_dir)
            log(f"   ✅ Failed files archived")
        
        # 9. Create metadata file
        metadata = {
            "session_id": session_id,
            "archived_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "offer_name": get_offer_name_for_session(session_id),
            "files_archived": files_archived,
            "cleanup_performed": cleanup,
            "archive_structure": {
                "offer": str(archive_base / "offer"),
                "cvs_originals": str(archive_base / "cvs" / "originals"),
                "cvs_extracted": str(archive_base / "cvs" / "extracted"),
                "cvs_formatted": str(archive_base / "cvs" / "formatted"),
                "matching": str(archive_base / "matching"),
                "tests": str(archive_base / "tests"),
                "final": str(archive_base / "final"),
                "logs": str(archive_base / "logs")
            }
        }
        
        metadata_file = archive_base / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        log(f"   📂 Archive location: data/archive/{session_id}/")
        log(f"   📄 Files archived: {files_archived}")
        
        # 10. Cleanup original directories if requested
        if cleanup and files_archived > 0:
            log("")
            log("🧹 Cleaning up original files...")
            cleaned_dirs = 0
            
            for dir_path in dirs_to_cleanup:
                try:
                    if dir_path.exists():
                        shutil.rmtree(dir_path)
                        cleaned_dirs += 1
                except Exception as e:
                    log(f"   ⚠️  Could not remove {dir_path.name}: {e}")
            
            log(f"   ✅ Removed {cleaned_dirs} session directory(ies)")
        
        return True
        
    except Exception as e:
        log(f"   ❌ Archive failed: {e}")
        return False


# ================================
# INTERACTIVE PROMPT
# ================================
def prompt_for_session() -> Optional[str]:
    """
    Display available sessions and prompt user to select one.
    
    Returns:
        Selected session ID or None if cancelled
    """
    print("\n" + "=" * 70)
    print("📦 SESSION ARCHIVER")
    print("=" * 70 + "\n")
    
    # Show available (non-archived) sessions
    sessions = find_available_sessions()
    
    # if not sessions:
    #     print("ℹ️  No sessions available for archiving.")
        
    #     # Show already archived sessions
    #     archived = find_archived_sessions()
    #     if archived:
    #         print("\n📚 Already archived sessions:")
    #         for session_id, offer_name, archived_at in archived:
    #             if offer_name:
    #                 print(f"   • {session_id} - {offer_name} (archived: {archived_at})")
    #             else:
    #                 print(f"   • {session_id} (archived: {archived_at})")
        
    #     return None
    
    print("📋 Available sessions to archive:\n")
    for idx, (session_id, offer_name) in enumerate(sessions, 1):
        if offer_name:
            print(f"   {idx}. {session_id} - {offer_name}")
        else:
            print(f"   {idx}. {session_id}")
    
    print(f"\n   0. Cancel\n")
    
    # # Also show already archived sessions for reference
    # archived = find_archived_sessions()
    # if archived:
    #     print("📚 Already archived sessions:")
    #     for session_id, offer_name, _ in archived[:5]:  # Show only last 5
    #         if offer_name:
    #             print(f"   • {session_id} - {offer_name}")
    #         else:
    #             print(f"   • {session_id}")
    #     if len(archived) > 5:
    #         print(f"   ... and {len(archived) - 5} more")
    #     print("")
    
    # Extract session IDs for validation
    session_ids = [s[0] for s in sessions]
    
    while True:
        user_input = input("🆔 Enter session number or ID to archive (0 to cancel): ").strip()
        
        if not user_input:
            print("❌ Selection cannot be empty. Please try again.\n")
            continue
        
        # Check for cancel
        if user_input == "0":
            print("\n⚠️  Archiving cancelled.\n")
            return None
        
        # Check if numeric selection
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(sessions):
                return sessions[idx][0]
            else:
                print(f"❌ Invalid selection. Enter 0-{len(sessions)}.\n")
                continue
        
        # Check if valid session ID
        if user_input in session_ids:
            return user_input
        else:
            print(f"❌ Session not found: {user_input}")
            print("   Please enter a valid session ID or number.\n")
            continue


# Note: prompt_for_test_scores() has been removed as test scores are now
# auto-detected from data/tests/{session_id}/ (saved by final_result.py)


# ================================
# ENTRY POINT
# ================================
def main():
    """Main entry point for the archiver module"""
    parser = argparse.ArgumentParser(
        description="Archive session data and clean up original files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python archiver.py                     # Interactive mode
  python archiver.py --session 20260122123145
  python archiver.py --session 20260122123145 --tests scores.csv
  python archiver.py --session 20260122123145 --no-cleanup
  python archiver.py --list              # List available sessions
        """
    )
    parser.add_argument(
        "--session",
        type=str,
        help="Session ID to archive"
    )
    parser.add_argument(
        "--tests",
        type=str,
        help="Path to test scores file to include in archive"
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Do not remove original files after archiving"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available sessions and exit"
    )
    
    args = parser.parse_args()
    
    # Handle --list option
    if args.list:
        print("\n📋 Available sessions to archive:\n")
        sessions = find_available_sessions()
        if not sessions:
            print("   No sessions available for archiving")
        else:
            for session_id, offer_name in sessions:
                if offer_name:
                    print(f"   • {session_id} - {offer_name}")
                else:
                    print(f"   • {session_id}")
        
        # print("\n📚 Already archived sessions:\n")
        # archived = find_archived_sessions()
        # if not archived:
        #     print("   No archived sessions")
        # else:
        #     for session_id, offer_name, archived_at in archived:
        #         if offer_name:
        #             print(f"   • {session_id} - {offer_name} (archived: {archived_at})")
        #         else:
        #             print(f"   • {session_id} (archived: {archived_at})")
        print("")
        return
    
    try:
        # Determine session ID
        if args.session:
            session_id = args.session
            print(f"\n📦 Archiving session: {session_id}\n")
        else:
            session_id = prompt_for_session()
            if not session_id:
                return
        
        # Determine test scores path (only from CLI arg, auto-detected from session otherwise)
        test_scores_path = None
        if args.tests:
            test_scores_path = Path(args.tests)
            if not test_scores_path.exists():
                print(f"❌ Test scores file not found: {test_scores_path}")
                return
        # Note: Test scores are now auto-detected from data/tests/{session_id}/ 
        
        # Determine cleanup setting
        cleanup = not args.no_cleanup
        
        print("")
        
        # Perform archiving
        success = archive_session(
            session_id=session_id,
            test_scores_path=test_scores_path,
            cleanup=cleanup,
            verbose=True
        )
        
        if success:
            print("\n✅ Session archived successfully!\n")
        else:
            print("\n❌ Archiving failed.\n")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Archiving interrupted by user.\n")
    except Exception as e:
        print(f"\n💥 Error: {e}\n")
    finally:
        print("👋 Archiver terminated\n")


if __name__ == "__main__":
    main()
