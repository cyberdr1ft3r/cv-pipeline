"""
Chatbot Configuration Module
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import yaml

# Load environment variables from config/.env
env_path = Path(__file__).parent.parent.parent / "config" / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Fallback to system env vars

# Load YAML config for LLM settings
yaml_config_path = Path(__file__).parent.parent.parent / "config" / "config_yaml.yaml"
_yaml_config = None
if yaml_config_path.exists():
    try:
        with open(yaml_config_path, 'r', encoding='utf-8') as f:
            _yaml_config = yaml.safe_load(f)
    except Exception:
        _yaml_config = None

class Config:
    """Base configuration"""
    
    # Project paths
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    # Chatbot's own stores stay local (sqlite locking is unsafe on a network FS).
    DB_PATH = DATA_DIR / "chatbot_db" / "candidates.db"
    CHROMA_PATH = DATA_DIR / "chatbot_db" / "chroma"
    # Action 227: archived pipeline sessions now live under DATA_ROOT (mounted
    # SFTP share in prod, ./data locally) — read them from there.
    DATA_ROOT = Path(os.getenv("DATA_ROOT") or DATA_DIR)
    ARCHIVE_PATH = DATA_ROOT / "archive"
    
    # Database
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    
    # LLM Configuration - load from YAML if available, else use defaults
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    SESSION_SECRET_KEY = os.getenv("CHATBOT_SESSION_SECRET", "")
    if _yaml_config and 'api' in _yaml_config:
        LLM_MODEL = _yaml_config['api'].get('model', 'meta-llama/llama-3.3-70b-instruct:free')
        LLM_TEMPERATURE = _yaml_config['api'].get('temperature', 0.0)
        LLM_MAX_TOKENS = _yaml_config['api'].get('max_tokens', 8192)
        LLM_TIMEOUT = _yaml_config['api'].get('timeout_seconds', 120)
        LLM_MAX_REQUESTS_PER_MINUTE = _yaml_config['api'].get('max_requests_per_minute', 5)
        LLM_RETRY_WAIT_SECONDS = _yaml_config['api'].get('retry_wait_seconds', 5)
        LLM_MAX_RETRIES = _yaml_config['api'].get('max_retries', 5)
    else:
        LLM_MODEL = 'meta-llama/llama-3.3-70b-instruct:free'
        LLM_TEMPERATURE = 0.0
        LLM_MAX_TOKENS = 8192
        LLM_TIMEOUT = 120
        LLM_MAX_REQUESTS_PER_MINUTE = 5
        LLM_RETRY_WAIT_SECONDS = 5
        LLM_MAX_RETRIES = 5
    
    # Embeddings
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION = 384
    
    # Cache
    CACHE_TTL = 3600  # 1 hour
    CACHE_MAX_SIZE = 1000
    
    # API
    API_HOST = "0.0.0.0"
    API_PORT = 8000
    CORS_ORIGINS = ["http://localhost:3000", "http://localhost:8501", "http://localhost:8000"]
    
    # Sync
    AUTO_SYNC_ON_STARTUP = True
    SYNC_CHECK_INTERVAL = 3600  # 1 hour
    
    # Logging
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Embeddings
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION = 384
    
    # Cache
    CACHE_TTL = 3600  # 1 hour
    CACHE_MAX_SIZE = 1000
    
    # API
    API_HOST = "0.0.0.0"
    API_PORT = 8000
    CORS_ORIGINS = ["http://localhost:3000", "http://localhost:8501", "http://localhost:8000"]
    
    # Sync
    AUTO_SYNC_ON_STARTUP = True
    SYNC_CHECK_INTERVAL = 3600  # 1 hour
    
    # Logging
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    LOG_LEVEL = "DEBUG"

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    LOG_LEVEL = "WARNING"

# Select config based on environment
ENV = os.getenv("ENVIRONMENT", "development")
config = DevelopmentConfig() if ENV == "development" else ProductionConfig()
