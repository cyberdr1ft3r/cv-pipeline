# script/offer_extractor.py

"""
Job Offer Extractor Module
Extracts text from job offer files (text or images via OCR/LLM Vision).

This module supports two extraction modes:
1. AGENTIC MODE (default): Uses LLM-based intelligent extraction
2. LIBRARY MODE (fallback): Uses traditional Python libraries

Set EXTRACTION_MODE in config or use_agentic parameter to control behavior.
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import base64
from openai import OpenAI
from dotenv import load_dotenv
import re

# Excel support
try:
    import openpyxl
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

# Try to import xlrd for old .xls files
try:
    import xlrd
    XLRD_AVAILABLE = True
except ImportError:
    XLRD_AVAILABLE = False

# ================================
# LOAD ENV
# ================================
ENV_PATH = Path(__file__).resolve().parents[1] / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise RuntimeError(f"❌ OPENROUTER_API_KEY is not defined. Expected in {ENV_PATH}")

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ================================
# LOAD CONFIG
# ================================
CONFIG_PATH = PROJECT_ROOT / "config" / "config_yaml.yaml"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# Action 227: offer files resolve under DATA_ROOT via the shared resolver.
# This module is imported by the service (from script.offer_extractor ...) and
# also run within the script context, so the dual import covers both.
try:
    from script.storage_paths import CURRENT_DIR, safe_relpath
except ImportError:
    from storage_paths import CURRENT_DIR, safe_relpath

OFFER_DIR_BASE = CURRENT_DIR / "offer"

# Supported file extensions
TEXT_EXTENSIONS = {'.txt', '.md', '.text'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp'}
EXCEL_EXTENSIONS = {'.xlsx', '.xls', '.xlsm'}

# OpenAI client for vision API
client = OpenAI(base_url=CONFIG["api"]["base_url"], api_key=OPENROUTER_API_KEY)

# ================================
# LOGGING
# ================================
def setup_logging():
    """Setup console logging"""
    logger = logging.getLogger("OfferExtractor")
    logger.setLevel(logging.DEBUG)
    logger.handlers = []
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    
    logger.addHandler(console_handler)
    return logger

logger = setup_logging()

# ================================
# FILE TYPE DETECTION
# ================================
def detect_file_type(file_path: Path) -> str:
    """
    Detect if file is a text file, image, or Excel file.
    
    Returns:
        'text', 'image', 'excel', or 'unknown'
    """
    suffix = file_path.suffix.lower()
    
    if suffix in TEXT_EXTENSIONS:
        return 'text'
    elif suffix in IMAGE_EXTENSIONS:
        return 'image'
    elif suffix in EXCEL_EXTENSIONS:
        return 'excel'
    else:
        # Try to detect by content
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)
                # Check for common image signatures
                if header[:8] == b'\x89PNG\r\n\x1a\n':  # PNG
                    return 'image'
                elif header[:2] == b'\xff\xd8':  # JPEG
                    return 'image'
                elif header[:6] in (b'GIF87a', b'GIF89a'):  # GIF
                    return 'image'
                elif header[:4] == b'RIFF':  # WEBP
                    return 'image'
            # Try to read as text
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read(1000)
            return 'text'
        except (UnicodeDecodeError, IOError):
            return 'unknown'

# ================================
# OCR ARTIFACT CLEANING  
# ================================
def clean_ocr_artifacts(text: str) -> str:
    """
    Remove common OCR emoji artifacts from text.
    """
    # Remove artifacts at the start of lines (including =, ©, &, numbers, §)
    text = re.sub(r'^[=©&§®@*\d\s]+', '', text, flags=re.MULTILINE)
    
    # Remove standalone symbols between pipes or spaces
    text = re.sub(r'\|\s*[&®]\s*', '| ', text)
    
    # Remove ® symbol when it appears before capital letters
    text = re.sub(r'®\s*(?=[A-Z])', '', text)
    
    # Clean up multiple spaces (but NOT newlines) - only on same line
    text = re.sub(r'[ \t]+', ' ', text) 
    
    # Clean up lines with only symbols
    lines = [line for line in text.split('\n') if not re.match(r'^[=©&§®@*\s]+$', line)]
    text = '\n'.join(lines)
    
    return text.strip()

# ================================
# TEXT FILE EXTRACTION
# ================================
def extract_from_text_file(file_path: Path) -> Tuple[bool, str]:
    """
    Extract text from a text file.
    
    Returns:
        (success, text_or_error)
    """
    try:
        # Try different encodings
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    text = f.read().strip()
                    
                if text:
                    return True, text
            except UnicodeDecodeError:
                continue
        
        return False, "Could not decode text file with any supported encoding"
        
    except Exception as e:
        return False, f"Failed to read text file: {e}"

# ================================
# EXCEL FILE EXTRACTION
# ================================
def detect_content_area_openpyxl(sheet) -> Optional[tuple]:
    """
    Detect main content area in openpyxl worksheet.
    Returns (min_row, max_row, min_col, max_col) or None.
    """
    max_col = sheet.max_column
    max_row = sheet.max_row
    
    # Analyze column density
    col_density = {}
    for col_idx in range(1, max_col + 1):
        non_empty_count = 0
        for row_idx in range(1, max_row + 1):
            cell_value = sheet.cell(row=row_idx, column=col_idx).value
            if cell_value is not None and str(cell_value).strip():
                non_empty_count += 1
        col_density[col_idx] = non_empty_count
    
    # Find columns with content
    content_cols = []
    for col_idx in range(1, max_col + 1):
        if col_density[col_idx] > 0:
            content_cols.append(col_idx)
    
    if not content_cols:
        return None
    
    # Detect main contiguous group
    main_content_cols = []
    for i, col in enumerate(content_cols):
        if i == 0:
            main_content_cols.append(col)
        else:
            gap = col - content_cols[i-1]
            if gap <= 3:
                main_content_cols.append(col)
            else:
                break
    
    if not main_content_cols:
        return None
    
    min_col = min(main_content_cols)
    max_col = max(main_content_cols)
    
    # Find rows with content in this range
    content_rows = []
    for row_idx in range(1, max_row + 1):
        has_content = False
        for col_idx in range(min_col, max_col + 1):
            cell_value = sheet.cell(row=row_idx, column=col_idx).value
            if cell_value is not None and str(cell_value).strip():
                has_content = True
                break
        if has_content:
            content_rows.append(row_idx)
    
    if not content_rows:
        return None
    
    min_row = min(content_rows)
    max_row = max(content_rows)
    
    return (min_row, max_row, min_col, max_col)

def detect_content_area_xlrd(sheet) -> Optional[tuple]:
    """
    Detect main content area in xlrd worksheet.
    Returns (min_row, max_row, min_col, max_col) or None.
    """
    max_col = sheet.ncols
    max_row = sheet.nrows
    
    # Analyze column density
    col_density = {}
    for col_idx in range(max_col):
        non_empty_count = 0
        for row_idx in range(max_row):
            cell_value = sheet.cell_value(row_idx, col_idx)
            if cell_value is not None and str(cell_value).strip():
                non_empty_count += 1
        col_density[col_idx] = non_empty_count
    
    # Find columns with content
    content_cols = []
    for col_idx in range(max_col):
        if col_density[col_idx] > 0:
            content_cols.append(col_idx)
    
    if not content_cols:
        return None
    
    # Detect main contiguous group
    main_content_cols = []
    for i, col in enumerate(content_cols):
        if i == 0:
            main_content_cols.append(col)
        else:
            gap = col - content_cols[i-1]
            if gap <= 3:
                main_content_cols.append(col)
            else:
                break
    
    if not main_content_cols:
        return None
    
    min_col = min(main_content_cols)
    max_col = max(main_content_cols)
    
    # Find rows with content in this range
    content_rows = []
    for row_idx in range(max_row):
        has_content = False
        for col_idx in range(min_col, max_col + 1):
            cell_value = sheet.cell_value(row_idx, col_idx)
            if cell_value is not None and str(cell_value).strip():
                has_content = True
                break
        if has_content:
            content_rows.append(row_idx)
    
    if not content_rows:
        return None
    
    min_row = min(content_rows)
    max_row = max(content_rows)
    
    return (min_row, max_row, min_col, max_col)

# Excel file compatibility
def detect_content_area(sheet):
    """
    Backward compatibility wrapper.
    Auto-detects whether it's an openpyxl or xlrd sheet.
    """
    if hasattr(sheet, 'max_column'):  # openpyxl
        return detect_content_area_openpyxl(sheet)
    elif hasattr(sheet, 'ncols'):  # xlrd
        return detect_content_area_xlrd(sheet)
    else:
        return None

def extract_from_xlsx(file_path: Path) -> Tuple[bool, str]:
    """
    Extract text from modern Excel files (.xlsx, .xlsm) using openpyxl.
    """
    try:
        # Load the workbook (data_only=True to get calculated values)
        wb = openpyxl.load_workbook(file_path, data_only=True)
        
        all_text_parts = []
        
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            sheet_text = []
            
            # Add sheet name as header if multiple sheets
            if len(wb.sheetnames) > 1:
                sheet_text.append(f"\n{'='*50}")
                sheet_text.append(f"Sheet: {sheet_name}")
                sheet_text.append(f"{'='*50}\n")
            
            # Automatically detect the main content area
            content_area = detect_content_area_openpyxl(sheet)
            
            if content_area is None:
                continue
            
            min_row, max_row, min_col, max_col = content_area
            
            # Track merged cells to avoid duplicates
            merged_ranges = sheet.merged_cells.ranges
            merged_cells_values = {}
            
            # Get values from merged cells (use top-left cell value)
            for merged_range in merged_ranges:
                m_min_col, m_min_row, m_max_col, m_max_row = merged_range.bounds
                cell_value = sheet.cell(row=m_min_row, column=m_min_col).value
                if cell_value:
                    for row in range(m_min_row, m_max_row + 1):
                        for col in range(m_min_col, m_max_col + 1):
                            if row == m_min_row and col == m_min_col:
                                merged_cells_values[(row, col)] = str(cell_value)
                            else:
                                merged_cells_values[(row, col)] = None
            
            # Iterate through rows in the detected content area
            current_section = []
            for row_idx in range(min_row, max_row + 1):
                row_values = []
                
                for col_idx in range(min_col, max_col + 1):
                    cell = sheet.cell(row=row_idx, column=col_idx)
                    
                    if (row_idx, col_idx) in merged_cells_values:
                        cell_value = merged_cells_values[(row_idx, col_idx)]
                    else:
                        cell_value = cell.value
                    
                    if cell_value is not None and str(cell_value).strip():
                        row_values.append(str(cell_value).strip())
                
                if row_values:
                    row_text = " | ".join(row_values)
                    current_section.append(row_text)
                elif current_section:
                    sheet_text.extend(current_section)
                    sheet_text.append("")
                    current_section = []
            
            if current_section:
                sheet_text.extend(current_section)
            
            if sheet_text:
                all_text_parts.extend(sheet_text)
        
        wb.close()
        
        full_text = "\n".join(all_text_parts)
        
        if full_text.strip():
            return True, full_text.strip()
        else:
            return False, "Excel file contains no text data"
        
    except Exception as e:
        return False, f"Failed to read Excel file: {e}"

def extract_from_xls(file_path: Path) -> Tuple[bool, str]:
    """
    Extract text from old Excel files (.xls) using xlrd.
    """
    if not XLRD_AVAILABLE:
        return False, "xlrd not installed. Run: pip install xlrd"
    
    try:
        # Open the workbook
        workbook = xlrd.open_workbook(file_path, formatting_info=False)
        
        all_text_parts = []
        
        for sheet_idx in range(workbook.nsheets):
            sheet = workbook.sheet_by_index(sheet_idx)
            sheet_text = []
            
            # Add sheet name as header if multiple sheets
            if workbook.nsheets > 1:
                sheet_text.append(f"\n{'='*50}")
                sheet_text.append(f"Sheet: {sheet.name}")
                sheet_text.append(f"{'='*50}\n")
            
            # Automatically detect the main content area
            content_area = detect_content_area_xlrd(sheet)
            
            if content_area is None:
                continue
            
            min_row, max_row, min_col, max_col = content_area
            
            # Get merged cells info
            merged_cells = {}
            if hasattr(sheet, 'merged_cells'):
                for crange in sheet.merged_cells:
                    rlo, rhi, clo, chi = crange
                    # Get value from top-left cell
                    cell_value = sheet.cell_value(rlo, clo)
                    for row in range(rlo, rhi):
                        for col in range(clo, chi):
                            if row == rlo and col == clo:
                                merged_cells[(row, col)] = cell_value
                            else:
                                merged_cells[(row, col)] = None
            
            # Iterate through rows in the detected content area
            current_section = []
            for row_idx in range(min_row, max_row + 1):
                row_values = []
                
                for col_idx in range(min_col, max_col + 1):
                    # Check if this cell is part of a merged range
                    if (row_idx, col_idx) in merged_cells:
                        cell_value = merged_cells[(row_idx, col_idx)]
                    else:
                        cell_value = sheet.cell_value(row_idx, col_idx)
                    
                    # Convert cell value to string
                    if cell_value is not None and cell_value != '':
                        # Handle different cell types
                        if isinstance(cell_value, float):
                            # Check if it's actually an integer
                            if cell_value == int(cell_value):
                                cell_str = str(int(cell_value))
                            else:
                                cell_str = str(cell_value)
                        else:
                            cell_str = str(cell_value)
                        
                        cell_str = cell_str.strip()
                        if cell_str:
                            row_values.append(cell_str)
                
                if row_values:
                    row_text = " | ".join(row_values)
                    current_section.append(row_text)
                elif current_section:
                    sheet_text.extend(current_section)
                    sheet_text.append("")
                    current_section = []
            
            if current_section:
                sheet_text.extend(current_section)
            
            if sheet_text:
                all_text_parts.extend(sheet_text)
        
        full_text = "\n".join(all_text_parts)
        
        if full_text.strip():
            return True, full_text.strip()
        else:
            return False, "Excel file contains no text data"
        
    except Exception as e:
        return False, f"Failed to read .xls file: {e}"

def extract_from_excel_file(file_path: Path) -> Tuple[bool, str]:
    """
    Extract text from an Excel file (.xlsx, .xls, .xlsm).
    Automatically detects main content area and ignores isolated columns.
    Supports both old (.xls) and new (.xlsx, .xlsm) formats.
    
    Args:
        file_path: Path to the Excel file
    
    Returns:
        (success, text_or_error): Tuple with success status and extracted text or error message
    """
    file_ext = file_path.suffix.lower()
    
    # Route to appropriate handler based on file extension
    if file_ext == '.xls':
        return extract_from_xls(file_path)
    elif file_ext in ['.xlsx', '.xlsm']:
        return extract_from_xlsx(file_path)
    else:
        return False, f"Unsupported file format: {file_ext}. Supported formats: .xls, .xlsx, .xlsm"

# ================================
# IMAGE OCR EXTRACTION (Local)
# ================================
# def preprocess_image_for_ocr(image):
#     """Optimize image for better OCR results"""
#     # Convert to grayscale
#     image = image.convert('L')
    
#     # Increase contrast
#     enhancer = ImageEnhance.Contrast(image)
#     image = enhancer.enhance(2.0)
    
#     # Sharpen
#     image = image.filter(ImageFilter.SHARPEN)
    
#     # Upscale if too small
#     width, height = image.size
#     if width < 1000:
#         scale = 1000 / width
#         new_size = (int(width * scale), int(height * scale))
#         image = image.resize(new_size, Image.Resampling.LANCZOS)
    
#     return image

def extract_from_image_ocr(file_path: Path) -> Tuple[bool, str]:
    """
    Extract text from image using local OCR (Tesseract).
    
    Returns:
        (success, text_or_error)
    """
    try:
        # Check if Tesseract is available
        try:
            pytesseract.pytesseract.tesseract_cmd = CONFIG.get("paths", {}).get("tesseract_cmd") or "tesseract"
            version = pytesseract.get_tesseract_version()
            logger.debug(f"   Using Tesseract version: {version}")
        except Exception:
            return False, "Tesseract OCR not installed or not in PATH"
        
        # Open and preprocess image
        with Image.open(file_path) as image:
            logger.debug(f"   Original image: {image.mode} {image.size}")
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if 'A' in image.mode else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Preprocess for better OCR
            # image = preprocess_image_for_ocr(image) # preprocessing disabled for actual version
            
            # Extract text with multiple strategies
            text = None
            lang_configs = [None, 'fra', 'eng+fra']
            
            for lang in lang_configs:
                try:
                    if lang:
                        text = pytesseract.image_to_string(image, lang=lang)
                    else:
                        text = pytesseract.image_to_string(image)
                    
                    # Clean OCR artifacts
                    if text:
                        text = clean_ocr_artifacts(text)
                        char_count = len(text.strip())
                        logger.debug(f"   Extracted {char_count} chars with lang={lang or 'default'}")
                    
                    # Accept if we got meaningful text
                    min_length = 50 # Minimum length to consider successful
                    if text and len(text.strip()) > min_length:
                        logger.debug(f"   ✅ OCR successful")
                        return True, text.strip()
                        
                except Exception as lang_error:
                    logger.debug(f"   ⚠️  Config failed (lang={lang}: {lang_error}")
                    continue
            
            # If we got some text but less than threshold
            if text and text.strip():
                logger.debug(f"   ⚠️  Returning short text ({len(text.strip())} chars)")
                return True, text.strip()
            
            return False, "OCR extracted no text from image"
        
    except Exception as e:
        logger.error(f"   ❌ OCR extraction failed: {e}")
        return False, f"OCR extraction failed: {e}"

# ================================
# IMAGE EXTRACTION VIA LLM VISION
# ================================
def extract_from_image_vision(file_path: Path) -> Tuple[bool, str]:
    """
    Extract text from image using LLM Vision API.
    This is more accurate than OCR for complex layouts.
    
    Returns:
        (success, text_or_error)
    """
    try:
        # Encode image as base64
        with open(file_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Determine image type
        suffix = file_path.suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
            '.gif': 'image/gif',
        }
        mime_type = mime_types.get(suffix, 'image/png')
        
        # Use a vision-capable model (free models with vision support)
        vision_models = [
            "nvidia/nemotron-3-nano-30b-a3b:free",  # Free, vision-capable
            "google/gemini-2.0-flash-exp:free",
            "nvidia/nemotron-nano-12b-v2-vl:free",
        ]
        
        last_error = None
        
        prompt = """Please extract and transcribe ALL text from this job offer image.
