import hashlib
import re
from typing import List, Iterable

class SimHash:
    """
    A pure Python implementation of SimHash for structural fingerprinting.
    Used to detect changes in website layout/template (Tier-2/Anti-scraping detection).
    """
    
    def __init__(self, features: Iterable[str], hash_bits: int = 64):
        self.hash_bits = hash_bits
        self.hash = self.build_simhash(features)

    def build_simhash(self, features: Iterable[str]) -> str:
        """
        Compute SimHash from a list of features (e.g., HTML tags).
        """
        v = [0] * self.hash_bits
        
        for feature in features:
            # Hash the feature
            h = self._string_hash(feature)
            
            # Update vector
            for i in range(self.hash_bits):
                bitmask = 1 << i
                if h & bitmask:
                    v[i] += 1
                else:
                    v[i] -= 1
                    
        # Construct fingerprint
        fingerprint = 0
        for i in range(self.hash_bits):
            if v[i] > 0:
                fingerprint |= (1 << i)
                
        # Return as hex string
        return hex(fingerprint)[2:].zfill(self.hash_bits // 4)

    def _string_hash(self, v: str) -> int:
        """
        Generate a hash for a string feature.
        """
        return int(hashlib.md5(v.encode('utf-8')).hexdigest(), 16)

def compute_structural_simhash(html_content: str) -> str:
    """
    Extracts structure (tags only) and computes SimHash.
    Ignores content, attributes, and comments.
    
    Args:
        html_content (str): Raw HTML content.
        
    Returns:
        str: Hexadecimal SimHash fingerprint.
    """
    if not html_content:
        return ""
        
    # Regex to extract tag names (e.g., 'div', 'a', 'span')
    # Matches <tag or </tag
    tags = re.findall(r'<[/]?([a-zA-Z0-9]+)[^>]*>', html_content)
    
    # Normalize tags to lowercase
    normalized_tags = [t.lower() for t in tags]
    
    if not normalized_tags:
        return ""
        
    sh = SimHash(normalized_tags)
    return sh.hash
