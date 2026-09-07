# script/cv_job_matcher.py

"""
CV-to-Job Matching Engine with Campaign ID Support
Only matches CVs and job offers with the EXACT same campaign timestamp ID
"""

import os
import sys
import json
import yaml
import time
import logging
import argparse
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from openai import OpenAI
from dotenv import load_dotenv
import certifi

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

# Action 227: resolve data folders under DATA_ROOT (mounted SFTP share in prod,
# ./data for local dev). Shared resolver works whether this file is run directly
# (import storage_paths) or imported by the service (from script.storage_paths).
try:
    from script.storage_paths import CURRENT_DIR, safe_relpath
except ImportError:
    from storage_paths import CURRENT_DIR, safe_relpath

CV_DIR_BASE = CURRENT_DIR / "intermediary_structured"
OFFERS_DIR_BASE = CURRENT_DIR / "offer"
LOG_DIR_BASE = CURRENT_DIR / "logs"
MATCHING_RESULTS_BASE = CURRENT_DIR / "matching_results"

# Will be set per session
CV_DIR = None
OFFERS_DIR = None
LOG_DIR = None
OUTPUT_DIR = None

os.makedirs(LOG_DIR_BASE, exist_ok=True)
os.makedirs(MATCHING_RESULTS_BASE, exist_ok=True)

# ================================
# SESSION ID MANAGEMENT
# ================================
def find_available_sessions() -> List[str]:
    """Find all available session IDs in intermediary_structured directory"""
    sessions = []
    if CV_DIR_BASE.exists():
        for item in CV_DIR_BASE.iterdir():
            if item.is_dir() and re.match(r'\d{14}', item.name):
                sessions.append(item.name)
    return sorted(sessions, reverse=True)

def get_job_offers_in_session(session_id: str) -> List[Path]:
    """Get all job offer files for a session"""
    session_offers_dir = OFFERS_DIR_BASE / session_id
    if session_offers_dir.exists():
        return list(session_offers_dir.glob("*.txt"))
    return []

# ================================
# EXTRACT CAMPAIGN ID FROM FILENAME - FIXED FOR EXACT MATCHING
# ================================
def extract_campaign_id(filename: str) -> Optional[str]:
    """
    Extract campaign ID (timestamp) from filename with EXACT matching
    
    Expected format: something_YYYYMMDD_HHMMSS.ext (exactly 8+6 digits)
    Example: architect_20260121_120000.txt → 20260121_120000
    
    IMPORTANT: This ensures EXACT matching:
    - architect_20260121_120000.txt ✅ → 20260121_120000
    - architect_20260121_1200001.txt ❌ → None (extra digit)
    - CV_name_20260121_120000.json ✅ → 20260121_120000
    """
    # Pattern: underscore + EXACTLY 8 digits + underscore + EXACTLY 6 digits + (dot, underscore, or end)
    # (?:\.|_|$) ensures we stop at a delimiter or end of string
    pattern = r'_(\d{8}_\d{6})(?:\.|_|$)'
    match = re.search(pattern, filename)
    if match:
        return match.group(1)
    return None

# ================================
# LOAD MATCHING PROMPT
# ================================
def load_matching_prompt():
    """Load matching prompt template from external file"""
    try:
        prompt_key = "matching"
        if prompt_key in CONFIG.get("prompts", {}):
            relative_path = CONFIG["prompts"][prompt_key]
        else:
            relative_path = "prompts/matching_prompt.txt"
        
        prompt_path = PROJECT_ROOT / "config" / relative_path
        
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
        
        if not template.strip():
            raise ValueError(f"Prompt file is empty: {prompt_path.name}")
        
        return template
        
    except Exception as e:
        print(f"❌ Failed to load matching prompt: {e}")
        raise

try:
    MATCHING_PROMPT_TEMPLATE = load_matching_prompt()
except Exception as e:
    print(f"❌ Cannot start without matching prompt template")
    raise

# ================================
# LOGGING
# ================================
def setup_logging(session_id: str):
    """Setup logging with session-specific log directory"""
    global LOG_DIR
    LOG_DIR = LOG_DIR_BASE / session_id
    os.makedirs(LOG_DIR, exist_ok=True)
    
    log_file = LOG_DIR / f"matching_{session_id}.log"

    logger = logging.getLogger("CVMatcher")
    logger.setLevel(logging.DEBUG)
    logger.handlers = []

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Only show WARNING and ERROR in console
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Log session info to file only (DEBUG level, won't show in console)
    logger.debug(f"Session ID: {session_id}")
    logger.debug(f"Log file: {safe_relpath(log_file)}")
    logger.debug(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return logger

# ================================
# SSL CERTIFICATES
# ================================
try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "certifi", "--quiet"])
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

