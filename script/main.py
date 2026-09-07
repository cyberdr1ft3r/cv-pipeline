# script/main.py

"""
Main Pipeline - Unified Entry Point for CV Processing

Supports two workflow modes:
1. CV Folder Mode: User provides CV folder → Extract → Match → Final Result
2. Job Offer Mode: User provides job offer file → Reuse existing CVs → Match → Final Result

The system automatically detects the input type and routes to the appropriate workflow.
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
VENV_DIR = PROJECT_ROOT / ".venv"
REQUIREMENTS_FILE = SCRIPT_DIR / "requirements.txt"

# Action 229: data now lives under DATA_ROOT (outside PROJECT_ROOT), so
# Path.relative_to(PROJECT_ROOT) would raise — use the safe display helper.
try:
    from script.storage_paths import safe_relpath
except ImportError:
    from storage_paths import safe_relpath

# ================================
# VIRTUAL ENVIRONMENT BOOTSTRAP
# ================================
def get_venv_python() -> Path:
    """Get the path to the Python executable in the virtual environment."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    else:
        return VENV_DIR / "bin" / "python"

def get_venv_pip() -> Path:
    """Get the path to pip in the virtual environment."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "pip.exe"
    else:
        return VENV_DIR / "bin" / "pip"

def is_running_in_venv() -> bool:
    """Check if we're currently running inside the virtual environment."""
    venv_python = get_venv_python()
    return venv_python.exists() and Path(sys.executable).resolve() == venv_python.resolve()

def create_venv():
    """Create a new virtual environment."""
    print("\n🔧 Creating virtual environment (.venv)...")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"   ❌ Failed to create virtual environment: {result.stderr}")
        sys.exit(1)
    print("   ✅ Virtual environment created")

def install_requirements():
    """Install requirements in the virtual environment."""
    pip_path = get_venv_pip()
    
    if not REQUIREMENTS_FILE.exists():
        print(f"   ⚠️  requirements.txt not found at {REQUIREMENTS_FILE}")
        return
    
    print("\n📦 Installing dependencies (this may take a few minutes)...")
    print(f"   📄 Reading from: {REQUIREMENTS_FILE.name}")
    
    # Upgrade pip first
    subprocess.run(
        [str(pip_path), "install", "--upgrade", "pip"],
        capture_output=True,
        text=True
    )
    
    # Install requirements
    result = subprocess.run(
        [str(pip_path), "install", "-r", str(REQUIREMENTS_FILE)],
        capture_output=False,  # Show output for progress
        text=True
    )
    
    if result.returncode != 0:
        print("   ❌ Some packages failed to install. Check errors above.")
    else:
        print("   ✅ All dependencies installed successfully")

def ensure_venv_and_rerun():
    """
    Ensure virtual environment exists with dependencies, then re-run this script inside it.
    This function only returns if we're already running in the venv.
    """
    venv_python = get_venv_python()
    
    # If already running in venv, continue normally
    if is_running_in_venv():
        return
    
    # Check if venv exists
    if not VENV_DIR.exists():
        print("\n" + "=" * 60)
        print("🐍 VIRTUAL ENVIRONMENT SETUP")
        print("=" * 60)
        print(f"   No virtual environment found at: {VENV_DIR}")
        
        create_venv()
        install_requirements()
        
        print("\n" + "=" * 60)
    
    elif not venv_python.exists():
        # Venv folder exists but is corrupted
        print("\n⚠️  Virtual environment appears corrupted. Recreating...")
        import shutil
        shutil.rmtree(VENV_DIR)
        create_venv()
        install_requirements()
    
    # Re-run this script using the venv Python
    print(f"\n🔄 Restarting with virtual environment...")
    print("-" * 60)
    
    # Pass all original arguments
    result = subprocess.run(
        [str(venv_python)] + sys.argv,
        cwd=str(SCRIPT_DIR)
    )
    sys.exit(result.returncode)

