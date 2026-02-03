import csv
import random

# Common media domains by country (Tier 1/2)
DOMAINS = {
    "USA": ["nytimes.com", "cnn.com", "wsj.com", "washingtonpost.com", "foxnews.com", "usatoday.com", "nbcnews.com", "cnbc.com", "bloomberg.com", "npr.org"],
    "GBR": ["bbc.co.uk", "reuters.com", "theguardian.com", "independent.co.uk", "dailymail.co.uk", "telegraph.co.uk", "skynews.com"],
    "CHN": ["xinhuanet.com", "chinadaily.com.cn", "globaltimes.cn", "scmp.com"],
    "FRA": ["lemonde.fr", "lefigaro.fr", "france24.com", "euronews.com"],
    "DEU": ["dw.com", "spiegel.de", "bild.de", "zeit.de"],
    "JPN": ["nhk.or.jp", "asahi.com", "japantimes.co.jp", "kyodonews.net"],
    "RUS": ["rt.com", "tass.com", "moscowtimes.ru"],
    "IND": ["thehindu.com", "timesofindia.indiatimes.com", "hindustantimes.com"],
    "BRA": ["folha.uol.com.br", "estadao.com.br", "oglobo.globo.com"],
    "UNK": ["example.com", "test.io", "startup.ai", "cloud.net"]
}

# Generate 1000 items (Proof of Concept for 10k)
DATASET_SIZE = 1000
OUTPUT_FILE = "data/golden_url_dataset.csv"

def generate_url(domain):
    protocols = ["http", "https"]
    paths = ["/article/123", "/news/world", "/2026/01/01/title", ""]
    return f"{random.choice(protocols)}://www.{domain}{random.choice(paths)}"

def main():
    print(f"Generating {DATASET_SIZE} golden records...")
    
    records = []
    
    # Ensure representation of all categories
    for country, domains in DOMAINS.items():
        for domain in domains:
            records.append((generate_url(domain), country))
            
    # Fill the rest randomly
    while len(records) < DATASET_SIZE:
        country = random.choice(list(DOMAINS.keys()))
        domain = random.choice(DOMAINS[country])
        records.append((generate_url(domain), country))
        
    random.shuffle(records)
    
    # Write to CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "country_label"])
        writer.writerows(records)
        
    print(f"Dataset saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()