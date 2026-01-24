
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.operators.storage import storage_operator

def insert_fake_data():
    print("Inserting fake data for UI verification...")
    
    # Fake errors for 2017
    fake_errors = [
        {
            "word": "teh",
            "suggestion": "the",
            "context": "This is teh context.",
            "corrected_context": "This is the context.",
            "timestamp": "2017-01-01T12:00:00Z",
            "country_code": "US",
            "country_name": "United States",
            "url": "http://fake.com/1",
            "title": "Fake News 1"
        },
        {
            "word": "wrold",
            "suggestion": "world",
            "context": "Hello wrold.",
            "corrected_context": "Hello world.",
            "timestamp": "2017-06-15T12:00:00Z",
            "country_code": "GB",
            "country_name": "United Kingdom",
            "url": "http://fake.com/2",
            "title": "Fake News 2"
        },
        {
            "word": "compay",
            "suggestion": "company",
            "context": "A big compay.",
            "corrected_context": "A big company.",
            "timestamp": "2017-12-31T12:00:00Z",
            "country_code": "CN",
            "country_name": "China",
            "url": "http://fake.com/3",
            "title": "Fake News 3"
        }
    ]
    
    with storage_operator.get_connection() as conn:
        cursor = conn.cursor()
        for err in fake_errors:
            cursor.execute('''
                INSERT INTO error_events (country_code, country_name, word, suggestion, timestamp, context, corrected_context, title, url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                err["country_code"], err["country_name"], err["word"], err["suggestion"],
                err["timestamp"], err["context"], err["corrected_context"], err["title"], err["url"]
            ))
        conn.commit()
    
    print("Inserted 3 fake error events.")

if __name__ == "__main__":
    insert_fake_data()
