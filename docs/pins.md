# Pins

Every version this project depends on. Changing a row is a recorded decision (the maintainers' decision log, not shipped) and invalidates every report taken under the old value.

| what | pin | status |
|---|---|---|
| Vespa | `vespaengine/vespa:8.751.13` (image id `83fec6133c2c`, 1.54 GB) | pulled 2026-09-14 |
| Vespa CLI | 8.562.17 (go1.24.5 darwin/arm64) | recorded |
| Container VM resources (Rancher Desktop for every measurement; any Docker Engine API runtime — Docker Engine, Docker Desktop, Rancher Desktop or Podman — for a reader) | 4 CPU / 10 GB | decided D8; runtime per D126 |
| Host | Apple M4 Pro, 14 cores, 24 GiB (hostinfo.py reports it as 25.8 GB, decimal), macOS 15.7 | recorded |
| Python | 3.11.13 (pyenv) | recorded |
| Dataset | `tasksource/esci` @ `8113b17a5d4099e20243282c926f1bc1a08a4d13` (mirror of `amazon-science/esci-data`), locale `us` | carried from old project |
| Corpus preset | `book`: 3,500 hard US queries, 33,000 distractors, validation fraction 0.3, seed 42, gains `kdd` (D21) → build `esci-us-hard-book-s42-kdd-v4`: train 1,715 / validation 735 / test 1,050 queries; 101,341 products (68,341 judged + 33,000 distractors); content hash in its `build.json` | built 2026-09-14 |
| Embedder | `BAAI/bge-small-en-v1.5` @ `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, pooling `cls`, normalize `true`, declared by `url` | carried |
| Comparison embedder (ch04 only, measured once, not in any shipped app — D32 / D51 / D52) | `BAAI/bge-base-en-v1.5` @ `a5beb1e3e68b9ab74eb54cfd186867f64f240e1a`, pooling `cls`, normalize `true`, 768 dims, declared by `url` in `chapters/ch04/models/bge-base.xml` | added 2026-09-15 |
| Late interaction | `colbert-ir/colbertv2.0` @ `c1e84128e85ef755c096a95bdb06b47793b13acf` | carried from ch04 `models/colbert.md` |
| Cross-encoder | `cross-encoder/ms-marco-MiniLM-L6-v2` @ `233902d25c440f23af6f7d6e94d2946bac0bee0a` | carried |
| LLM for the ch11 trajectory record (D116 / D118 補充 2) | OpenAI `gpt-6-luna` via Vespa `ai.vespa.llm.clients.OpenAI` (`model` in the llm-client config; no `temperature` is set — the model accepts only its default); no dated id exists, and `LLMSearcher` returns only the token stream — the record file stores the configured model name, the run date and the Vespa build; key in repo-root `.env` (`OPENAI_API_KEY`, git-ignored), sent per request as `X-LLM-API-KEY`, never in the app package | chosen 2026-09-29 |
| Python packages | `shared/requirements/lock/{base,embed,ml,tests}.txt`, each frozen from a fresh 3.11.13 venv on 2026-09-14; headline: requests 2.34.2, pyarrow 25.0.1, onnxruntime 1.30.0, tokenizers 0.23.2, lightgbm 4.7.0, onnxmltools 1.16.0, onnx 1.22.0, numpy 2.4.6, pytest 9.1.1 | frozen |
| Corpus content hash | per build, in `builds/<id>/build.json` | — |