Maintain the original structure and formatting as much as possible.
Include all details: job title, company, requirements, responsibilities, qualifications, etc.
Output the text in a clean, readable format. Don't add any extra commentary.
If no text is found, respond with 'No text found'."""

        for model in vision_models:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{image_data}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=CONFIG["api"]["vision"]["max_tokens"],
                    temperature=CONFIG["api"]["vision"]["temperature"],
                )

                text = response.choices[0].message.content
                if text and len(text.strip()) > 50:
                    return True, text.strip()
                elif text and text.strip():
                    # Got some text, might be enough
                    return True, text.strip()
                    
            except Exception as model_error:
                last_error = str(model_error)
                logger.debug(f"Vision model {model} failed: {model_error}")
                continue
        
        return False, f"All vision models failed. Last error: {last_error}"
        
    except Exception as e:
        return False, f"Vision extraction failed: {e}"

# ================================
# MAIN EXTRACTION FUNCTION
# ================================

# Try to import agentic extractor
try:
    from agentic_extractor import AgenticExtractor, ExtractionMethod
    AGENTIC_AVAILABLE = True
except ImportError:
    AGENTIC_AVAILABLE = False

# Default extraction mode: 'agentic' or 'library'
DEFAULT_EXTRACTION_MODE = CONFIG.get("extraction", {}).get("mode", "agentic")


def extract_offer_text(
    file_path: Path, 
    prefer_vision: bool = False,
    use_agentic: Optional[bool] = None
) -> Tuple[bool, str, str]:
    """
    Extract job offer text from file (text, image, or Excel).
    
    This function supports two extraction modes:
    1. AGENTIC MODE: Uses LLM-based intelligent extraction with library fallback
    2. LIBRARY MODE: Uses traditional Python libraries (OCR, openpyxl, etc.)
    
    Args:
        file_path: Path to the job offer file
        prefer_vision: (Library mode only) If True, use LLM Vision for images
        use_agentic: Override extraction mode. True=agentic, False=library, None=use default
        
    Returns:
        (success, text_or_error, method_used)
    """
    if not file_path.exists():
        return False, f"File not found: {file_path}", "none"
    
    # Determine extraction mode
    if use_agentic is None:
        use_agentic = DEFAULT_EXTRACTION_MODE == "agentic" and AGENTIC_AVAILABLE
    
    # ===== AGENTIC EXTRACTION MODE =====
    if use_agentic and AGENTIC_AVAILABLE:
        logger.info(f"   🤖 Using AGENTIC extraction mode")
        try:
            extractor = AgenticExtractor()
            result = extractor.extract(file_path)
            if result.success:
                return result.to_tuple()
            logger.warning(f"   ⚠️  Agentic extraction failed: {result.text}")
            logger.info(f"   🔄 Falling back to library extraction...")
            # Fall through to library mode
        except Exception as e:
            logger.warning(f"   ⚠️  Agentic extraction failed: {e}")
            logger.info(f"   🔄 Falling back to library extraction...")
            # Fall through to library mode
    
    # ===== LIBRARY EXTRACTION MODE =====
    logger.info(f"   📚 Using LIBRARY extraction mode")
    return _extract_with_libraries(file_path, prefer_vision)


def _extract_with_libraries(file_path: Path, prefer_vision: bool = False) -> Tuple[bool, str, str]:
    """
    Original library-based extraction (backward compatible).
    
    Args:
        file_path: Path to the job offer file
        prefer_vision: If True, use LLM Vision for images instead of local OCR
        
    Returns:
        (success, text_or_error, method_used)
    """
    file_type = detect_file_type(file_path)
    
    if file_type == 'text':
        logger.info(f"   📄 Detected text file: {file_path.name}")
        success, result = extract_from_text_file(file_path)
        return success, result, "text_file"
    
    elif file_type == 'image':
        logger.info(f"   🖼️  Detected image file: {file_path.name}")
        
        # Try local OCR (Fast and offline)
        logger.info("   🔍 Extracting text using local OCR...")
        success, result = extract_from_image_ocr(file_path)
        if success:
            return True, result, "ocr"
        
        # Fallback to LLM Vision (more reliable, no local dependencies)
        logger.info("   ⚠️ OCR failed, 🤖 Extracting text using AI Vision...")
        success, result = extract_from_image_vision(file_path)
        if success:
            return True, result, "llm_vision"
        
        vision_error = result  # Save the error for reporting
        
        # Both failed - return combined error info
        return False, f"Vision: {vision_error} | OCR: {result}", "failed"
    
    elif file_type == 'excel':
        logger.info(f"   📊 Detected Excel file: {file_path.name}")
        success, result = extract_from_excel_file(file_path)
        return success, result, "excel"
    
    else:
        return False, f"Unknown file type: {file_path.suffix}", "unknown"

# ================================
# SAVE OFFER TO SESSION
# ================================
def save_offer_to_session(offer_text: str, session_id: str, original_filename: str) -> Path:
    """
    Save extracted offer text to session directory.
    
    Args:
        offer_text: The extracted offer text
        session_id: Session ID for organization
        original_filename: Original filename (for naming)
        
    Returns:
        Path to the saved offer file
    """
    session_offer_dir = OFFER_DIR_BASE / session_id
    os.makedirs(session_offer_dir, exist_ok=True)
    
    # Generate output filename (always .txt)
    base_name = Path(original_filename).stem
    output_filename = f"{base_name}.txt"
    output_path = session_offer_dir / output_filename
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(offer_text)
    
    logger.info(f"   💾 Offer saved: data/offer/{session_id}/{output_filename}")
    
    return output_path

# ================================
# INTERACTIVE MODE
# ================================
def interactive_extract():
    """Interactive mode for offer extraction"""
    print("\n" + "=" * 70)
    print("📋 JOB OFFER TEXT EXTRACTOR")
    print("=" * 70)
    print("\nSupported formats:")
    print("  • Text files: .txt, .md")
    print("  • Images: .png, .jpg, .jpeg, .webp, .bmp, .tiff")
    print("  • Excel files: .xlsx, .xls, .xlsm")
    print("")
    print("Extraction: 🤖 Agentic (LLM-based) with 📚 Library fallback")
    print("")
    
    # Get file path
    while True:
        file_input = input("📄 Enter path to job offer file: ").strip().strip('"').strip("'")
        
        if not file_input:
            print("   ❌ Path cannot be empty\n")
            continue
        
        file_path = Path(file_input)
        
        if not file_path.exists():
            print(f"   ❌ File not found: {file_path}\n")
            continue
        
        if not file_path.is_file():
            print(f"   ❌ Not a file: {file_path}\n")
            continue
        
        break
    
    # Extract text (Agentic by default with Library fallback)
    file_type = detect_file_type(file_path)
    print(f"\n⏳ Extracting text from {file_type} file...")
    
    success, result, method = extract_offer_text(file_path)
    
    if success:
        print(f"\n✅ Extraction successful using {method}")
        print(f"   Extracted {len(result):,} characters")
        print("\n" + "-" * 70)
        print("PREVIEW (first 500 characters):")
        print("-" * 70)
        print(result[:500] + ("..." if len(result) > 500 else ""))
        print("-" * 70)
        
        # Optionally save
        save_choice = input("\n💾 Save to session directory? (y/n) [y]: ").strip().lower()
        if save_choice != 'n':
            session_id = datetime.now().strftime("%Y%m%d%H%M%S")
            saved_path = save_offer_to_session(result, session_id, file_path.name)
            print(f"\n✅ Saved to: {safe_relpath(saved_path)}")
    else:
        print(f"\n❌ Extraction failed: {result}")

# ================================
# ENTRY POINT
# ================================
if __name__ == "__main__":
    try:
        interactive_extract()
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