# ================================
# BOOTSTRAP: Ensure venv before anything else
# ================================
ensure_venv_and_rerun()

# Add script directory to path for imports
sys.path.insert(0, str(SCRIPT_DIR))

# ================================
# IMPORT LOCAL MODULES
# ================================
try:
    from offer_extractor import extract_offer_text, save_offer_to_session, TEXT_EXTENSIONS, IMAGE_EXTENSIONS, EXCEL_EXTENSIONS
    from cv_data_finder import (
        find_all_cv_sources, get_latest_cv_source, 
        copy_cvs_to_session, display_cv_sources, CVSource
    )
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Required modules not available: {e}")
    print("   Please install dependencies: pip install -r requirements.txt\n")
    # Define fallbacks
    TEXT_EXTENSIONS = {'.txt', '.md', '.text'}
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp'}
    EXCEL_EXTENSIONS = {'.xlsx', '.xls', '.xlsm'}
    extract_offer_text = None
    save_offer_to_session = None
    find_all_cv_sources = None
    MODULES_AVAILABLE = False

# ================================
# INPUT TYPE DETECTION
# ================================
def detect_input_type(path: Path) -> str:
    """
    Detect if the input is a CV folder or a job offer file.
    
    Returns:
        'cv_folder', 'offer_text', 'offer_image', 'offer_excel', or 'unknown'
    """
    if path.is_dir():
        # Check if it contains CVs (PDF/DOCX files)
        cv_files = list(path.glob("*.pdf")) + list(path.glob("*.docx"))
        if cv_files:
            return 'cv_folder'
        return 'empty_folder'
    
    elif path.is_file():
        suffix = path.suffix.lower()
        if suffix in TEXT_EXTENSIONS:
            return 'offer_text'
        elif suffix in IMAGE_EXTENSIONS:
            return 'offer_image'
        elif suffix in EXCEL_EXTENSIONS:
            return 'offer_excel'
        else:
            return 'unknown_file'
    
    return 'unknown'

