"""
AI-Powered CV Section Optimizer
Optimizes projects AND experiences for CV generation using LLM
Uses external prompt files for better organization
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
import time
import yaml

logger = logging.getLogger("CVOptimizer")

# ================================
# CONFIGURATION
# ================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "config_yaml.yaml"
PROMPTS_DIR = PROJECT_ROOT / "config" / "prompts"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

API_CONFIG = CONFIG["api"]

# Load .env file using python-dotenv
from dotenv import load_dotenv
ENV_PATH = PROJECT_ROOT / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# ================================
# LOAD PROMPTS FROM FILES
# ================================
def load_prompt(filename: str) -> str:
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        logger.error(f"❌ Fichier prompt introuvable: {prompt_path}")
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()

PROJECT_OPTIMIZATION_PROMPT = load_prompt("cv_projects_optimizer_prompt.txt")
EXPERIENCE_OPTIMIZATION_PROMPT = load_prompt("cv_experiences_optimizer_prompt.txt")
logger.info("✅ Prompts d'optimisation CV chargés depuis fichiers externes")

# ================================
# AI OPTIMIZATION FUNCTIONS
# ================================
def optimize_projects_with_ai(
    projects: List[Dict[str, Any]],
    job_context: Optional[str] = None,
    max_projects: int = 6
) -> List[Dict[str, Any]]:
    if not projects:
        logger.warning("Aucun projet à optimiser")
        return []

    projects_json = json.dumps(projects, ensure_ascii=False, indent=2)
    job_context_text = job_context or "Aucun contexte d'offre d'emploi fourni"

    prompt = PROJECT_OPTIMIZATION_PROMPT.format(
        projects_json=projects_json,
        job_context=job_context_text
    )

    try:
        response = call_llm_api(prompt)
        response = clean_llm_response(response)
        result = json.loads(response)
        optimized = result.get("optimized_projects", [])
        if len(optimized) > max_projects:
            if optimized and "relevance_score" in optimized[0]:
                optimized.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            optimized = optimized[:max_projects]
        logger.info(f"✅ {len(optimized)} projets optimisés")
        return optimized
    except Exception as e:
        logger.error(f"❌ Échec de l'optimisation IA: {e}")
        return projects[:max_projects]


def optimize_experiences_with_ai(
    experiences: List[Dict[str, Any]],
    job_context: Optional[str] = None,
    max_missions_per_experience: int = 5
) -> List[Dict[str, Any]]:
    if not experiences:
        logger.warning("Aucune expérience à optimiser")
        return []

    experiences_json = json.dumps(experiences, ensure_ascii=False, indent=2)
    job_context_text = job_context or "Aucun contexte d'offre d'emploi fourni"

    prompt = EXPERIENCE_OPTIMIZATION_PROMPT.format(
        experiences_json=experiences_json,
        job_context=job_context_text
    )

    try:
        response = call_llm_api(prompt)
        response = clean_llm_response(response)
        result = json.loads(response)
        optimized = result.get("optimized_experiences", [])
        for exp in optimized:
            missions = exp.get("missions", [])
            if len(missions) > max_missions_per_experience:
                exp["missions"] = missions[:max_missions_per_experience]
        logger.info(f"✅ {len(optimized)} expériences optimisées")
        return optimized
    except Exception as e:
        logger.error(f"❌ Échec de l'optimisation des expériences: {e}")
        return [
            {**exp, "missions": exp.get("missions", [])[:max_missions_per_experience]}
            for exp in experiences
        ]

# ================================
# HELPER: CLEAN LLM RESPONSE
# ================================
def clean_llm_response(response: str) -> str:
    response = response.strip()
    if response.startswith("```"):
        parts = response.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{") or part.startswith("["):
                return part
    return response

# ================================
# LLM API CALL
# ================================
def call_llm_api(prompt: str, max_retries: int = 3) -> str:
    url = f"{API_CONFIG['base_url']}/chat/completions"
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise Exception("Clé API introuvable. Définissez OPENROUTER_API_KEY dans .env")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": API_CONFIG["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": API_CONFIG.get("optimizer", {}).get("temperature", 0.1),
        "max_tokens": API_CONFIG.get("optimizer", {}).get("max_tokens", 3000),
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=API_CONFIG.get("timeout_seconds", 120))
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"].strip()
                return content
            elif response.status_code == 429:
                time.sleep(2 ** attempt * 5)
                continue
            else:
                if attempt < len(API_CONFIG.get("fallback_models", [])):
                    payload["model"] = API_CONFIG["fallback_models"][attempt]
                    continue
                response.raise_for_status()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(5)
    raise Exception("Nombre maximum de tentatives dépassé")

# ================================
# STANDALONE TEST
# ================================
if __name__ == "__main__":
    sample_projects = [
        {
            "nom": "Plateforme E-commerce",
            "description": "Développement d'une plateforme e-commerce complète avec gestion des stocks, panier d'achat, paiement sécurisé",
            "technologies": ["Java", "Spring Boot", "MySQL", "React", "AWS"]
        },
        {
            "nom": "Application Mobile Banking",
            "description": "Application mobile de banque en ligne",
            "technologies": ["Flutter", "Firebase", "Node.js"]
        }
    ]

    sample_experiences = [
        {
            "titre_poste": "Développeur Full Stack",
            "entreprise": "TechCorp",
            "lieu": "Paris",
            "dates": "2021-2024",
            "contexte": "Développement d'applications web pour le secteur bancaire",
            "missions": [
                "Développement de nouvelles fonctionnalités pour l'application web",
                "Maintenance et correction de bugs du code existant",
                "Participation aux réunions d'équipe et aux revues de code",
                "Rédaction de documentation technique",
                "Formation des nouveaux développeurs"
            ],
            "environnement": ["Java", "Spring", "Angular", "MySQL"]
        }
    ]

    job_context = """
    Architecte Java/Angular recherché pour projet e-commerce.
    Compétences requises: Java, Spring Boot, Microservices, Angular, AWS, Docker.
    Expérience avec systèmes e-commerce et paiement souhaitable.
    Leadership technique et mentorat d'équipe apprécié.
    """

    optimized_projects = optimize_projects_with_ai(sample_projects, job_context, 3)
    print(json.dumps(optimized_projects, ensure_ascii=False, indent=2))

    optimized_exp = optimize_experiences_with_ai(sample_experiences, job_context, 5)
    print(json.dumps(optimized_exp, ensure_ascii=False, indent=2))
