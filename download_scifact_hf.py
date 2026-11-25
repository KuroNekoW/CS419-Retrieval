
from pathlib import Path
from shutil import copyfile
from datasets import load_dataset
from huggingface_hub import hf_hub_download

OUTPUT_DIR = Path("data/raw/scifact")
QRELS_DIR = OUTPUT_DIR / "qrels"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
QRELS_DIR.mkdir(parents=True, exist_ok=True)

# 1. Download corpus
print("Downloading corpus...")

corpus = load_dataset(
    "BeIR/scifact",
    "corpus",
    split="corpus"
)

corpus.to_json(
    str(OUTPUT_DIR / "corpus.jsonl"),
    orient="records",
    lines=True,
    force_ascii=False
)

# 2. Download queries
print("Downloading queries...")

queries = load_dataset(
    "BeIR/scifact",
    "queries",
    split="queries"
)

queries.to_json(
    str(OUTPUT_DIR / "queries.jsonl"),
    orient="records",
    lines=True,
    force_ascii=False
)

# 3. Download relevance judgments
for split in ["train", "test"]:
    print(f"Downloading {split} qrels...")

    file_path = hf_hub_download(
        repo_id="BeIR/scifact-qrels",
        filename=f"{split}.tsv",
        repo_type="dataset"
    )

    copyfile(
        file_path,
        QRELS_DIR / f"{split}.tsv"
    )

# 4. Display dataset information
print("\nDownload completed!")
print(f"Corpus: {len(corpus)} documents")
print(f"Queries: {len(queries)} queries")
print(f"Saved to: {OUTPUT_DIR.resolve()}")
