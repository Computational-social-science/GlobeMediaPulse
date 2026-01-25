import logging
from typing import Optional
try:
    from transformers import pipeline
except ImportError:
    pipeline = None

logger = logging.getLogger(__name__)

class NarrativeAnalystOperator:
    """
    Narrative Analyst: Quantifies sentiment and narrative stance.
    
    Research Motivation:
        - Computes 'Sentiment Delta' to measure 'Narrative Divergence' between media tiers.
        - Provides the raw 'sentiment_score' (-1.0 to 1.0) for downstream aggregation.
    """
    
    def __init__(self, model_name: str = "distilbert-base-uncased-finetuned-sst-2-english"):
        self.enabled = False
        
        if not pipeline:
            logger.warning("Transformers library not installed. Narrative Analyst disabled.")
            return

        try:
            logger.info(f"Loading Sentiment model: {model_name}...")
            self.analyzer = pipeline("sentiment-analysis", model=model_name)
            self.enabled = True
        except Exception as e:
            logger.error(f"Failed to load Sentiment model: {e}")
            self.enabled = False

    def analyze_sentiment(self, text: str) -> Optional[float]:
        """
        Computes a normalized sentiment score (-1.0 to 1.0).
        
        Args:
            text (str): Content to analyze.
            
        Returns:
            float: Score from -1.0 (Negative) to 1.0 (Positive).
        """
        if not self.enabled or not text:
            return None
            
        try:
            # Truncate
            truncated_text = text[:512]
            result = self.analyzer(truncated_text)[0]
            # result: {'label': 'POSITIVE', 'score': 0.99}
            
            label = result['label']
            score = result['score']
            
            # Normalize to -1.0 to 1.0
            if label == 'NEGATIVE':
                return -score
            else:
                return score
                
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return None

# Singleton Instance
narrative_analyst = NarrativeAnalystOperator()
