import os
import mimetypes
import yaml
from typing import List, Optional
from pathlib import Path
from pydantic import BaseModel, validator

try:
    import magic
except ImportError:
    magic = None

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config_yaml.yaml"
with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _CONFIG = yaml.safe_load(_f)

class ValidationError(Exception):
    """Custom validation error"""
    pass

class FileValidator:
    """File validation utilities"""

    ALLOWED_EXTENSIONS = {
        'pdf': ['application/pdf'],
        'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
        'doc': ['application/msword'],
        'txt': ['text/plain'],
        'csv': ['text/csv', 'text/plain', 'application/vnd.ms-excel'],
        'xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
        'xls': ['application/vnd.ms-excel'],
        'xlsm': ['application/vnd.ms-excel.sheet.macroEnabled.12', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
        'png': ['image/png'],
        'jpg': ['image/jpeg'],
        'jpeg': ['image/jpeg'],
        'gif': ['image/gif'],
        'tiff': ['image/tiff'],
        'bmp': ['image/bmp']
    }

    MAX_FILE_SIZE = int(_CONFIG["api"]["pipeline_upload_max_mb"]) * 1024 * 1024

    @classmethod
    def _detect_mime_type(cls, path: Path) -> str:
        """Detect MIME type using libmagic when available, otherwise fall back to mimetypes."""
        if magic is not None:
            try:
                mime_type = magic.from_file(str(path), mime=True)
                if mime_type:
                    return mime_type
            except Exception:
                pass

        guessed_mime, _ = mimetypes.guess_type(str(path))
        if guessed_mime:
            return guessed_mime

        allowed_mimes = cls.ALLOWED_EXTENSIONS.get(path.suffix.lower().lstrip('.'), [])
        return allowed_mimes[0] if allowed_mimes else ""

    @classmethod
    def validate_filename(cls, filename: str) -> None:
        """Validate a filename (extension only, no file needed)"""
        path = Path(filename)
        
        # Check file extension
        extension = path.suffix.lower().lstrip('.')
        if not extension:
            raise ValidationError(f"File must have an extension: {filename}")
        
        if extension not in cls.ALLOWED_EXTENSIONS:
            raise ValidationError(f"Unsupported file extension: .{extension}")

    @classmethod
    def validate_file(cls, file_path: str) -> None:
        """Validate a single file"""
        path = Path(file_path)

        if not path.exists():
            raise ValidationError(f"File does not exist: {file_path}")

        if not path.is_file():
            raise ValidationError(f"Path is not a file: {file_path}")

        # Check file size
        file_size = path.stat().st_size
        if file_size > cls.MAX_FILE_SIZE:
            raise ValidationError(f"File too large: {file_size} bytes (max: {cls.MAX_FILE_SIZE})")

        # Check file extension
        extension = path.suffix.lower().lstrip('.')
        if extension not in cls.ALLOWED_EXTENSIONS:
            raise ValidationError(f"Unsupported file extension: {extension}")

        # Check MIME type (extract base MIME type without parameters like charset)
        try:
            mime_type = cls._detect_mime_type(path)
            # Extract base MIME type (before any semicolon)
            base_mime = mime_type.split(';')[0].strip() if mime_type else ""
            allowed_mimes = cls.ALLOWED_EXTENSIONS.get(extension, [])
            
            # Check if base MIME type is in allowed list
            if base_mime not in allowed_mimes:
                raise ValidationError(f"Invalid file type: {mime_type} for extension {extension}")
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Could not determine file type: {str(e)}")

    @classmethod
    def validate_files(cls, file_paths: List[str]) -> None:
        """Validate multiple files"""
        for file_path in file_paths:
            cls.validate_file(file_path)

    @classmethod
    def get_file_info(cls, file_path: str) -> dict:
        """Get file information"""
        path = Path(file_path)
        stat = path.stat()

        return {
            'name': path.name,
            'size': stat.st_size,
            'extension': path.suffix.lower().lstrip('.'),
            'mime_type': cls._detect_mime_type(path),
            'modified': stat.st_mtime
        }