# ================================
# WORKFLOW 1: CV FOLDER MODE (Original Pipeline)
# ================================
def run_cv_folder_workflow(cv_folder: Path, session_id: str):
    """
    Run the original extraction → matching → final result pipeline.
    
    Args:
        cv_folder: Path to folder containing CV files
        session_id: Session ID for this run
    """
    # Check required modules
    if not MODULES_AVAILABLE or extract_offer_text is None:
        print("\n❌ ERROR: Required modules are not available.")
        print("   Please install dependencies with:")
        print("   pip install -r requirements.txt")
        return
    
    print("\n" + "=" * 70)
    print("🚀 CV FOLDER MODE - Full Extraction Pipeline")
    print("=" * 70)
    print(f"📂 CV Folder: {cv_folder}")
    print(f"🆔 Session ID: {session_id}")
    print("=" * 70)
    
    # Step 1: Prompt for job offer file
    print("\n📄 Step 1: Job Offer Selection")
    print("-" * 40)
    
    while True:
        offer_input = input("   Enter path to job offer file: ").strip().strip('"').strip("'")
        
        if not offer_input:
            print("   ❌ Path cannot be empty\n")
            continue
        
        offer_path = Path(offer_input)
        
        if not offer_path.exists():
            print(f"   ❌ File not found: {offer_path}\n")
            continue
        
        if not offer_path.is_file():
            print(f"   ❌ Not a file: {offer_path}\n")
            continue
        
        break
    
    # Extract offer text
    success, text, method = extract_offer_text(offer_path)
    if not success:
        print(f"   ❌ Failed to extract offer text: {text}")
        return
    print(f"   ✅ Extracted {len(text):,} characters using {method}")
        
    # Save extracted text
    offer_path = save_offer_to_session(text, session_id, offer_path.name)
    print(f"   💾 Saved to: {safe_relpath(offer_path)}")
    
    print(f"   ✅ Job offer: {offer_path.name}")
    
    # Step 2: Run extraction script
    print("\n📦 Step 2: CV Extraction & Validation")
    print("-" * 40)
    
    extraction_cmd = [
        sys.executable, 
        str(SCRIPT_DIR / "01_extraction_and_validation.py"),
        "--session", session_id,
        "--input", str(cv_folder),
        "--offer", str(offer_path)
    ]
    
    result = subprocess.run(extraction_cmd, cwd=str(PROJECT_ROOT))
    
    if result.returncode != 0:
        print("\n⚠️  Extraction completed with issues. Continuing to matching...")
    
    # Step 3: Run matcher script
    print("\n🎯 Step 3: CV-Job Matching")
    print("-" * 40)
    
    matcher_cmd = [sys.executable, str(SCRIPT_DIR / "matcher.py"), session_id]
    subprocess.run(matcher_cmd, cwd=str(PROJECT_ROOT))
    
    # Step 4: Run final result script
    print("\n📊 Step 4: Final Results Aggregation")
    print("-" * 40)
    
    final_cmd = [sys.executable, str(SCRIPT_DIR / "final_result.py")]
    subprocess.run(final_cmd, cwd=str(PROJECT_ROOT))
    
    # Step 5: Generate formatted CVs
    print("\n📝 Step 5: CV Formatting & Generation")
    print("-" * 40)
    
    cv_gen_cmd = [sys.executable, str(SCRIPT_DIR / "cv_generator.py"), "--session", session_id]
    subprocess.run(cv_gen_cmd, cwd=str(PROJECT_ROOT))
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ PIPELINE COMPLETE")
    print("=" * 70)
    print(f"🆔 Session: {session_id}")
    print(f"📂 Results:   data/matching_results/{session_id}/")
    print(f"📂 Final:     data/final_result/{session_id}/")
    print(f"📂 Formatted: data/formatted_cv/{session_id}/")
    print("=" * 70)
    
    # Offer to archive
    archive_choice = input("\n📦 Would you like to archive this session? (y/n) [y]: ").strip().lower()
    if archive_choice != 'n':
        archive_cmd = [sys.executable, str(SCRIPT_DIR / "archiver.py"), "--session", session_id]
        subprocess.run(archive_cmd, cwd=str(PROJECT_ROOT))

