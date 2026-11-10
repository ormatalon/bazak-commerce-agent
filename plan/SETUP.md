# Detailed setup and troubleshooting


These commands are for the `v2` branch and run from the repository root. Use Python 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/) to create a local virtual environment. Create a new `.venv` on each machine; a Windows virtual environment cannot be copied to a Mac. V1 on `v1` has separate setup instructions and does not require the embedding model.

### Windows (PowerShell)

Use the virtualenv interpreter: the system `python` command may open the Microsoft Store stub.

```powershell
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt --index https://download.pytorch.org/whl/cpu --index https://pypi.org/simple --index-strategy unsafe-best-match
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

If `CHAINLIT_AUTH_SECRET` is not already configured, generate it locally and copy the printed value into `.env`:

```powershell
.venv/Scripts/python.exe -m chainlit create-secret
```

Complete the shared configuration below, then download the model and start the app:

```powershell
.venv/Scripts/python.exe -m app.embeddings --download
.venv/Scripts/python.exe -m chainlit run app/main.py
```

### macOS (Apple Silicon, macOS 14 or newer)

Use a native Apple Silicon Terminal: `uname -m` should print `arm64`, and `sw_vers -productVersion` should show 14 or newer. If an Apple Silicon Mac reports `x86_64`, open Terminal without Rosetta and create its environment there.

Install uv once using its [official installer](https://docs.astral.sh/uv/getting-started/installation/), then reopen Terminal so `uv` is on `PATH`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

From the repository root on `v2`:

```bash
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt --index-url https://pypi.org/simple --only-binary torch,numpy
if [ ! -e .env ]; then cp .env.example .env; fi
```

Use PyPI for macOS; the Windows CPU-wheel index is not needed. PyTorch and NumPy use prebuilt wheels, while pure-Python dependencies may be built from their published source distributions. Do not add `--only-binary :all:`: Chainlit's pinned `literalai` dependency has no usable wheel.

If `CHAINLIT_AUTH_SECRET` is not already configured, generate it locally and copy the printed value into `.env`:

```bash
.venv/bin/python -m chainlit create-secret
```

Complete the shared configuration below, then download the model and start the app:

```bash
.venv/bin/python -m app.embeddings --download
.venv/bin/python -m chainlit run app/main.py
```

On later runs, only the last command is needed. No environment activation is required because these commands use its interpreter directly. Stop the server with **Ctrl+C**.

**Intel Macs and older macOS:** the pinned V2 `torch==2.15.0` release has a `macosx_14_0_arm64` wheel, but no native Intel Mac wheel. The setup above therefore targets Apple Silicon on macOS 14+. PyTorch [ended official macOS x86 builds after the 2.2 release series](https://dev-discuss.pytorch.org/t/pytorch-macos-x86-builds-deprecation-starting-january-2024/1690). Native Intel V2 support would require a different dependency plan; installing an older torch alone is not a verified solution for this pinned stack.

### Shared configuration and first run

Edit the ignored `.env` file locally:

- Set `OPENAI_API_KEY` for model calls.
- Choose `APP_USERNAME` and `APP_PASSWORD` for the local login.
- Set `CHAINLIT_AUTH_SECRET` to the generated value. Keep an existing secret if you already use this installation.
- LangSmith is optional: configure `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true` and the destination in [the monitoring runbook](MONITORING.md) when tracing is wanted.

Then open **http://localhost:8000** and sign in with that username and password. Secrets stay in `.env` and are never committed.

The model identifier is `intfloat/multilingual-e5-small`, pinned to revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`. It runs locally on CPU on both Windows and macOS; this setup does not enable Apple's GPU/MPS backend. The download is required once per machine. The catalog is fetched only if no valid local cache exists. Model calls, uncached currency lookups and enabled LangSmith exports need internet access; product images use catalog URLs.

**Verification:** the Python 3.12 dependency set was resolved for Apple Silicon macOS 14 with prebuilt torch/NumPy, and the Intel wheel incompatibility was reproduced. Resolution is not a native installation or UI test: this project has not been run on a physical Mac in this session.

### macOS troubleshooting

- `uv: command not found`: reopen Terminal after installation, or follow the installer's shell-path instructions.
- No matching torch distribution: check `uname -m`, macOS version and that this environment uses Python 3.12. Do not reuse a Windows or Rosetta-created environment.
- Missing embedding model: run `.venv/bin/python -m app.embeddings --download` from the repo root while online.
- Login configuration error: fill in the three local-login/authentication values above before starting Chainlit.
- Port 8000 already in use: stop the other instance, or run `.venv/bin/python -m chainlit run app/main.py --port 8001` and open http://localhost:8001.

