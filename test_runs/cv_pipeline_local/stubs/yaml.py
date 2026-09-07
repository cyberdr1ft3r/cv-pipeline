def safe_load(stream):
    return {
        "api": {
            "base_url": "http://test.invalid",
            "model": "test-model",
            "fallback_models": [],
            "max_retries": 1,
            "retry_wait_seconds": 0,
            "timeout_seconds": 1,
            "max_requests_per_minute": 999,
        },
        "paths": {"POPPLER_PATH": "", "tesseract_cmd": ""},
        "prompts": {
            "extraction": "prompts/extraction_prompt.txt",
            "validation": "prompts/validation_prompt.txt",
            "offer_parser_profile_system": "prompts/offer_parser_profile_system.txt",
            "offer_parser_profile_user": "prompts/offer_parser_profile_user.txt",
            "offer_parser_seniority_system": "prompts/offer_parser_seniority_system.txt",
            "offer_parser_seniority_user": "prompts/offer_parser_seniority_user.txt",
        },
        "extraction": {"ocr_dpi": 300},
        "pipeline": {
            "supported_extensions": [".pdf", ".docx", ".doc"],
            "seniority_levels": ["Junior", "Confirme", "Senior", "Expert"],
        },
        "watcher": {
            "reserved_dir_names": ["processed", "failed"],
            "internship_contract_types": ["stage", "pfe", "alternance"],
        },
        "logging": {"level": "INFO"},
    }
