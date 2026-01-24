import nltk
import os

# Set download directory
nltk_data_dir = os.path.join(os.getcwd(), 'backend', 'nltk_data')
if not os.path.exists(nltk_data_dir):
    os.makedirs(nltk_data_dir)

nltk.data.path.append(nltk_data_dir)

resources = [
    'punkt',
    'punkt_tab',
    'averaged_perceptron_tagger',
    'averaged_perceptron_tagger_eng',
    'maxent_ne_chunker',
    'words',
    'wordnet'
]

print(f"Downloading NLTK resources to {nltk_data_dir}...")
for r in resources:
    print(f"Downloading {r}...")
    try:
        nltk.download(r, download_dir=nltk_data_dir)
    except Exception as e:
        print(f"Failed to download {r}: {e}")

print("Done.")