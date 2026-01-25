import logging
import requests
import json
from typing import List, Dict, Any, Optional

try:
    import spacy
except ImportError:
    spacy = None

logger = logging.getLogger(__name__)

class EntityAlignerOperator:
    """
    Cross-Lingual Entity Alignment Operator.
    
    Research Motivation:
        - Maps diverse textual representations (e.g., "Ukraine", "Украина") to a single semantic ID (Wikidata QID).
        - Enables global, language-agnostic event aggregation.
    """
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        self.enabled = False
        self.nlp = None
        
        if not spacy:
            logger.warning("SpaCy not installed. Entity Alignment disabled.")
            return

        try:
            logger.info(f"Loading NER model: {model_name}...")
            if not spacy.util.is_package(model_name):
                logger.info(f"Downloading {model_name}...")
                spacy.cli.download(model_name)
            self.nlp = spacy.load(model_name)
            self.enabled = True
        except Exception as e:
            logger.error(f"Failed to load NER model: {e}")
            self.enabled = False
            
    def get_wikidata_qid(self, entity_text: str, language: str = "en") -> Optional[str]:
        """
        Queries Wikidata API to resolve an entity text to a QID.
        """
        if not entity_text:
            return None
            
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": entity_text,
            "language": language,
            "format": "json",
            "limit": 1
        }
        
        try:
            response = requests.get(url, params=params, timeout=3)
            if response.status_code == 200:
                data = response.json()
                results = data.get("search", [])
                if results:
                    return results[0].get("id") # e.g., "Q212"
        except Exception as e:
            # Silent fail to avoid spamming logs for every entity
            pass
            
        return None

    def extract_and_align(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts entities and maps them to QIDs.
        
        Args:
            text (str): Input text.
            
        Returns:
            List[Dict]: List of {'text': 'Ukraine', 'label': 'GPE', 'qid': 'Q212'}
        """
        if not self.enabled or not text:
            return []
            
        doc = self.nlp(text)
        aligned_entities = []
        
        # Limit to top 5 entities to respect API limits and performance
        # Focus on GPE (Geopolitical Entity), ORG, PERSON
        target_labels = {"GPE", "ORG", "PERSON", "LOC"}
        
        seen_texts = set()
        
        for ent in doc.ents:
            if ent.label_ in target_labels and ent.text not in seen_texts:
                qid = self.get_wikidata_qid(ent.text)
                aligned_entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "qid": qid
                })
                seen_texts.add(ent.text)
                
                if len(aligned_entities) >= 5:
                    break
                    
        return aligned_entities

# Singleton Instance
entity_aligner = EntityAlignerOperator()
