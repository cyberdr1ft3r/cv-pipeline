"""
Auto-Sync Engine for the Chatbot
Automatically loads and indexes latest candidate data from data/archive/ on startup
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class DataSyncEngine:
    """Discovers and syncs latest candidate data from archive directories"""
    
    def __init__(self, db_path: str, data_archive_dir: str):
        """
        Initialize sync engine
        
        Args:
            db_path: Path to SQLite database
            data_archive_dir: Path to data/archive/ directory containing session folders
        """
        self.db_path = db_path
        self.archive_dir = Path(data_archive_dir)
        self.conn = None
    
    def discover_latest_session(self) -> Optional[Path]:
        """Find the most recently modified session directory"""
        
        if not self.archive_dir.exists():
            logger.warning(f"Archive directory not found: {self.archive_dir}")
            return None
        
        # Find all session directories (format: YYYYMMDDHHMMSS)
        sessions = []
        for item in self.archive_dir.iterdir():
            if item.is_dir() and len(item.name) == 14 and item.name.isdigit():
                sessions.append(item)
        
        if not sessions:
            logger.info("No session directories found in archive")
            return None
        
        # Get most recent by timestamp
        latest = max(sessions, key=lambda p: p.name)
        logger.info(f"Found latest session: {latest.name}")
        return latest
    
    def get_sync_metadata(self) -> Dict:
        """Get current sync state from database"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            SELECT * FROM sync_metadata 
            ORDER BY last_synced DESC 
            LIMIT 1
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return {}
        
        except Exception as e:
            logger.error(f"Error reading sync metadata: {e}")
            conn.close()
            return {}
    
    def should_sync(self, latest_session: Path) -> bool:
        """Check if latest session is newer than last sync"""
        
        metadata = self.get_sync_metadata()
        
        if not metadata:
            logger.info("No sync history - full sync needed")
            return True
        
        last_synced_dir = metadata.get('source_dir')
        
        if not last_synced_dir:
            return True
        
        # Compare timestamps
        last_session_time = Path(last_synced_dir).name
        latest_session_time = latest_session.name
        
        should_sync = latest_session_time > last_session_time
        
        if should_sync:
            logger.info(f"New session detected: {latest_session_time} > {last_session_time}")
        else:
            logger.info(f"Data already up-to-date: {latest_session_time}")
        
        return should_sync
    
    def load_candidates_from_json(self, session_dir: Path) -> List[Dict]:
        """Load candidates from session's extracted CV JSON files"""
        
        candidates = []
        
        # Try to load from cvs/extracted/ (where extracted CV data is stored)
        extracted_dir = session_dir / 'cvs' / 'extracted'
        
        if not extracted_dir.exists():
            logger.warning(f"Extracted CV directory not found: {extracted_dir}")
            return candidates
        
        # Look for JSON files in extracted directory
        for json_file in extracted_dir.glob('*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Extract candidate name from data
                    name = data.get('candidate_name') or data.get('name')
                    
                    if name:
                        candidates.append({
                            'candidate_name': name,
                            'email': data.get('email'),
                            'phone': data.get('phone'),
                            'location': data.get('location'),
                            'years_experience': data.get('years_experience', 0),
                            'linkedin': data.get('linkedin_url'),
                            'github': data.get('github_url'),
                            'portfolio': data.get('portfolio_url'),
                            'technologies': data.get('technologies', [])
                        })
                    
                    logger.debug(f"Loaded {json_file.name}")
            
            except Exception as e:
                logger.warning(f"Error loading {json_file.name}: {e}")
        
        return candidates
    
    def update_candidate_data(self, candidates: List[Dict]) -> int:
        """Update database with candidate data"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        count = 0
        
        try:
            for cand in candidates:
                # Skip if no name
                if 'candidate_name' not in cand:
                    continue
                
                name = cand.get('candidate_name', '')
                
                # Check if candidate exists
                cursor.execute(
                    'SELECT id FROM candidates WHERE candidate_name = ?',
                    (name,)
                )
                
                existing = cursor.fetchone()
                
                if not existing:
                    # Insert new candidate
                    cursor.execute('''
                    INSERT INTO candidates (
                        candidate_name, email, phone, location,
                        years_experience, linkedin, github, portfolio
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        name,
                        cand.get('email'),
                        cand.get('phone'),
                        cand.get('location'),
                        cand.get('years_experience', 0),
                        cand.get('linkedin'),
                        cand.get('github'),
                        cand.get('portfolio')
                    ))
                    count += 1
                    logger.debug(f"Inserted candidate: {name}")
            
            conn.commit()
            logger.info(f"Updated {count} candidates in database")
            return count
        
        except Exception as e:
            logger.error(f"Error updating candidates: {e}")
            conn.rollback()
            return 0
        
        finally:
            conn.close()
    
    def update_technologies(self, candidates: List[Dict]) -> int:
        """Update technologies/skills for candidates"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        count = 0
        
        try:
            for cand in candidates:
                name = cand.get('candidate_name', '')
                
                # Get candidate ID
                cursor.execute(
                    'SELECT id FROM candidates WHERE candidate_name = ?',
                    (name,)
                )
                
                result = cursor.fetchone()
                if not result:
                    continue
                
                cand_id = result[0]
                
                # Get technologies from candidate data
                techs = cand.get('technologies', [])
                if isinstance(techs, str):
                    techs = [t.strip() for t in techs.split(',')]
                
                for tech in techs:
                    if not tech:
                        continue
                    
                    # Check if tech exists for this candidate
                    cursor.execute('''
                    SELECT id FROM technologies 
                    WHERE candidate_id = ? AND tech_name = ?
                    ''', (cand_id, tech))
                    
                    if not cursor.fetchone():
                        # Insert new technology
                        cursor.execute('''
                        INSERT INTO technologies (
                            candidate_id, tech_name, category, proficiency_level
                        )
                        VALUES (?, ?, ?, ?)
                        ''', (cand_id, tech, 'skill', 'unknown'))
                        count += 1
            
            conn.commit()
            logger.info(f"Updated {count} technology records")
            return count
        
        except Exception as e:
            logger.error(f"Error updating technologies: {e}")
            conn.rollback()
            return 0
        
        finally:
            conn.close()
    
    def sync(self) -> bool:
        """Execute full sync process"""
        
        logger.info("="*80)
        logger.info("STARTING DATA SYNC")
        logger.info("="*80)
        
        # Discover latest session
        latest_session = self.discover_latest_session()
        
        if not latest_session:
            logger.warning("No session found to sync")
            return False
        
        # Check if sync is needed
        if not self.should_sync(latest_session):
            logger.info("Data already up-to-date, skipping sync")
            return True
        
        # Load candidate data
        candidates = self.load_candidates_from_json(latest_session)
        
        if not candidates:
            logger.warning("No candidates found to sync")
            return False
        
        logger.info(f"Found {len(candidates)} candidates to sync")
        
        # Update database
        updated = self.update_candidate_data(candidates)
        techs = self.update_technologies(candidates)
        
        # Update sync metadata
        self._update_sync_metadata(str(latest_session), len(candidates))
        
        logger.info("="*80)
        logger.info(f"SYNC COMPLETE: {updated} candidates, {techs} technologies")
        logger.info("="*80)
        
        return True
    
    def _update_sync_metadata(self, source_dir: str, candidates_count: int):
        """Update sync metadata in database"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO sync_metadata (
                source_dir, last_synced, candidates_count, status
            )
            VALUES (?, CURRENT_TIMESTAMP, ?, 'success')
            ''', (source_dir, candidates_count))
            
            conn.commit()
            logger.debug("Updated sync metadata")
        
        except Exception as e:
            logger.error(f"Error updating sync metadata: {e}")
        
        finally:
            conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    import os as _os
    from pathlib import Path as _Path
    # Action 227: archived sessions live under DATA_ROOT; the chatbot DB stays local.
    _data_root = _Path(_os.getenv("DATA_ROOT") or "data")
    db_path = 'data/chatbot_db/candidates.db'
    archive_dir = str(_data_root / 'archive')

    sync_engine = DataSyncEngine(db_path, archive_dir)
    sync_engine.sync()