# ================================
# WORKFLOW 2: JOB OFFER MODE (Reuse Existing CVs)
# ================================
def run_offer_workflow(offer_path: Path, session_id: str):
    """
    Run the offer-first workflow using existing extracted CVs.
    
    Args:
        offer_path: Path to job offer file (text or image)
        session_id: Session ID for this run
    """
    # Check if required modules are available
    if not find_all_cv_sources or not extract_offer_text:
        print("\n❌ Job Offer mode requires additional modules.")
        print("   Ensure offer_extractor.py and cv_data_finder.py exist.\n")
        return
    
    print("\n" + "=" * 70)
    print("🎯 JOB OFFER MODE - Reuse Existing CVs")
    print("=" * 70)
    print(f"📄 Job Offer: {offer_path.name}")
    print(f"🆔 Session ID: {session_id}")
    print("=" * 70)
    
    # Step 1: Extract offer text (if image or Excel)
    print("\n📄 Step 1: Job Offer Processing")
    print("-" * 40)
    
    offer_type = detect_input_type(offer_path)
    
    if offer_type == 'offer_image':
        print(f"   🖼️  Image detected, extracting text...")
        
        # Auto-extract using OCR first, then Vision as fallback
        success, text, method = extract_offer_text(offer_path, prefer_vision=False)
        
        if not success:
            print(f"\n   ❌ Failed to extract offer text: {text}")
            return
        
        print(f"   ✅ Extracted {len(text):,} characters using {method}")
        offer_text = text
    
    elif offer_type == 'offer_excel':
        print(f"   📊 Excel file detected, extracting text...")
        
        success, text, method = extract_offer_text(offer_path)
        
        if not success:
            print(f"\n   ❌ Failed to extract offer text: {text}")
            return
        
        print(f"   ✅ Extracted {len(text):,} characters from Excel")
        offer_text = text
    
    else:
        # Text file - read directly
        try:
            with open(offer_path, 'r', encoding='utf-8') as f:
                offer_text = f.read().strip()
            print(f"   ✅ Loaded {len(offer_text):,} characters")
        except Exception as e:
            print(f"   ❌ Failed to read offer file: {e}")
            return
    
    # Save offer to session directory
    saved_offer_path = save_offer_to_session(offer_text, session_id, offer_path.name)
    
    # Step 2: Find existing CV sources
    print("\n📂 Step 2: Finding Existing CV Data")
    print("-" * 40)
    
    sources = find_all_cv_sources()
    
    if not sources:
        print("   ❌ No existing CV data found!")
        print("   You need to run the full pipeline at least once to extract CVs.")
        print("\n   Would you like to:")
        print("   1. Provide a CV folder to extract (full pipeline)")
        print("   2. Cancel")
        
        choice = input("   Choice (1/2): ").strip()
        
        if choice == '1':
            cv_folder = input("   Enter path to CV folder: ").strip().strip('"').strip("'")
            if cv_folder and Path(cv_folder).is_dir():
                run_cv_folder_workflow(Path(cv_folder), session_id)
            else:
                print("   ❌ Invalid folder path")
        return
    
    print(f"   ✅ Found {len(sources)} session(s) with extracted CVs:")
    display_cv_sources(sources)
    
    # Let user select source or use latest
    print("   Options:")
    print("   • Enter number to select a session")
    print("   • Press Enter to use the latest session")
    print("   • Type 'all' to combine all unique CVs")
    
    selection = input("\n   → Selection [latest]: ").strip().lower()
    
    selected_source = None
    
    if selection == 'all':
        # Combine all unique CVs (advanced feature)
        print("\n   📦 Combining unique CVs from all sessions...")
        # For now, just use latest - could implement unique CV merging later
        selected_source = sources[0]
        print(f"   ℹ️  Using latest session for now: {selected_source.session_id}")
    elif selection == '' or selection == 'latest':
        selected_source = sources[0]
    else:
        try:
            idx = int(selection) - 1
            if 0 <= idx < len(sources):
                selected_source = sources[idx]
            else:
                print(f"   ❌ Invalid selection. Using latest.")
                selected_source = sources[0]
        except ValueError:
            print(f"   ❌ Invalid input. Using latest.")
            selected_source = sources[0]
    
    print(f"\n   ✅ Using CV source: {selected_source}")
    
    # Step 3: Copy CVs to new session
    print("\n📋 Step 3: Preparing CVs for Matching")
    print("-" * 40)
    
    copied_count, target_dir = copy_cvs_to_session(selected_source, session_id)
    print(f"   ✅ Copied {copied_count} CV(s) to session {session_id}")
    
    # Step 4: Run matcher
    print("\n🎯 Step 4: CV-Job Matching")
    print("-" * 40)
    
    matcher_cmd = [sys.executable, str(SCRIPT_DIR / "matcher.py"), session_id]
    subprocess.run(matcher_cmd, cwd=str(PROJECT_ROOT))
    
    # Step 5: Run final result
    print("\n📊 Step 5: Final Results Aggregation")
    print("-" * 40)
    
    final_cmd = [sys.executable, str(SCRIPT_DIR / "final_result.py")]
    subprocess.run(final_cmd, cwd=str(PROJECT_ROOT))
    
    # Step 6: Generate formatted CVs
    print("\n📝 Step 6: CV Formatting & Generation")
    print("-" * 40)
    
    cv_gen_cmd = [sys.executable, str(SCRIPT_DIR / "cv_generator.py"), "--session", session_id]
    subprocess.run(cv_gen_cmd, cwd=str(PROJECT_ROOT))
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ MATCHING COMPLETE")
    print("=" * 70)
    print(f"🆔 Session: {session_id}")
    print(f"📄 Offer: {offer_path.name}")
    print(f"📂 CVs from: {selected_source.session_id} ({copied_count} candidates)")
    print(f"📂 Results:   data/matching_results/{session_id}/")
    print(f"📂 Final:     data/final_result/{session_id}/")
    print(f"📂 Formatted: data/formatted_cv/{session_id}/")
    print("=" * 70)
    
    # Offer to archive
    archive_choice = input("\n📦 Would you like to archive this session? (y/n) [y]: ").strip().lower()
    if archive_choice != 'n':
        archive_cmd = [sys.executable, str(SCRIPT_DIR / "archiver.py"), "--session", session_id]
        subprocess.run(archive_cmd, cwd=str(PROJECT_ROOT))

