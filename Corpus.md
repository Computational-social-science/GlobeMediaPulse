# Building a Global News English Vocabulary (2015–Present)  
### For Spelling Error Research

To build a comprehensive vocabulary of news English covering the globe with a time span of nearly a decade (January 1, 2015 to present), and to support spelling error behavior research, I recommend a **hierarchical, multi-source, dynamic-static combined** strategy. This approach ensures both authority and broad coverage of global English variants and real news contexts.

*(The original document includes a diagram illustrating the complete workflow and data source framework. Diagram not available in text version.)*

## Core Data Sources & Acquisition Methods

| Category                        | Recommended Resources                          | Description & Acquisition Method |
|---------------------------------|------------------------------------------------|----------------------------------|
| Authority Benchmark Lexicons    | Oxford / Merriam-Webster Dictionaries          | Authoritative reference. Full wordlists usually require official API or licensed data products. |
|                                 | SCOWL Wordlists                                | Designed for spell-checking; integrates multiple sources, distinguishes common vs. domain words. Free and programmatically accessible. |
|                                 | WordNet                                        | Princeton University lexical database with rich semantic relations. Easily downloadable via Python NLTK library. |
| Dynamic News Corpora            | NOW Corpus                                     | 2016–present, 20+ countries, >3 billion words, daily updates. Core news vocabulary source. Wordlist available through the corpus providers. |
|                                 | Global Humanitarian News Corpus                | 1.1 million English humanitarian news articles (2010–2020), frequency matrix for 79,229 lemmas. Useful supplement. |
|                                 | GDELT Project                                  | Real-time global news monitoring. Extract high-frequency words via BigQuery (`gdelt-bq.extra.englishwords`) or analyze Global Knowledge Graph. |
| Global Variants & Error Data    | Country-specific English Variant Dictionaries  | e.g., *Dictionary of Caribbean English Usage*, etc. |
|                                 | Birkbeck Spelling Error Corpus                 | 36,133 spelling errors across 6,136 words. Classic dataset for error research; downloadable from project website. |

## Building Steps & Technical Recommendations

### 1. Data Collection & Cleaning
- Use Python (`requests`, `beautifulsoup4`) to download or crawl publicly available wordlists and datasets.
- Clean text: remove punctuation, numbers, HTML tags; convert to lowercase.
- Apply lemmatization using **NLTK** or **spaCy** to normalize different word forms into lemmas.

### 2. Vocabulary Integration & Deduplication
- Merge all lemmas from every source into a single set.
- Remove duplicates while recording the original source(s) for each word (for traceability).

### 3. Word Frequency & Metadata Annotation
- Calculate frequency of each word in news texts since 2015 using NOW, GDELT, etc.
- Add metadata: SCOWL tier, presence in Oxford/Webster, per-country frequency, domain tags, etc.

### 4. Spelling Error Mapping
- Map “error → correct” pairs from Birkbeck (and other error corpora) onto your vocabulary list.

### 5. Validation & Classification
- Use **PyEnchant** (with SCOWL/Oxford as backend) to validate spelling correctness.
- Classify entries as: standard, regional variant, domain-specific, neologism, etc.
- Manually or semi-automatically verify high-frequency entities/topics from GDELT.

## Key Considerations

- **Scale & Representativeness** — Target vocabulary size: hundreds of thousands to low millions. Must represent news English from all 194 countries, not just US/UK varieties.
- **Legal & Ethical** — Strictly follow license terms of each dataset (especially NOW Corpus). Use only for research and provide proper citations.
- **Recommended Tools**:
  - Data processing: **Pandas**
  - Text processing: **NLTK** / **spaCy**
  - Spell checking: **PyEnchant**

This framework provides a complete, reproducible pipeline from data acquisition to final vocabulary construction. If you have a specific research focus (e.g., particular regions, error types, or news domains), the data sources and workflow can be further refined.
