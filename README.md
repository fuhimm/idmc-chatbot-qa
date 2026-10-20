# IDMC Chatbot QA & RAG Evaluation (`idmc-chatbot-qa`)

Repositori mandiri untuk **Quality Assurance (QA)** dan **Evaluasi RAG (Ragas)** pada proyek **Chatbot RAG IDMC Jogjaprov** (`idmc.jogjaprov.go.id` — berbasis Chrome Extension & Web Widget).

Repositori ini dirancang secara **modular** agar pengujian dapat dijalankan secara bertahap baik sebelum maupun sesudah pipeline Backend & AI/RAG selesai diintegrasikan:
- **Repo Scraping (Knowledge Base):** [hmnnanxiety/chatbotscraping-pmld](https://github.com/hmnnanxiety/chatbotscraping-pmld/tree/standalone/scraping-pipeline)
- **Repo Frontend (UI Extension/Web):** [hmnnanxiety/idmc-chatbot](https://github.com/hmnnanxiety/idmc-chatbot)

---

## 1. Struktur Direktori

```text
idmc-chatbot-qa/
├── datasets/
│   ├── 01_functional_test_cases.csv      # 15 Functional Test Cases (FT-01 s.d. FT-15)
│   ├── 02_evaluation_dataset_ragas.csv   # 12 In-Scope (EV-01..12) + 5 Parafrase (PR-01..05)
│   └── 03_oos_adv_grey_dataset.csv       # 7 OOS + 5 Adversarial + 10 Grey Area (Pass/Fail)
├── scripts/
│   └── evaluate_ragas.py                 # Skrip evaluasi Ragas (Switch Mode: MOCK vs LIVE)
├── reports/
│   └── .gitkeep                          # Direktori output hasil evaluasi CSV & JSON
├── .env.example                          # Template konfigurasi environment
├── .gitignore                            # Daftar file yang diabaikan Git
├── requirements.txt                      # Dependensi Python untuk evaluasi QA
└── README.md                             # Dokumentasi & Kontrak API Backend/AI
```

---

## 2. Ringkasan Dataset Pengujian

1. **`datasets/01_functional_test_cases.csv` (`FT-01` s.d. `FT-15`)**
   - Menguji fitur dan alur fungsional sistem pada Chrome Extension/Widget.
   - Dilengkapi kolom `execution_phase`:
     - `Frontend_Only`: Dapat diuji langsung pada repo Frontend (`idmc-chatbot`) tanpa menunggu Backend siap (validasi input kosong/spasi, batas karakter, state `isAssistantLoading`, navigasi `Home/Conversation/History`, sanitasi tag HTML).
     - `Requires_Backend_AI`: Membutuhkan integrasi endpoint Backend & RAG.

2. **`datasets/02_evaluation_dataset_ragas.csv` (`EV-01` s.d. `EV-12` & `PR-01` s.d. `PR-05`)**
   - Berisi **12 pertanyaan In-Scope** dan **5 pertanyaan In-Scope Parafrase** berdasarkan cakupan aktual portal IDMC DIY (Beranda Dashboard Pembangunan serta 9 menu aktif: *Dashboard Ajimandaya, IKM dan Perkebunan, JSP, Kepegawaian/Simpeg, Koperasi & UKM, Pangan, Surveillance CCTV, Manajemen SPBE, dan Social Media Analytic*).
   - Dievaluasi menggunakan 4 metrik Ragas: **Faithfulness**, **Answer Relevancy**, **Context Precision**, dan **Context Recall**.

3. **`datasets/03_oos_adv_grey_dataset.csv` (`OOS-01..07`, `ADV-01..05`, `GA-01..10`)**
   - Menguji kepatuhan batasan lingkup (*guardrails*) chatbot terhadap **7 pertanyaan Out-of-Scope**, **5 serangan Adversarial/Prompt Injection**, dan **10 kasus Grey Area** lengkap dengan kriteria *Pass* dan *Fail*.

---

## 3. Cara Menjalankan Evaluasi Ragas

### A. Persiapan Environment

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### B. Menjalankan Mode `MOCK` (Sebelum Backend Siap)

Secara default, `.env` mengatur `EVAL_MODE=MOCK`. Pada mode ini, `scripts/evaluate_ragas.py` menggunakan kolom `contexts_placeholder` dan `answer_placeholder` dari CSV untuk memverifikasi alur evaluasi:

```bash
python scripts/evaluate_ragas.py
```

### C. Menjalankan Mode `LIVE` (Setelah Backend & AI Siap)

Ubah konfigurasi di dalam file `.env`:

```dotenv
EVAL_MODE=LIVE
BACKEND_API_URL=http://localhost:8000/api/v1/chat
OPENAI_API_KEY=sk-proj-xxxx
```

Lalu jalankan kembali perintah:

```bash
python scripts/evaluate_ragas.py
```

Hasil evaluasi akan otomatis tersimpan di folder `reports/` dalam format `.csv` (detail per baris pertanyaan) dan `.json` (rata-rata 4 metrik Ragas).

---

## 4. Spesifikasi Kontrak JSON untuk Tim Backend & AI Engineer

Agar skrip otomatisasi QA (`scripts/evaluate_ragas.py`) pada mode `LIVE` dapat menghitung metrik **Faithfulness**, **Answer Relevancy**, **Context Precision**, dan **Context Recall** secara otomatis, endpoint API Chat pada Backend **wajib** mengembalikan teks jawaban beserta *raw chunks* konteks yang diambil dari Vector Database.

### Endpoint Request (dari Skrip QA ke Backend)

- **Method:** `POST`
- **URL:** Sesuai `BACKEND_API_URL` (contoh: `http://localhost:8000/api/v1/chat`)
- **Headers:** `Content-Type: application/json`
- **Request Body:**

```json
{
  "question": "Apa saja layanan atau menu dashboard yang tersedia di IDMC?"
}
```

### Endpoint Response (Wajib Dikembalikan oleh Backend)

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "answer": "Layanan menu dashboard yang tersedia di IDMC DIY meliputi Dashboard Pembangunan (Beranda), Dashboard Ajimandaya, Dashboard IKM dan Perkebunan, Dashboard JSP, Dashboard Kepegawaian, Dashboard Koperasi & UKM, Dashboard Pangan, Dashboard Surveillance, Manajemen SPBE, serta Social Media Analytic.",
  "contexts": [
    "Sembilan menu aktif pada portal IDMC DIY meliputi: Dashboard Ajimandaya, Dashboard IKM dan Perkebunan, Dashboard JSP, Dashboard Kepegawaian, Dashboard Koperasi & UKM, Dashboard Pangan, Dashboard Surveillance, Manajemen SPBE, dan Social Media Analytic.",
    "Selain sembilan grup menu tersebut, terdapat halaman Beranda yang menampilkan Dashboard Pembangunan."
  ],
  "is_refusal": false,
  "sources": [
    {
      "menu": "Portal Scope IDMC DIY",
      "source_id": "portal_menus_v1"
    }
  ]
}
```

### Ketentuan Field Response:
| Field | Tipe Data | Status | Keterangan |
| :--- | :--- | :--- | :--- |
| `answer` | `string` | **Wajib** | Jawaban akhir yang disusun oleh LLM (atau pesan penolakan sopan jika *out-of-scope*). |
| `contexts` | `array of strings` | **Wajib** | Daftar potongan teks (*chunks*) asli dari vector database yang dijadikan rujukan oleh LLM saat menjawab. Jika tidak ada konteks relevan yang ditemukan, kembalikan array kosong `[]`. |
| `is_refusal` | `boolean` | *Opsional* | Bernilai `true` apabila chatbot menolak menjawab karena pertanyaan berada di luar lingkup IDMC. Memudahkan pengujian otomatis dataset OOS & Adversarial. |
| `sources` | `array of objects` | *Opsional* | Metadata sumber chunk (misal nama dashboard/menu atau `chunk_id` dari hasil `ready_for_vector_db_v2.json`). |
