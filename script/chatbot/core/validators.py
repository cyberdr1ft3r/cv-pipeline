"""
Response Validators Module
Validates responses for accuracy and consistency
"""

import logging
from typing import Dict, List, Tuple, Any

logger = logging.getLogger(__name__)

class ResponseValidator:
    """Validate responses for accuracy and consistency"""
    
    def __init__(self, db_session=None):
        """
        Initialize validator
        
        Args:
            db_session: Database session for validation queries
        """
        self.db = db_session
    
    def validate(
        self,
        results: List[Dict],
        intent: str,
        entities: Dict
    ) -> Dict:
        """
        Validate query results
        
        Returns:
            {
                "is_valid": True,
                "reason": "...",
                "warnings": [],
                "error_count": 0
            }
        """
        
        warnings = []
        errors = []
        
        # Basic validation
        if not isinstance(results, list):
            errors.append("Results must be a list")
        
        # Intent-specific validation
        if intent == "profile":
            validation = self._validate_profile(results)
            errors.extend(validation["errors"])
            warnings.extend(validation["warnings"])
        
        elif intent == "comparison":
            validation = self._validate_comparison(results)
            errors.extend(validation["errors"])
            warnings.extend(validation["warnings"])
        
        elif intent == "ranking":
            validation = self._validate_ranking(results)
            errors.extend(validation["errors"])
            warnings.extend(validation["warnings"])
        
        # Check for suspicious patterns
        suspicious = self._check_suspicious_patterns(results, entities)
        if suspicious:
            warnings.extend(suspicious)
        
        is_valid = len(errors) == 0
        
        logger.info(
            f"Validation result: valid={is_valid}, errors={len(errors)}, warnings={len(warnings)}"
        )
        
        return {
            "is_valid": is_valid,
            "reason": errors[0] if errors else "Valid",
            "warnings": warnings,
            "error_count": len(errors)
        }
    
    def _validate_profile(self, results: List[Dict]) -> Dict:
        """Validate profile query results"""
        errors = []
        warnings = []
        
        if not results:
            errors.append("No candidate found")
        elif len(results) == 0:
            warnings.append("Expected 1 result, got 0")
        elif len(results) > 1:
            warnings.append(f"Expected 1 result, got {len(results)}")
        
        # Check required fields
        if results and isinstance(results[0], dict):
            required_fields = ["candidate_name", "email", "location"]
            missing = [f for f in required_fields if f not in results[0]]
            if missing:
                warnings.append(f"Missing fields: {', '.join(missing)}")
        
        return {"errors": errors, "warnings": warnings}
    
    def _validate_comparison(self, results: List[Dict]) -> Dict:
        """Validate comparison query results"""
        errors = []
        warnings = []
        
        if len(results) < 2:
            errors.append(f"Comparison requires at least 2 candidates, got {len(results)}")
        elif len(results) > 2:
            warnings.append(f"Comparison expects 2 candidates, got {len(results)}")
        
        return {"errors": errors, "warnings": warnings}
    
    def _validate_ranking(self, results: List[Dict]) -> Dict:
        """Validate ranking query results"""
        errors = []
        warnings = []
        
        if not results:
            errors.append("No candidates found for ranking")
        
        # Check if results are sorted
        if len(results) > 1:
            scores = [r.get("final_score") for r in results if "final_score" in r]
            if scores and not all(scores[i] >= scores[i+1] for i in range(len(scores)-1)):
                warnings.append("Results are not sorted by score")
        
        return {"errors": errors, "warnings": warnings}
    
    def _check_suspicious_patterns(self, results: List[Dict], entities: Dict) -> List[str]:
        """Check for suspicious patterns in results"""
        
        warnings = []
        
        if not results:
            return warnings
        
        # Check if claimed skills match actual data
        if entities.get("skills") and results:
            for result in results:
                candidate_skills = result.get("skills", [])
                if not candidate_skills:
                    continue
                
                claimed_skills = set(s.lower() for s in entities.get("skills", []))
                actual_skills = set(s.lower() for s in candidate_skills)
                
                missing_skills = claimed_skills - actual_skills
                if missing_skills:
                    warnings.append(
                        f"Candidate {result.get('candidate_name')} "
                        f"missing skills: {', '.join(missing_skills)}"
                    )
        
        return warnings
    
    def check_hallucination(
        self,
        candidate_id: int,
        claim: str,
        claim_type: str = "skill"
    ) -> Tuple[bool, str]:
        """
        Check if a claim about a candidate is factual
        
        Args:
            candidate_id: Candidate ID
            claim: Claim to verify
            claim_type: Type of claim ("skill", "gap", "experience", etc.)
        
        Returns:
            (is_valid: bool, reason: str)
        """
        
        if not self.db:
            return True, "No database available for validation"
        
        if claim_type == "skill":
            return self._verify_skill_claim(candidate_id, claim)
        elif claim_type == "gap":
            return self._verify_gap_claim(candidate_id, claim)
        elif claim_type == "experience":
            return self._verify_experience_claim(candidate_id, claim)
        
        return True, "Unknown claim type"
    
    def _verify_skill_claim(self, candidate_id: int, skill: str) -> Tuple[bool, str]:
        """Verify if candidate actually has the claimed skill"""
        
        try:
            # Query database for candidate's actual skills
            query = """
            SELECT skills FROM candidates WHERE id = ?
            """
            result = self.db.execute(query, [candidate_id]).fetchone()
            
            if not result:
                return False, "Candidate not found"
            
            candidate_skills = result[0]
            if not candidate_skills:
                return False, "Candidate has no skills in database"
            
            # Check if skill is in list
            import json
            if isinstance(candidate_skills, str):
                skills_list = json.loads(candidate_skills)
            else:
                skills_list = candidate_skills
            
            skill_lower = skill.lower()
            has_skill = any(s.lower() == skill_lower for s in skills_list)
            
            if has_skill:
                return True, f"Candidate has {skill} skill"
            else:
                return False, f"Candidate does not have {skill} skill"
        
        except Exception as e:
            logger.error(f"Error verifying skill claim: {str(e)}")
            return True, f"Error during verification: {str(e)}"
    
    def _verify_gap_claim(self, candidate_id: int, skill: str) -> Tuple[bool, str]:
        """Verify if candidate actually lacks the skill"""
        
        has_skill, reason = self._verify_skill_claim(candidate_id, skill)
        
        # For gap analysis, we're checking if candidate LACKS the skill
        # So if has_skill is False, the gap claim is valid
        return not has_skill, f"Gap in {skill}: {reason}"
    
    def _verify_experience_claim(self, candidate_id: int, claim: str) -> Tuple[bool, str]:
        """Verify experience claims"""
        
        try:
            # Parse claim like "5 years" or "senior engineer"
            import re
            
            years_match = re.search(r'(\d+)\s*years?', claim, re.IGNORECASE)
            
            if years_match:
                claimed_years = int(years_match.group(1))
                
                query = "SELECT years_experience FROM candidates WHERE id = ?"
                result = self.db.execute(query, [candidate_id]).fetchone()
                
                if result and result[0] is not None:
                    actual_years = result[0]
                    
                    if actual_years >= claimed_years:
                        return True, f"Candidate has {actual_years} years (claim: {claimed_years})"
                    else:
                        return False, f"Candidate has {actual_years} years (claim: {claimed_years})"
            
            return True, "Could not parse experience claim"
        
        except Exception as e:
            logger.error(f"Error verifying experience claim: {str(e)}")
            return True, f"Error during verification: {str(e)}"
