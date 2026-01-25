import logging
import os
from pathlib import Path
from typing import Optional

try:
    from transformers import pipeline, AutoTokenizer
except ImportError:
    pipeline = None

# ONNX Runtime Support
try:
    from optimum.onnxruntime import ORTModelForSequenceClassification
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

logger = logging.getLogger(__name__)

class NarrativeAnalystOperator:
    """
    Narrative Analyst: Quantifies sentiment and narrative stance.
    
    Research Motivation:
        - Computes 'Sentiment Delta' to measure 'Narrative Divergence' between media tiers.
        - Provides the raw 'sentiment_score' (-1.0 to 1.0) for downstream aggregation.
        - Supports ONNX Runtime for optimized inference (Quantized Models).
    """
    
    def __init__(self, model_name: str = "distilbert-base-uncased-finetuned-sst-2-english"):
        self.model_name = model_name
        self.analyzer = None
        self._enabled_status = None # Tri-state: None (Unknown), True, False
        self.onnx_mode = False

    @property
    def enabled(self) -> bool:
        if self._enabled_status is None:
             self._initialize_model()
        return self._enabled_status

    def _initialize_model(self):
        if not pipeline:
            logger.warning("Transformers library not installed. Narrative Analyst disabled.")
            self._enabled_status = False
            return

        # 1. Try Loading ONNX Model (Optimized)
        onnx_path = Path(os.getcwd()) / "backend" / "resources" / "models" / "sentiment_onnx"
        if ONNX_AVAILABLE and onnx_path.exists():
            try:
                logger.info(f"Loading Quantized ONNX Model from {onnx_path}...")
                model = ORTModelForSequenceClassification.from_pretrained(onnx_path)
                tokenizer = AutoTokenizer.from_pretrained(onnx_path)
                self.analyzer = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)
                self.onnx_mode = True
                self._enabled_status = True
                logger.info("ONNX Sentiment model loaded successfully (Accelerated).")
                return
            except Exception as e:
                logger.warning(f"Failed to load ONNX model, falling back to PyTorch: {e}")

        # 2. Fallback to Standard PyTorch Model
        try:
            logger.info(f"Lazy loading Standard PyTorch Model: {self.model_name}...")
            self.analyzer = pipeline("sentiment-analysis", model=self.model_name)
            self._enabled_status = True
            logger.info("Sentiment model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Sentiment model: {e}")
            self._enabled_status = False

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