client = OpenAI(base_url=CONFIG["api"]["base_url"], api_key=OPENROUTER_API_KEY)

# ================================
# API CALL
# ================================
def send_to_openrouter(prompt, purpose="matching", retries=None, wait=None):
    """Send request to OpenRouter with retry logic"""
    if retries is None:
        retries = CONFIG["api"].get("max_retries", 5)
    if wait is None:
        wait = CONFIG["api"].get("retry_wait_seconds", 5)
    
    model = CONFIG["api"]["model"]
    
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=CONFIG["api"]["temperature"],
                max_tokens=CONFIG["api"]["max_tokens"],
            )
            return response.choices[0].message.content
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(wait)
    
    return None

def clean_json_response(text: str) -> Optional[str]:
    """Extract and clean JSON from LLM response"""
    if not text:
        return None
    
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break
    
    start = text.find("{")
    end = text.rfind("}")
    
    if start == -1 or end == -1:
        return None
    
    return text[start:end+1].strip()

# ================================
# DATA MODELS
# ================================
@dataclass
class MatchScore:
    cv_filename: str
    candidate_name: str
    email: str
    phone: str
    annees_experience: str
    overall_score: float
    skills_match: float
    experience_match: float
    education_match: float
    strengths: List[str]
    gaps: List[str]
    recommendation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# ================================
