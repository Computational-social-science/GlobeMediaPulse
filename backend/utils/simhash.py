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

    def hamming_distance(self, other_hash: str) -> int:
        """
        Compute Hamming distance between this hash and another hex string hash.
        """
        # Convert hex strings to integers
        h1 = int(self.hash, 16)
        h2 = int(other_hash, 16)
        
        # XOR to find different bits
        x = h1 ^ h2
        
        # Count set bits (Hamming distance)
        return bin(x).count('1')

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
    
    # [Improvement] Include hrefs (links) as structural features.
    # This ensures that if the news content (links) changes, the SimHash changes,
    # allowing for effective incremental update detection.
    links = re.findall(r'href=["\'](.*?)["\']', html_content)
    
    # Normalize tags to lowercase
    features = [t.lower() for t in tags]
    
    # Add link features (weighted or raw)
    # We strip query params to focus on path structure
    for link in links:
        if link and not link.startswith('#') and not link.startswith('javascript'):
            features.append(f"link:{link.split('?')[0]}")
    
    if not features:
        return ""
        
    sh = SimHash(features)
    return sh.hash

def is_similar(hash1: str, hash2: str, threshold: int = 3) -> bool:
    """
    Checks if two SimHashes are similar (Hamming distance <= threshold).
    Default threshold 3 is common for near-duplicate detection in 64-bit hashes.
    """
    if not hash1 or not hash2:
        return False
        
    # Convert hex strings to integers
    h1 = int(hash1, 16)
    h2 = int(hash2, 16)
    
    x = h1 ^ h2
    return bin(x).count('1') <= threshold
