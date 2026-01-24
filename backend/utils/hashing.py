import hashlib

def generate_url_hash(url: str) -> str:
    """
    Generate a SHA-256 hash fingerprint for a given URL.
    
    Args:
        url (str): The URL to hash.
        
    Returns:
        str: The 64-character hexadecimal SHA-256 hash.
    """
    if not url:
        return ""
    return hashlib.sha256(url.encode('utf-8')).hexdigest()
