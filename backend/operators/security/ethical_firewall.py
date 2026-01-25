import logging
from typing import Tuple, Optional
try:
    from transformers import pipeline
except ImportError:
    pipeline = None

logger = logging.getLogger(__name__)

class EthicalFirewallOperator:
    """
    Ethical Firewall: Filters out unsafe, toxic, or extremist content.
    
    Research Motivation:
        - Prevents the ingestion of harmful content (Hate Speech, NSFW, Extremism).
        - Ensures the dataset remains clean and safe for downstream analysis.
        - Uses a pre-trained Transformer model (Safety-BERT concept) for classification.
    """
    
    def __init__(self, model_name: str = "unitary/toxic-bert", threshold: float = 0.7):
        self.enabled = False
        self.threshold = threshold
        
        if not pipeline:
            logger.warning("Transformers library not installed. Ethical Firewall disabled.")
            return

        try:
            logger.info(f"Loading Ethical Firewall model: {model_name}...")
            # Use a pipeline for text classification. 
            # 'return_all_scores=True' allows us to see all labels (toxic, severe_toxic, obscene, threat, insult, identity_hate)
            self.classifier = pipeline("text-classification", model=model_name, top_k=None)
            self.enabled = True
            logger.info("Ethical Firewall initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to load Ethical Firewall model: {e}")
            self.enabled = False

    def check_safety(self, text: str) -> Tuple[bool, str, float]:
        """
        Checks if the text contains unsafe content.
        
        Args:
            text (str): The content to check (Title + Description).
            
        Returns:
            Tuple[bool, str, float]: (is_safe, label, max_score)
        """
        if not self.enabled or not text:
            return True, "safe", 0.0
            
        try:
            # Truncate text to 512 tokens (approx 2000 chars) to fit BERT limits
            truncated_text = text[:2000]
            results = self.classifier(truncated_text)
            
            # results is a list of lists of dicts (for batch size 1)
            # [[{'label': 'toxic', 'score': 0.9}, {'label': 'severe_toxic', 'score': 0.1}, ...]]
            scores = results[0]
            
            max_score = 0.0
            primary_label = "safe"
            is_unsafe = False
            
            for item in scores:
                label = item['label']
                score = item['score']
                
                # Check against toxicity categories
                # Note: 'unitary/toxic-bert' outputs: toxic, severe_toxic, obscene, threat, insult, identity_hate
                if score > max_score:
                    max_score = score
                    primary_label = label
                
                if score > self.threshold:
                    is_unsafe = True
            
            if is_unsafe:
                return False, primary_label, max_score
            else:
                return True, "safe", max_score
                
        except Exception as e:
            logger.error(f"Error during safety check: {e}")
            # Fail open (safe) or fail closed (unsafe)? 
            # For research pipelines, usually fail open but log error to avoid data loss due to model error.
            return True, "error", 0.0

# Singleton Instance
ethical_firewall = EthicalFirewallOperator()
