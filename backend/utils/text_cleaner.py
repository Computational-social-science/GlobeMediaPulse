import re
import unicodedata
import logging

logger = logging.getLogger(__name__)

class UnicodeSpaceCleaner:
    """
    High-performance text cleaner for normalizing Unicode whitespace and removing noise.
    
    Design Philosophy:
    - Uses str.translate (C-level) for extremely fast character mapping.
    - Targets 25+ specific Unicode whitespace characters (including invisible separators).
    - Provides layered regex cleaning for common web scraper noise (emails, social handles, CTAs).
    - Ensures consistency for downstream tasks like SimHash (Event Fingerprinting) and Geocoding.
    """
    def __init__(self):
        # 1. Build Translation Table for 25+ Unicode Spaces
        # Maps all variants to a single ASCII space (0x20)
        self.whitespace_codepoints = {
            0x0009, # CHARACTER TABULATION
            0x000A, # LINE FEED
            0x000B, # LINE TABULATION
            0x000C, # FORM FEED
            0x000D, # CARRIAGE RETURN
            0x0020, # SPACE
            0x0085, # NEXT LINE
            0x00A0, # NO-BREAK SPACE
            0x1680, # OGHAM SPACE MARK
            0x2000, # EN QUAD
            0x2001, # EM QUAD
            0x2002, # EN SPACE
            0x2003, # EM SPACE
            0x2004, # THREE-PER-EM SPACE
            0x2005, # FOUR-PER-EM SPACE
            0x2006, # SIX-PER-EM SPACE
            0x2007, # FIGURE SPACE
            0x2008, # PUNCTUATION SPACE
            0x2009, # THIN SPACE
            0x200A, # HAIR SPACE
            0x2028, # LINE SEPARATOR
            0x2029, # PARAGRAPH SEPARATOR
            0x202F, # NARROW NO-BREAK SPACE
            0x205F, # MEDIUM MATHEMATICAL SPACE
            0x3000, # IDEOGRAPHIC SPACE
            0x180E, # MONGOLIAN VOWEL SEPARATOR (Historical whitespace)
            0x200B, # ZERO WIDTH SPACE (Invisible)
            0xFEFF, # ZERO WIDTH NO-BREAK SPACE
        }
        
        self.trans_table = {cp: ' ' for cp in self.whitespace_codepoints}
        
        # 2. Regex for collapsing multiple spaces
        self.whitespace_re = re.compile(r'\s+')
        
        # 3. Layered Noise Patterns (Regex)
        self.noise_patterns = [
            # Social Media Handles (e.g. @username) - conservative to avoid emails
            re.compile(r'(?<!\w)@[\w_]{3,}'), 
            
            # Emails
            re.compile(r'[\w\.-]+@[\w\.-]+\.\w+'),
            
            # Common News Scraper Noise / CTAs
            re.compile(r'(?i)read more at.*?$'),
            re.compile(r'(?i)click here to.*?$'),
            re.compile(r'(?i)follow us on.*?$'),
            re.compile(r'(?i)subscribe to.*?$'),
            re.compile(r'(?i)sign up for.*?$'),
            re.compile(r'http[s]?://\S+'), # Raw URLs
        ]

    def clean(self, text: str) -> str:
        """
        Execute the cleaning pipeline.
        
        Steps:
        1. Translate: Unicode Whitespace -> ASCII Space (Fastest)
        2. Normalize: NFKC Normalization (Standardize characters)
        3. Regex: Remove specific noise patterns (URLs, CTAs)
        4. Collapse: Merge multiple spaces into one and trim
        
        Args:
            text (str): Raw input text.
            
        Returns:
            str: Cleaned, normalized text.
        """
        if not text:
            return ""
            
        # Step 1: Unicode Translation (High Performance)
        # Effectively turns all 25+ variants into ' '
        text = text.translate(self.trans_table)
        
        # Step 2: NFKC Normalization
        # Converts compatibility characters (like ﬀ -> ff, ⁹ -> 9)
        text = unicodedata.normalize('NFKC', text)
        
        # Step 3: Noise Removal
        for pattern in self.noise_patterns:
            text = pattern.sub(' ', text)
            
        # Step 4: Collapse & Trim
        text = self.whitespace_re.sub(' ', text).strip()
        
        return text

# Global Instance
global_cleaner = UnicodeSpaceCleaner()
