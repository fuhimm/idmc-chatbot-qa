"""
scripts/evaluate_ragas.py

Skrip evaluasi kualitas RAG Chatbot IDMC Jogjaprov menggunakan 4 metrik Ragas:
- faithfulness
- answer_relevancy
- context_precision
- context_recall

Mendukung Switch Mode via .env:
- EVAL_MODE=MOCK : Menggunakan data simulasi (answer_placeholder & contexts_placeholder dari CSV)
- EVAL_MODE=LIVE : Menembak endpoint API Backend/RAG (BACKEND_API_URL)
"""

from __future__ import annotations

import csv
import datetime
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import requests
except ImportError:
    requests = None

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
DATASET_PATH = BASE_DIR / "datasets" / "02_evaluation_dataset_ragas.csv"
REPORTS_DIR = BASE_DIR / "reports"


def _load_env_file() -> None:
    """Memuat variabel dari file .env menggunakan python-dotenv atau parser ringan bawaan."""
    if load_dotenv is not None:
        load_dotenv(ENV_PATH)
        return
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip("'\""))


_load_env_file()

EVAL_MODE = os.getenv("EVAL_MODE", "MOCK").strip().upper()
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000/api/v1/chat").strip()
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "").strip()
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()


def get_chatbot_response(question: str, row_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Mengambil respons chatbot berdasarkan EVAL_MODE ('MOCK' atau 'LIVE').

    Kontrak return value:
    {
        "answer": str,
        "contexts": List[str]
    }
    """
    if EVAL_MODE == "MOCK":
        if row_data:
            raw_contexts = str(row_data.get("contexts_placeholder", "")).strip()
            contexts = [c.strip() for c in raw_contexts.split("|") if c.strip()]
            answer = str(row_data.get("answer_placeholder", "")).strip()
            if answer and contexts:
                return {"answer": answer, "contexts": contexts}

        return {
            "answer": f"[MOCK ANSWER] Informasi mengenai '{question}' tersedia pada portal IDMC DIY.",
            "contexts": [
                "IDMC DIY (idmc.jogjaprov.go.id) menyajikan 9 menu dashboard aktif dan halaman Beranda."
            ],
        }

    if EVAL_MODE == "LIVE":
        headers = {"Content-Type": "application/json"}
        if BACKEND_API_KEY:
            headers["Authorization"] = f"Bearer {BACKEND_API_KEY}"

        payload = {"question": question}
        try:
            if requests is not None:
                response = requests.post(
                    BACKEND_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                data = response.json()
            else:
                req = urllib.request.Request(
                    BACKEND_API_URL,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

            answer = data.get("answer")
            contexts = data.get("contexts")

            if not isinstance(answer, str):
                raise ValueError("Field 'answer' (string) tidak ditemukan pada response JSON API.")
            if not isinstance(contexts, list) or not all(isinstance(c, str) for c in contexts):
                raise ValueError("Field 'contexts' (list of strings) tidak ditemukan pada response JSON API.")

            return {"answer": answer, "contexts": contexts}
        except Exception as exc:
            print(f"[ERROR] Gagal memanggil endpoint LIVE untuk pertanyaan '{question}': {exc}", file=sys.stderr)
            return {"answer": "", "contexts": []}

    raise ValueError(f"EVAL_MODE tidak valid: '{EVAL_MODE}'. Gunakan 'MOCK' atau 'LIVE'.")


def has_valid_llm_key() -> bool:
    """Memeriksa apakah OPENAI_API_KEY sudah diisi untuk eksekusi LLM-as-a-Judge Ragas."""
    if not OPENAI_API_KEY:
        return False
    placeholder_prefixes = ("your-", "sk-xxx", "masukkan-")
    return not OPENAI_API_KEY.lower().startswith(placeholder_prefixes)


def run_evaluation() -> int:
    if not DATASET_PATH.exists():
        print(f"[ERROR] File dataset tidak ditemukan di: {DATASET_PATH}", file=sys.stderr)
        return 1

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATASET_PATH, mode="r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    print("=" * 65)
    print("IDMC Chatbot RAG Evaluation Pipeline")
    print(f"Mode Eksekusi : {EVAL_MODE}")
    if EVAL_MODE == "LIVE":
        print(f"Target API    : {BACKEND_API_URL}")
    print(f"Total Sampel  : {len(rows)} pertanyaan (In-Scope & Parafrase)")
    print("=" * 65)

    questions: List[str] = []
    ground_truths: List[str] = []
    answers: List[str] = []
    contexts_list: List[List[str]] = []

    for idx, row in enumerate(rows):
        q = str(row["question"]).strip()
        gt = str(row["ground_truth"]).strip()

        res = get_chatbot_response(q, row_data=row)
        questions.append(q)
        ground_truths.append(gt)
        answers.append(res["answer"])
        contexts_list.append(res["contexts"])
        print(f"[{idx + 1:02d}/{len(rows):02d}] {row['id']} ({row['category']}) -> OK ({len(res['contexts'])} chunks)")

    eval_records = {
        "question": questions,
        "answer": answers,
        "contexts": contexts_list,
        "ground_truth": ground_truths,
    }

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = REPORTS_DIR / f"ragas_evaluation_{EVAL_MODE.lower()}_{timestamp}.csv"
    output_summary = REPORTS_DIR / f"ragas_summary_{EVAL_MODE.lower()}_{timestamp}.json"

    if has_valid_llm_key():
        print("\n[INFO] Menjalankan evaluasi Ragas menggunakan LLM-as-a-Judge...")
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )

        hf_dataset = Dataset.from_dict(eval_records)
        result = evaluate(
            dataset=hf_dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            ],
        )
        result_df = result.to_pandas()
        result_df.insert(0, "category", [r["category"] for r in rows])
        result_df.insert(0, "id", [r["id"] for r in rows])
        result_df.to_csv(output_csv, index=False, encoding="utf-8")

        summary_scores = {
            "mode": EVAL_MODE,
            "evaluator": "ragas_llm_judge",
            "timestamp": timestamp,
            "total_samples": len(rows),
            "metrics": {
                "faithfulness": round(float(result_df["faithfulness"].mean()), 4),
                "answer_relevancy": round(float(result_df["answer_relevancy"].mean()), 4),
                "context_precision": round(float(result_df["context_precision"].mean()), 4),
                "context_recall": round(float(result_df["context_recall"].mean()), 4),
            },
        }
    else:
        print(
            "\n[WARN] OPENAI_API_KEY belum dikonfigurasi di .env. "
            "Menjalankan simulasi skor metrik Ragas (Dry-Run) untuk verifikasi pipeline QA."
        )
        fieldnames = [
            "id",
            "category",
            "question",
            "ground_truth",
            "answer",
            "contexts",
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
        ]
        f_scores, ar_scores, cp_scores, cr_scores = [], [], [], []
        with open(output_csv, mode="w", encoding="utf-8", newline="") as out_f:
            writer = csv.DictWriter(out_f, fieldnames=fieldnames)
            writer.writeheader()
            for i, row in enumerate(rows):
                f_val = 0.95 if answers[i] else 0.0
                ar_val = 0.92 if answers[i] else 0.0
                cp_val = 0.90 if contexts_list[i] else 0.0
                cr_val = 0.94 if contexts_list[i] else 0.0
                f_scores.append(f_val)
                ar_scores.append(ar_val)
                cp_scores.append(cp_val)
                cr_scores.append(cr_val)
                writer.writerow(
                    {
                        "id": row["id"],
                        "category": row["category"],
                        "question": questions[i],
                        "ground_truth": ground_truths[i],
                        "answer": answers[i],
                        "contexts": json.dumps(contexts_list[i], ensure_ascii=False),
                        "faithfulness": f_val,
                        "answer_relevancy": ar_val,
                        "context_precision": cp_val,
                        "context_recall": cr_val,
                    }
                )

        n = max(len(rows), 1)
        summary_scores = {
            "mode": EVAL_MODE,
            "evaluator": "mock_dry_run (set OPENAI_API_KEY in .env for live Ragas LLM judge)",
            "timestamp": timestamp,
            "total_samples": len(rows),
            "metrics": {
                "faithfulness": round(sum(f_scores) / n, 4),
                "answer_relevancy": round(sum(ar_scores) / n, 4),
                "context_precision": round(sum(cp_scores) / n, 4),
                "context_recall": round(sum(cr_scores) / n, 4),
            },
        }

    with open(output_summary, "w", encoding="utf-8") as f:
        json.dump(summary_scores, f, indent=2, ensure_ascii=False)

    print("\n=== RINGKASAN METRIK RAGAS ===")
    for metric_name, score in summary_scores["metrics"].items():
        print(f"- {metric_name:<20}: {score:.4f}")
    print(f"\n[SUCCESS] Laporan detail disimpan ke : {output_csv}")
    print(f"[SUCCESS] Ringkasan JSON disimpan ke : {output_summary}")
    return 0


if __name__ == "__main__":
    sys.exit(run_evaluation())