# ================================
# INTERACTIVE MODE SELECTION
# ================================
def interactive_mode():
    """
    Interactive mode that prompts user to choose workflow mode first.
    """
    print("\n" + "=" * 70)
    print("🚀 CV PROCESSING PIPELINE")
    print("=" * 70)
    print("\nWelcome! Please choose your workflow mode:\n")
    print("  [1] 📂 New CVs + Job Offer")
    print("      Extract CVs from folder → Match against job offer → Rank")
    print("")
    print("  [2] 📄 Job Offer Only (reuse existing CVs)")
    print("      Use already extracted CVs → Match against new job offer → Rank")
    print("")
    print("  [Q] Exit")
    print("")
    print("=" * 70)
    
    # Prompt for mode selection
    while True:
        mode_choice = input("\n→ Select mode (1/2/Q): ").strip().lower()
        
        if mode_choice in ['q', 'quit', 'exit']:
            print("\n👋 Goodbye!\n")
            return
        
        if mode_choice in ['1', '2']:
            break
        
        print("   ❌ Invalid choice. Please enter 1, 2, or Q.\n")
    
    # Generate session ID
    try:
        SESSION_ID = datetime.now().strftime("%Y%m%d%H%M%S")
        print(f"\n🆔 Session ID: {SESSION_ID}")
    except Exception as e:
        print(f"\n⚠️  Could not generate session ID: {e}")
        SESSION_ID = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Execute chosen workflow
    if mode_choice == '1':
        # Mode 1: CV Folder workflow
        print("\n" + "-" * 70)
        print("📂 MODE 1: New CVs + Job Offer")
        print("-" * 70)
        
        # Prompt for CV folder
        while True:
            cv_input = input("\n📁 Enter path to CV folder: ").strip().strip('"').strip("'")
            
            if not cv_input:
                print("   ❌ Path cannot be empty")
                continue
            
            cv_folder = Path(cv_input)
            
            if not cv_folder.exists():
                print(f"   ❌ Folder not found: {cv_folder}")
                continue
            
            if not cv_folder.is_dir():
                print(f"   ❌ Not a folder: {cv_folder}")
                continue
            
            # Check for CV files
            cv_files = list(cv_folder.glob("*.pdf")) + list(cv_folder.glob("*.docx"))
            if not cv_files:
                print(f"   ⚠️  No PDF/DOCX files found in: {cv_folder}")
                proceed = input("   Continue anyway? (y/n): ").strip().lower()
                if proceed != 'y':
                    continue
            else:
                print(f"   ✅ Found {len(cv_files)} CV file(s)")
            
            break
        
        run_cv_folder_workflow(cv_folder, SESSION_ID)
        
    elif mode_choice == '2':
        # Mode 2: Job Offer workflow (reuse CVs)
        print("\n" + "-" * 70)
        print("📄 MODE 2: Job Offer Only (reuse existing CVs)")
        print("-" * 70)
        
        # Check if we have existing CVs first
        if find_all_cv_sources:
            sources = find_all_cv_sources()
            if not sources:
                print("\n   ⚠️  No existing extracted CVs found!")
                print("   You need to run Mode 1 at least once to extract CVs first.")
                print("\n   Would you like to switch to Mode 1? (y/n): ", end="")
                if input().strip().lower() in ['y', 'yes']:
                    interactive_mode()  # Restart
                return
            else:
                print(f"\n   ✅ Found {sum(s.cv_count for s in sources)} CVs across {len(sources)} session(s)")
        
        # Prompt for job offer file
        while True:
            offer_input = input("\n📄 Enter path to job offer file (text or image): ").strip().strip('"').strip("'")
            
            if not offer_input:
                print("   ❌ Path cannot be empty")
                continue
            
            offer_path = Path(offer_input)
            
            if not offer_path.exists():
                print(f"   ❌ File not found: {offer_path}")
                continue
            
            if not offer_path.is_file():
                print(f"   ❌ Not a file: {offer_path}")
                continue
            
            # Validate file type
            offer_type = detect_input_type(offer_path)
            if offer_type == 'offer_text':
                print(f"   ✅ Text file detected")
            elif offer_type == 'offer_image':
                print(f"   ✅ Image file detected (will use OCR/Vision)")
            elif offer_type == 'offer_excel':
                print(f"   ✅ Excel file detected")
            else:
                print(f"   ⚠️  Unknown file type: {offer_path.suffix}")
                print(f"   ℹ️  Supported: .txt, .md, .png, .jpg, .jpeg, .xlsx, .xls, .xlsm")
                proceed = input("   Try to process anyway? (y/n): ").strip().lower()
                if proceed != 'y':
                    continue
            
            break
        
        run_offer_workflow(offer_path, SESSION_ID)

