import nltk
import os

resources = [
    'punkt',
    'averaged_perceptron_tagger',
    'maxent_ne_chunker',
    'words',
    'wordnet'
]

print("Downloading NLTK resources...")
for r in resources:
    print(f"Downloading {r}...")
    nltk.download(r)
print("Done.")