import logging
import re
import requests
from io import BytesIO
from PIL import Image
import imagehash
from typing import Optional

logger = logging.getLogger(__name__)

class VisualFingerprintOperator:
    """
    Operator for Visual and Textual Fingerprinting of Media Sources.
    
    Research Motivation:
        - **Sockpuppet Detection**: Identifies "Coordination Networks" where multiple ostensibly independent
          sites share the same visual identity (Logo/Favicon) or legal templates (Copyright text).
        - **Logo Recognition**: Uses Perceptual Hashing (pHash) to detect identical or near-identical logos
          resilient to resizing, format changes, and minor color shifts.
    """
    
    def __init__(self):
        # Common user agent for image downloading
        self.headers = {
            'User-Agent': 'GlobeMediaPulse/2.0 (Scientific Research; +http://globemediapulse.org)'
        }

    def compute_logo_hash(self, image_url: str) -> Optional[str]:
        """
        Downloads an image and computes its Perceptual Hash (pHash).
        
        Args:
            image_url (str): The URL of the logo or favicon.
            
        Returns:
            str: Hex string of the hash, or None if failed.
        """
        if not image_url:
            return None
            
        try:
            response = requests.get(image_url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                # Compute pHash (robust to scaling/aspect ratio)
                phash = imagehash.phash(img)
                return str(phash)
        except Exception as e:
            logger.warning(f"Failed to compute hash for {image_url}: {e}")
            return None
            
    def extract_copyright(self, html_content: str) -> Optional[str]:
        """
        Extracts copyright notice from HTML content.
        
        Methodology:
            - Heuristic Regex matching for patterns like "© 2024 Media Name" or "Copyright 2024".
            - Normalizes whitespace.
            
        Returns:
            str: Normalized copyright text or None.
        """
        if not html_content:
            return None
            
        # Regex to find copyright patterns
        # Matches: ©, (c), Copyright followed by year/text
        pattern = r"(?:©|&copy;|&#169;|Copyright)\s*(?:20\d{2})?.*?(?=\.|<|$)"
        
        match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            text = match.group(0)
            # Clean tags and whitespace
            text = re.sub(r'<[^>]+>', '', text)
            text = " ".join(text.split())
            return text[:200] # Truncate to reasonable length
            
        return None

# Singleton Instance
visual_fingerprinter = VisualFingerprintOperator()