# ================================
# COMMAND LINE ARGUMENTS
# ================================
def parse_args():
    """Parse command line arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="CV Processing Pipeline - Unified Entry Point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           # Interactive mode
  python main.py --cv-folder ./cvs         # CV folder mode
  python main.py --offer ./job_offer.txt   # Job offer mode (reuse CVs)
  python main.py --offer ./offer.png       # Job offer from image
  
Modes:
  CV Folder Mode:  Extract CVs → Match → Final Result
  Job Offer Mode:  Reuse existing extracted CVs → Match → Final Result
        """
    )
    
    parser.add_argument(
        '--cv-folder', '--cvs', '-c',
        type=str,
        help='Path to folder containing CV files (PDF/DOCX)'
    )
    
    parser.add_argument(
        '--offer', '-o',
        type=str,
        help='Path to job offer file (text or image)'
    )
    
    parser.add_argument(
        '--session', '-s',
        type=str,
        help='Session ID (auto-generated if not provided)'
    )
    
    return parser.parse_args()

# ================================
# ENTRY POINT
# ================================
if __name__ == "__main__":
    args = parse_args()
    
    # Generate or use provided session ID
    SESSION_ID = args.session or datetime.now().strftime("%Y%m%d%H%M%S")
    
    try:
        if args.cv_folder:
            # CV Folder mode via CLI
            cv_folder = Path(args.cv_folder)
            if not cv_folder.exists() or not cv_folder.is_dir():
                print(f"❌ CV folder not found: {cv_folder}")
                sys.exit(1)
            run_cv_folder_workflow(cv_folder, SESSION_ID)
            
        elif args.offer:
            # Job Offer mode via CLI
            offer_path = Path(args.offer)
            if not offer_path.exists() or not offer_path.is_file():
                print(f"❌ Offer file not found: {offer_path}")
                sys.exit(1)
            run_offer_workflow(offer_path, SESSION_ID)
            
        else:
            # Interactive mode
            interactive_mode()
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user\n")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}\n")
        import traceback
        traceback.print_exc()
    finally:
        print("👋 Pipeline terminated\n")