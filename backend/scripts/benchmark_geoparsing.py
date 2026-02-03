import sys
import os
import time
import csv
import logging
from typing import List, Dict, Any
from unittest.mock import MagicMock
from sklearn.metrics import f1_score, confusion_matrix

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Benchmark")

# Mock Redis for GeoParser if not available
mock_redis = MagicMock()
mock_redis.from_url.return_value.get.return_value = None # Cache miss by default
sys.modules['redis'] = mock_redis

try:
    from backend.operators.intelligence.geo_resolver import GeoResolver
except ImportError as e:
    logger.error(f"Import failed: {e}")
    sys.exit(1)

GOLDEN_DATASET_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/golden_url_dataset.csv'))

def load_golden_dataset():
    if not os.path.exists(GOLDEN_DATASET_PATH):
        logger.error(f"Golden dataset not found at {GOLDEN_DATASET_PATH}")
        return []
    
    data = []
    with open(GOLDEN_DATASET_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

def run_benchmark():
    logger.info("==================================================")
    logger.info("       GEOPARSING SOLUTION BENCHMARK REPORT       ")
    logger.info("==================================================")

    # 1. Load Test Data
    test_data = load_golden_dataset()
    if not test_data:
        # Fallback to small list if no file
        logger.warning("Using fallback small dataset.")
        test_data = [
            {"url": "http://www.nytimes.com/article/1", "country_label": "USA"},
            {"url": "https://www.bbc.co.uk/news", "country_label": "GBR"},
            {"url": "https://www.chinadaily.com.cn", "country_label": "CHN"},
            {"url": "http://tech.io", "country_label": "UNK"}
        ]
    
    logger.info(f"Test Dataset Size: {len(test_data)} URLs")
    
    # 2. Initialize Engine
    logger.info("\n[Initialization]")
    try:
        t0 = time.time()
        new_engine = GeoResolver()
        t_new_init = (time.time() - t0) * 1000
        logger.info(f"New GeoResolver Init: {t_new_init:.2f} ms")
    except Exception as e:
        logger.error(f"New GeoResolver Init Failed: {e}")
        return

    # 3. Run Inference
    y_true = []
    y_pred = []
    latencies = []
    
    logger.info("\n[Running Inference...]")
    for i, row in enumerate(test_data):
        url = row['url']
        expected = row['country_label']
        
        t0 = time.time()
        try:
            res = new_engine.resolve(url)
            predicted = res.get("country_code", "UNK")
        except Exception:
            predicted = "ERR"
        t_latency = (time.time() - t0) * 1000
        
        y_true.append(expected)
        y_pred.append(predicted)
        latencies.append(t_latency)
        
        if i % 100 == 0 and i > 0:
            print(f"Processed {i}/{len(test_data)}...")

    # 4. Metrics
    avg_latency = sum(latencies) / len(latencies)
    macro_f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)
    
    logger.info("\n[Performance Metrics]")
    logger.info(f"Average Latency: {avg_latency:.2f} ms")
    logger.info(f"Macro-F1 Score:  {macro_f1:.4f}")
    
    # Check Threshold
    THRESHOLD = 0.95
    if macro_f1 >= THRESHOLD:
        logger.info(f"\n✅ SUCCESS: Macro-F1 ({macro_f1:.4f}) >= {THRESHOLD}")
    else:
        logger.error(f"\n❌ FAILURE: Macro-F1 ({macro_f1:.4f}) < {THRESHOLD}")
        
    # Confusion Matrix (Top 5 Classes)
    logger.info("\n[Confusion Matrix Sample (Top Classes)]")
    labels = sorted(list(set(y_true)))
    # Simple print of mismatches
    errors = 0
    for true, pred in zip(y_true, y_pred):
        if true != pred:
            if errors < 10:
                logger.info(f"Mismatch: Expected {true}, Got {pred}")
            errors += 1
    logger.info(f"Total Mismatches: {errors}/{len(test_data)}")

if __name__ == "__main__":
    run_benchmark()