# CV MATCHER WITH CAMPAIGN ID
# ================================
class CVJobMatcher:
    """Matches CVs against job descriptions using session-based organization"""
    
    def __init__(self, logger, session_id: str, experience_context: str = "", cv_limit: int | None = None):
        self.logger = logger
        self.session_id = session_id
        self.experience_context = experience_context or ""
        self.cv_limit = cv_limit if cv_limit and cv_limit > 0 else None
        # Set session-specific directories
        self.cv_dir = CV_DIR_BASE / session_id
        self.offers_dir = OFFERS_DIR_BASE / session_id
    
    def find_matching_cvs(self) -> List[Path]:
        """Find all CVs in the session directory"""
        if not self.cv_dir.exists():
            self.logger.warning(f"⚠️  CV directory not found: {safe_relpath(self.cv_dir)}")
            return []
        
        all_cvs = sorted(self.cv_dir.glob("*.json"), key=lambda p: p.name)
        if self.cv_limit and len(all_cvs) > self.cv_limit:
            self.logger.info(
                f"   Limiting matching pool to {self.cv_limit}/{len(all_cvs)} CV(s)"
            )
            all_cvs = all_cvs[: self.cv_limit]
        self.logger.debug(f"Found {len(all_cvs)} CV(s) in session {self.session_id}")
        return all_cvs
    
    def load_cv(self, cv_path: Path) -> Optional[Dict[str, Any]]:
        """Load and parse CV JSON file"""
        try:
            with open(cv_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load CV {cv_path.name}: {e}")
            return None
    
    def extract_contact_info(self, cv_data: Dict[str, Any]) -> tuple[str, str]:
        """Extract email and phone from CV data"""
        info = cv_data.get("informations_personnelles", {})
        email = info.get("email", "N/A")
        phone = info.get("telephone", info.get("phone", "N/A"))
        return email, phone
    
    def format_candidate_summary(self, cv_data: Dict[str, Any]) -> str:
        """Format CV data into a concise summary"""
        info = cv_data.get("informations_personnelles", {})
        competences = cv_data.get("competences", {})
        experiences = cv_data.get("experiences_professionnelles", [])
        formation = cv_data.get("formation", [])
        certifications = cv_data.get("certifications", [])
        
        summary_parts = []
        
        nom = info.get("nom_complet", "Unknown")
        titre = info.get("titre", "")
        summary_parts.append(f"Name: {nom}")
        if titre:
            summary_parts.append(f"Title: {titre}")
        
        if competences:
            techs = competences.get("technologies", [])
            methos = competences.get("methodologies_et_outils", [])
            
            def to_string_list(items):
                result = []
                for item in items:
                    if isinstance(item, str):
                        result.append(item)
                    elif isinstance(item, dict):
                        result.append(item.get("nom", item.get("name", str(item))))
                    else:
                        result.append(str(item))
                return result
            
            all_skills = to_string_list(techs) + to_string_list(methos)
            if all_skills:
                summary_parts.append(f"\nSkills: {', '.join(all_skills[:25])}")
        
        if experiences:
            summary_parts.append(f"\nExperiences ({len(experiences)} positions):")
            for i, exp in enumerate(experiences[:3], 1):
                titre_poste = exp.get("titre_poste", exp.get("poste", ""))
                entreprise = exp.get("entreprise", "")
                dates = exp.get("dates", exp.get("periode", ""))
                summary_parts.append(f"  {i}. {titre_poste} at {entreprise} ({dates})")
        
        if formation:
            summary_parts.append(f"\nEducation:")
            for edu in formation[:2]:
                diplome = edu.get("diplome", "")
                etablissement = edu.get("etablissement", "")
                annee = edu.get("annee", "")
                summary_parts.append(f"  - {diplome}, {etablissement} ({annee})")
        
        if certifications:
            cert_strings = []
            for cert in certifications[:5]:
                if isinstance(cert, str):
                    cert_strings.append(cert)
                elif isinstance(cert, dict):
                    cert_strings.append(cert.get("nom", cert.get("name", str(cert))))
                else:
                    cert_strings.append(str(cert))
            if cert_strings:
                summary_parts.append(f"\nCertifications: {', '.join(cert_strings)}")
        
        return "\n".join(summary_parts)
    
    def score_cv(self, job_description: str, cv_data: Dict[str, Any], cv_filename: str) -> Optional[MatchScore]:
        """Score a single CV against job description"""
        try:
            candidate_name = cv_data.get("informations_personnelles", {}).get("nom_complet", "Unknown")
            email, phone = self.extract_contact_info(cv_data)
            annees_experience = cv_data.get("profil_resume", {}).get("annees_experience", "N/A")
            
            self.logger.info(f"   🤖 Scoring: {candidate_name}")
            
            candidate_summary = self.format_candidate_summary(cv_data)
            prompt = MATCHING_PROMPT_TEMPLATE.format(
                experience_context=self.experience_context,
                job_description=job_description,
                candidate_summary=candidate_summary,
            )
            
            response = send_to_openrouter(prompt, purpose=f"scoring_{cv_filename}")
            
            if not response:
                self.logger.error(f"   ❌ No response for {cv_filename}")
                return None
            
            score_data = self._parse_score_response(response)
            if not score_data:
                return None
            
            recommendation = self._get_recommendation(score_data["overall_score"])
            
            match_score = MatchScore(
                cv_filename=cv_filename,
                candidate_name=candidate_name,
                email=email,
                phone=phone,
                annees_experience=annees_experience,
                overall_score=score_data["overall_score"],
                skills_match=score_data["skills_match"],
                experience_match=score_data["experience_match"],
                education_match=score_data["education_match"],
                strengths=score_data.get("strengths", []),
                gaps=score_data.get("gaps", []),
                recommendation=recommendation
            )
            
            self.logger.info(f"   ✅ {candidate_name}: {match_score.overall_score:.1f}/100 ({recommendation})")
            
            return match_score
            
        except Exception as e:
            self.logger.error(f"   ❌ Error scoring {cv_filename}: {e}")
            return None
    
    def _parse_score_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response"""
        try:
            cleaned_json = clean_json_response(response)
            if not cleaned_json:
                self.logger.debug("   ⚠️  Could not extract JSON from response")
                return None
            parsed = json.loads(cleaned_json)
            
            # Validate required fields
            required_fields = ["overall_score", "skills_match", "experience_match", "education_match"]
            missing = [f for f in required_fields if f not in parsed]
            if missing:
                self.logger.debug(f"   ⚠️  Missing required fields: {missing}")
                return None
            
            return parsed
        except json.JSONDecodeError as e:
            self.logger.debug(f"   ⚠️  JSON parsing error: {e}")
            return None
    
    def _get_recommendation(self, score: float) -> str:
        """Convert numeric score to recommendation"""
        if score >= 90:
            return "Exceptional Match"
        elif score >= 75:
            return "Strong Match"
        elif score >= 60:
            return "Good Match"
        elif score >= 40:
            return "Partial Match"
        else:
            return "Poor Match"
    
    def match_campaign_cvs(self, job_description: str) -> List[MatchScore]:
        """Score all CVs in the session"""
        cv_files = self.find_matching_cvs()
        
        if not cv_files:
            self.logger.warning(f"⚠️  No CVs found in session: {self.session_id}")
            return []
        
        self.logger.debug(f"Found {len(cv_files)} CV(s) in session {self.session_id}")
        print(f"📋 Analyzing {len(cv_files)} candidates...\n")
        
        scores = []
        success_count = 0
        failed_cvs = []  # Track failed CVs for retry
        
        # ========================================
        # FIRST PASS: Try to score all CVs
        # ========================================
        for idx, cv_file in enumerate(cv_files, 1):
            cv_data = self.load_cv(cv_file)
            if not cv_data:
                failed_cvs.append((cv_file, cv_data))
                continue
            
            score = self.score_cv(job_description, cv_data, cv_file.name)
            if score:
                scores.append(score)
                success_count += 1
            else:
                # Store for retry
                failed_cvs.append((cv_file, cv_data))
        
        # ========================================
        # RETRY MECHANISM: Retry failed CVs up to 3 times
        # ========================================
        if failed_cvs:
            max_retries = CONFIG.get("matching", {}).get("cv_retry_attempts", 3)
            for retry_attempt in range(1, max_retries + 1):
                remaining_failed = []
                retry_success = 0
                retry_failed = 0
                
                for idx, (cv_file, cv_data) in enumerate(failed_cvs, 1):
                    # If cv_data is None, try loading again
                    if cv_data is None:
                        cv_data = self.load_cv(cv_file)
                        if not cv_data:
                            retry_failed += 1
                            self.logger.error(f"   ❌ Cannot load CV")
                            remaining_failed.append((cv_file, cv_data))
                            continue
                    
                    # Wait before retry (increase with each attempt to avoid rate limiting)
                    wait_time = 3 + (retry_attempt * 2)
                    time.sleep(wait_time)
                    
                    score = self.score_cv(job_description, cv_data, cv_file.name)
                    if score:
                        scores.append(score)
                        success_count += 1
                        retry_success += 1
                    else:
                        retry_failed += 1
                        remaining_failed.append((cv_file, cv_data))
                
                # If all recovered, stop retrying
                if not remaining_failed:
                    break
                
                # Update failed list for next attempt
                failed_cvs = remaining_failed
        
        # ========================================
        # FINAL RESULTS
        # ========================================
        scores.sort(key=lambda x: x.overall_score, reverse=True)
        
        final_failed = len(cv_files) - success_count
        
        print(f"✅ Analyzed: {success_count}/{len(cv_files)} candidates\n")
        return scores
    
    def save_results(self, scores: List[MatchScore], job_title: str):
        """Save matching results with session ID in session-specific directory"""
        session_output_dir = MATCHING_RESULTS_BASE / self.session_id
        os.makedirs(session_output_dir, exist_ok=True)
        
        output_file = session_output_dir / f"match_{job_title}_{self.session_id}.json"
        
        results = {
            "session_id": self.session_id,
            "job_title": job_title,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_candidates": len(scores),
            "summary": {
                "exceptional": sum(1 for s in scores if s.overall_score >= 90),
                "strong": sum(1 for s in scores if 75 <= s.overall_score < 90),
                "good": sum(1 for s in scores if 60 <= s.overall_score < 75),
                "partial": sum(1 for s in scores if 40 <= s.overall_score < 60),
                "poor": sum(1 for s in scores if s.overall_score < 40)
            },
            "candidates": [s.to_dict() for s in scores]
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # Log to file only (DEBUG level)
        self.logger.debug(f"Results saved: {safe_relpath(output_file)}")
        self.logger.debug(f"Total candidates: {len(scores)}")
        
        return output_file
    
    def print_summary(self, scores: List[MatchScore]):
        """Print TOP 5 candidates in simplified format"""
        print("\n" + "=" * 110)
        print(f"📊 CANDIDATES LIST - Session: {self.session_id}".center(110))
        print("=" * 110)
        
        if not scores:
            print("Aucun candidat noté.")
            print("=" * 110 + "\n")
            return
        
        print(f"\n{'Rang':<6} {'Nom Complet':<28} {'Email':<28} {'Expérience':<16} {'Score':<8}")
        print("-" * 110)
        
        for i, score in enumerate(scores[:5], 1):
            nom = score.candidate_name[:26] if len(score.candidate_name) > 26 else score.candidate_name
            email = score.email[:26] if len(score.email) > 26 else score.email
            exp = score.annees_experience[:14] if len(score.annees_experience) > 14 else score.annees_experience
            
            print(f"#{i:<5} {nom:<28} {email:<28} {exp:<16} {score.overall_score:>5.0f}%")
        
        print("\n" + "=" * 110 + "\n")

# ================================
# INTERACTIVE CANDIDATE SELECTION
# ================================
def load_matching_results(results_file: Path) -> Optional[Dict[str, Any]]:
    """Load matching results from JSON file"""
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load results file: {e}")
        return None

def display_selection_help():
    """Display help for selection criteria"""
    print("\n" + "=" * 90)
    print("📋 SELECTION CRITERIA EXAMPLES".center(90))
    print("=" * 90)
    print("""
Examples of selection criteria:
  • top 5                      → Top 5 candidates by score
  • top 10                     → Top 10 candidates by score
  • score >= 80                → All candidates with score 80 or higher
  • score >= 75 and < 90       → Candidates with score between 75-90
  • exceptional                → All "Exceptional Match" candidates
  • strong                     → All "Strong Match" candidates
  • strong|good                → All "Strong Match" or "Good Match" candidates
  • all                        → Show all candidates

Special commands:
  • help                       → Show this help menu
  • exit/quit                  → Finish and exit selection
""")
    print("=" * 90)

def generate_candidate_analysis(candidates: List[Dict[str, Any]], job_title: str):
    """Generate comprehensive analysis report for all candidates"""
    if not candidates:
        print("❌ No candidates to analyze")
        return
    
    print("\n" + "=" * 110)
    print("📊 COMPREHENSIVE CANDIDATE ANALYSIS REPORT".center(110))
    print("=" * 110)
    
    # ========================================
    # OVERALL STATISTICS
    # ========================================
    print(f"\n🎯 Overall Statistics for: {job_title}")
    print("-" * 110)
    
    total = len(candidates)
    avg_score = sum(c.get("overall_score", 0) for c in candidates) / total if total > 0 else 0
    
    # Count by recommendation
    rec_counts = {}
    for c in candidates:
        rec = c.get("recommendation", "Unknown")
        rec_counts[rec] = rec_counts.get(rec, 0) + 1
    
    print(f"   • Total Candidates: {total}")
    print(f"   • Average Score: {avg_score:.1f}/100")
    print(f"   • Highest Score: {max((c.get('overall_score', 0) for c in candidates), default=0):.1f}/100")
    print(f"   • Lowest Score: {min((c.get('overall_score', 0) for c in candidates), default=0):.1f}/100")
    
    # ========================================
    # RECOMMENDATION BREAKDOWN
    # ========================================
    print(f"\n📈 Recommendation Breakdown:")
    print("-" * 110)
    
    rec_order = ["Exceptional Match", "Strong Match", "Good Match", "Partial Match", "Poor Match"]
    for rec in rec_order:
        count = rec_counts.get(rec, 0)
        percentage = (count / total * 100) if total > 0 else 0
        bar_length = int(percentage / 2)
        bar = "█" * bar_length + "░" * (50 - bar_length)
        print(f"   {rec:<20} │{bar}│ {count} ({percentage:5.1f}%)")
    
    # ========================================
    # SCORE DISTRIBUTION
    # ========================================
    print(f"\n📊 Score Distribution:")
    print("-" * 110)
    
    ranges = [
        ("90-100 (Exceptional)", 90, 100),
        ("75-89  (Strong)", 75, 89),
        ("60-74  (Good)", 60, 74),
        ("40-59  (Partial)", 40, 59),
        ("0-39   (Poor)", 0, 39)
    ]
    
    for label, min_score, max_score in ranges:
        count = sum(1 for c in candidates if min_score <= c.get("overall_score", 0) <= max_score)
        percentage = (count / total * 100) if total > 0 else 0
        bar_length = int(percentage / 2)
        bar = "█" * bar_length + "░" * (50 - bar_length)
        print(f"   {label:<20} │{bar}│ {count} ({percentage:5.1f}%)")
    
    # ========================================
    # COMPETENCE ANALYSIS
    # ========================================
    print(f"\n💪 Competence Analysis (Avg Scores):")
    print("-" * 110)
    
    skills_avg = sum(c.get("skills_match", 0) for c in candidates) / total if total > 0 else 0
    exp_avg = sum(c.get("experience_match", 0) for c in candidates) / total if total > 0 else 0
    edu_avg = sum(c.get("education_match", 0) for c in candidates) / total if total > 0 else 0
    
    def score_to_level(score):
        if score >= 80:
            return "🟢 Excellent"
        elif score >= 60:
            return "🟡 Good"
        elif score >= 40:
            return "🟠 Moderate"
        else:
            return "🔴 Poor"
    
    print(f"   • Skills Match:      {skills_avg:5.1f}/100  {score_to_level(skills_avg)}")
    print(f"   • Experience Match:  {exp_avg:5.1f}/100  {score_to_level(exp_avg)}")
    print(f"   • Education Match:   {edu_avg:5.1f}/100  {score_to_level(edu_avg)}")
    
    # ========================================
    # COMMON STRENGTHS (POINTS FORTS)
    # ========================================
    print(f"\n✨ Common Strengths (Points Forts):")
    print("-" * 110)
    
    strength_freq = {}
    for c in candidates:
        for strength in c.get("strengths", []):
            # Extract key phrases (first 10 words)
            key_phrase = " ".join(strength.split()[:10])
            strength_freq[key_phrase] = strength_freq.get(key_phrase, 0) + 1
    
    sorted_strengths = sorted(strength_freq.items(), key=lambda x: x[1], reverse=True)
    for i, (strength, count) in enumerate(sorted_strengths[:5], 1):
        print(f"   {i}. [{count}/{total}] {strength}")
    
    # ========================================
    # COMMON WEAKNESSES (POINTS FAIBLES)
    # ========================================
    print(f"\n⚠️  Common Weaknesses (Points Faibles):")
    print("-" * 110)
    
    gap_freq = {}
    for c in candidates:
        for gap in c.get("gaps", []):
            # Extract key phrases (first 10 words)
            key_phrase = " ".join(gap.split()[:10])
            gap_freq[key_phrase] = gap_freq.get(key_phrase, 0) + 1
    
    sorted_gaps = sorted(gap_freq.items(), key=lambda x: x[1], reverse=True)
    for i, (gap, count) in enumerate(sorted_gaps[:5], 1):
        print(f"   {i}. [{count}/{total}] {gap}")
    
    # ========================================
    # RECOMMENDATIONS
    # ========================================
    print(f"\n🎓 Recommendations:")
    print("-" * 110)
    
    if avg_score >= 75:
        print(f"   ✅ Overall pool quality is EXCELLENT (avg {avg_score:.1f}/100)")
        print(f"      → Consider fast-track hiring for highest-scoring candidates")
    elif avg_score >= 60:
        print(f"   🟡 Overall pool quality is GOOD (avg {avg_score:.1f}/100)")
        print(f"      → Viable candidates available; may need targeted interviews")
    else:
        print(f"   🔴 Overall pool quality is POOR (avg {avg_score:.1f}/100)")
        print(f"      → Consider expanding candidate search or adjusting requirements")
    
    if rec_counts.get("Good Match", 0) + rec_counts.get("Strong Match", 0) + rec_counts.get("Exceptional Match", 0) == 0:
        print(f"   ⚠️  No 'Good Match' or better candidates found")
        print(f"      → Review job requirements or candidate sourcing strategy")
    
    if edu_avg < 50:
        print(f"   📚 Consider training programs for education gaps")
    
    if exp_avg < 50:
        print(f"   👨‍💼 Consider mentorship or junior-friendly onboarding")
    
    print("\n" + "=" * 110 + "\n")

def parse_selection_criteria(criteria: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse user's selection criteria and filter candidates (supports natural language via LLM)"""
    criteria = criteria.strip().lower()
    
    # Exit commands
    if criteria in ['exit', 'quit', 'no', 'n', '']:
        return []
    
    # Analysis/Report commands
    if any(word in criteria for word in ['analyse', 'analysis', 'report', 'statistique', 'statistics', 'overview', 'summary']):
        # Extract job title from first candidate or use generic
        job_title = "Matching Results"
        generate_candidate_analysis(candidates, job_title)
        return []
    
    # Help command
    if criteria == 'help':
        display_selection_help()
        return []
    
    # All candidates
    if criteria == 'all':
        return candidates
    
    # For everything else, use LLM for intelligent interpretation
    # This gives maximum flexibility for natural language queries
    print("🤖 Processing your request...")
    interpreted = interpret_criteria_with_llm(criteria, candidates)
    return interpreted

def interpret_criteria_with_llm(user_input: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Use LLM to interpret natural language selection criteria - flexible conversation-style queries"""
    try:
        # Build detailed candidate data for LLM
        candidate_data = []
        for i, c in enumerate(candidates):
            candidate_data.append({
                "index": i,
                "name": c.get('candidate_name', 'Unknown'),
                "email": c.get('email', 'N/A'),
                "phone": c.get('phone', 'N/A'),
                "score": c.get('overall_score', 0),
                "recommendation": c.get('recommendation', 'N/A'),
                "skills_match": c.get('skills_match', 0),
                "experience_match": c.get('experience_match', 0),
                "education_match": c.get('education_match', 0),
                "strengths": c.get('strengths', []),
                "gaps": c.get('gaps', [])
            })
        
        prompt = f"""You are a smart CV selection assistant. The user is asking questions about candidates.
Your job is to understand their natural language query and select matching candidates.

Available candidates data:
{json.dumps(candidate_data, indent=2, ensure_ascii=False)}

User's request: "{user_input}"

Understand the user's intent and return a JSON object with:
- "interpretation": brief explanation of what the user asked for
- "indices": array of 0-based indices of selected candidates that match the criteria
- "explanation": why these candidates were selected

Examples:
- User: "top 2 by score" → {{"interpretation": "Top 2 candidates by overall score", "indices": [0, 1], "explanation": "Selected the 2 highest-scoring candidates"}}
- User: "who has score above 60" → {{"interpretation": "Candidates with score above 60", "indices": [0, 1], "explanation": "These 2 candidates have scores ≥ 60"}}
- User: "show me strong matches" → {{"interpretation": "Strong Match recommendations", "indices": [...], "explanation": "Selected all candidates with Strong Match rating"}}
- User: "best at skills" → {{"interpretation": "Best skills match", "indices": [0], "explanation": "Candidate with highest skills_match score"}}
- User: "compare top 2" → {{"interpretation": "Top 2 candidates for comparison", "indices": [0, 1], "explanation": "Top 2 candidates by overall score for detailed comparison"}}

Be flexible with natural language:
- "top ones", "top candidates", "best candidates" → top by score
- "score above/over/higher than X" → score >= X
- "score below/under X" → score <= X  
- "between X and Y" → score >= X and score <= Y
- "strong/good/exceptional matches" → by recommendation
- "best skills", "best experience", "best education" → highest in that category
- French and English understood

Return ONLY valid JSON, no other text."""

        response = send_to_openrouter(prompt, purpose="criteria_interpretation")
        
        if not response:
            return []
        
        # Extract JSON from response
        cleaned_json = clean_json_response(response)
        if not cleaned_json:
            return []
        
        result = json.loads(cleaned_json)
        indices = result.get("indices", [])
        explanation = result.get("explanation", "")
        
        # Print interpretation for transparency
        if explanation:
            print(f"🤖 Understanding: {explanation}")
        
        # Filter candidates by indices
        selected = [candidates[i] for i in indices if i < len(candidates)]
        return selected
        
    except Exception as e:
        print(f"⚠️  Could not interpret with LLM: {e}")
        return []

def display_selected_candidates(selected: List[Dict[str, Any]], job_title: str):
    """Display selected candidates in formatted table"""
    if not selected:
        print("\n⚠️  No candidates selected.")
        return
    
    print("\n" + "=" * 100)
    print(f"✅ SELECTED CANDIDATES ({len(selected)} results)".center(100))
    print("=" * 100)
    
    print(f"\n{'Rang':<6} {'Nom Complet':<25} {'Email':<25} {'Score':<8} {'Recommendation':<20}")
    print("-" * 100)
    
    for i, candidate in enumerate(selected, 1):
        nom = candidate.get("candidate_name", "N/A")[:23]
        email = candidate.get("email", "N/A")[:23]
        score = candidate.get("overall_score", 0)
        recommendation = candidate.get("recommendation", "N/A")
        
        print(f"#{i:<5} {nom:<25} {email:<25} {score:>5.0f}%  {recommendation:<20}")
    
    print("\n" + "-" * 100)
    print(f"📊 Details Summary:")
    print(f"   • Total Selected: {len(selected)}")
    avg_score = sum(c.get("overall_score", 0) for c in selected) / len(selected) if selected else 0
    print(f"   • Average Score: {avg_score:.1f}/100")
    print(f"   • Job Title: {job_title}")
    print("=" * 100 + "\n")

def interactive_candidate_selection(output_file: Path, job_title: str):
    """Interactive prompt for candidate selection based on criteria"""
    print("\n" + "=" * 90)
    print("🔍 INTERACTIVE CANDIDATE SELECTION".center(90))
    print("=" * 90)
    
    # Load results
    results = load_matching_results(output_file)
    if not results:
        return
    
    candidates = results.get("candidates", [])
    if not candidates:
        print("❌ No candidates found in results")
        return
    
    print(f"\n📊 Total candidates in results: {len(candidates)}")
    print("\n💡 Enter selection criteria (or type 'exit' to finish):\n")
    
    while True:
        user_input = input("→ Selection criteria: ").strip()
        
        if user_input.lower() == 'help':
            display_selection_help()
            continue
        
        if user_input.lower() in ['exit', 'quit']:
            print("\n✓ Selection complete. Exiting.\n")
            break
        
        if user_input.lower() in ['no', 'n', '']:
            print("⚠️  Please enter a criteria or type 'exit' to finish.\n")
            continue
        
        selected = parse_selection_criteria(user_input, candidates)
        
        if selected:
            display_selected_candidates(selected, job_title)
            print("💡 Enter another selection criteria or type 'exit' to finish:\n")
        else:
            print("⚠️  No results matched your criteria. Try again.\n")

# ================================
# MAIN
# ================================
def main():
    parser = argparse.ArgumentParser(
        description="Match CVs against job descriptions using session ID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python script/matcher.py 20260121162645
  python script/matcher.py --session 20260121162645
  python script/matcher.py --list    (show available sessions)
  python script/matcher.py 20260121162645 --reuse-session 20260120100000
        """
    )
    parser.add_argument("session_id", nargs="?", default=None, help="Session ID (YYYYMMDD_HHMMSS)")
    parser.add_argument("--session", type=str, default=None, help="Session ID (alternative)")
    parser.add_argument("--reuse-session", type=str, default=None, help="Reuse CVs from this session ID")
    parser.add_argument("--cv-dir", type=str, default=None, help="Override CV directory (offer_only: read from CV_Theque mount)")
    parser.add_argument(
        "--experience-context",
        type=str,
        default=None,
        help="French experience-range hint injected into the matching prompt (Action 281)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of CVs to score (alphabetical order by filename)",
    )
    parser.add_argument("--list", action="store_true", help="List available sessions")
    
    args = parser.parse_args()
    
    # Handle --list option
    if args.list:
        print("\n📋 Available Sessions:\n")
        sessions = find_available_sessions()
        if not sessions:
            print("   No sessions found")
        else:
            for i, session in enumerate(sessions, 1):
                cv_count = len(list((CV_DIR_BASE / session).glob("*.json"))) if (CV_DIR_BASE / session).exists() else 0
                offer_count = len(list((OFFERS_DIR_BASE / session).glob("*.txt"))) if (OFFERS_DIR_BASE / session).exists() else 0
                print(f"   {i}. {session}  ({cv_count} CVs, {offer_count} offers)")
        print()
        return
    
    # Get session ID from arguments
    session_id = args.session or args.session_id
    
    # If no session ID provided, auto-detect
    if not session_id:
        available_sessions = find_available_sessions()
        
        if len(available_sessions) == 0:
            print("\n❌ No sessions found")
            print("   Please run the extraction script first to create a session\n")
            return
        elif len(available_sessions) == 1:
            session_id = available_sessions[0]
            print(f"\n✅ Auto-detected session: {session_id}\n")
        else:
            print("\n❌ Multiple sessions found. Please specify one:\n")
            for i, session in enumerate(available_sessions, 1):
                cv_count = len(list((CV_DIR_BASE / session).glob("*.json"))) if (CV_DIR_BASE / session).exists() else 0
                offer_count = len(list((OFFERS_DIR_BASE / session).glob("*.txt"))) if (OFFERS_DIR_BASE / session).exists() else 0
                print(f"   {i}. {session}  ({cv_count} CVs, {offer_count} offers)")
            print()
            print("Usage:")
            print(f"   python script/matcher.py {available_sessions[0]}")
            print(f"   python script/matcher.py --session {available_sessions[0]}\n")
            return
    
    # Log reuse mode if specified
    if args.reuse_session:
        print(f"\n🔄 REUSE MODE: Using CVs from session {args.reuse_session}\n")
    
    # Validate session ID format
    if not re.match(r'\d{14}', session_id):
        print(f"\n❌ Invalid session ID format: {session_id}")
        print(f"Expected format: YYYYMMDDHHMMSS (14 digits)\n")
        return
    
    # Check if session exists (CV dir may be overridden for offer_only / CV_Theque)
    session_cv_dir = Path(args.cv_dir) if args.cv_dir else (CV_DIR_BASE / session_id)
    session_offer_dir = OFFERS_DIR_BASE / session_id
    
    if not session_cv_dir.exists():
        print(f"\n❌ Session CV directory not found: {safe_relpath(session_cv_dir)}\n")
        return
    
    if not session_offer_dir.exists():
        print(f"\n❌ Session offer directory not found: {safe_relpath(session_offer_dir)}\n")
        sys.exit(1)

    # Get job offers for this session
    job_offers = get_job_offers_in_session(session_id)

    if not job_offers:
        print(f"\n❌ No job offers found in session: {session_id}\n")
        sys.exit(1)
    
    logger = setup_logging(session_id)
    
    print("\n" + "=" * 70)
    print("🎯 CV-TO-JOB MATCHING ENGINE")
    print("=" * 70)
    
    matcher = CVJobMatcher(
        logger,
        session_id,
        experience_context=args.experience_context or "",
        cv_limit=args.limit,
    )
    if args.cv_dir:
        matcher.cv_dir = Path(args.cv_dir)
    
    # Process each job offer
    all_results = []
    for job_idx, job_file in enumerate(job_offers, 1):
        print(f"\n{'─' * 70}")
        print(f"📋 Position [{job_idx}/{len(job_offers)}]: {job_file.stem}")
        print(f"{'─' * 70}\n")
        
        # Extract job title from filename
        job_title = job_file.stem
        
        try:
            with open(job_file, "r", encoding="utf-8") as f:
                job_description = f.read().strip()
        except Exception as e:
            logger.error(f"❌ Failed to read job file {job_file.name}: {e}\n")
            continue
        
        if not job_description:
            logger.error(f"❌ Job description is empty: {job_file.name}\n")
            continue
        
        start_time = time.time()
        scores = matcher.match_campaign_cvs(job_description)
        elapsed = time.time() - start_time
        
        if not scores:
            logger.warning(f"⚠️  No candidates scored successfully for {job_title}\n")
            continue
        
        output_file = matcher.save_results(scores, job_title)
        matcher.print_summary(scores)
        
        all_results.append((job_title, len(scores), output_file))
    
    # Final summary
    if all_results:
        print("\n" + "=" * 70)
        print("✅ MATCHING COMPLETE")
        print("=" * 70)
        for job_title, score_count, output_file in all_results:
            print(f"  ✓ {job_title}: {score_count} candidates matched")
        print("=" * 70 + "\n")
    else:
        print("\n⚠️  No results generated\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user\n")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}\n")
        import traceback
        traceback.print_exc()
    finally:
        print("👋 Matching terminated\n")