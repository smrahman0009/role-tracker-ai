# Docker setup

A walkthrough of how Role Tracker AI is packaged as a Docker image — what
each piece does, why the choices were made, and the commands you actually
need to run day-to-day.

This doc is intentionally beginner-friendly. If you've never used Docker
before, you should be able to read it top-to-bottom and understand what's
happening.

---

## What is Docker, in one paragraph

Docker packages your app + its dependencies + a slice of an operating
system into a single, portable file called an **image**. Anywhere you can
run Docker — your laptop, a CI server, a cloud platform — you can run
that image and get the exact same behaviour. No "works on my machine"
problems. When you start an image, the running instance is called a
**container**. Containers are lightweight (think hundreds of megabytes,
not gigabytes) because they share the host kernel — they're isolated
processes, not full virtual machines.

Three terms you'll see repeatedly:

| Term | What it means |
|------|---------------|
| **Image** | The packaged, immutable artefact. Built once, run anywhere. |
| **Container** | A running instance of an image. Stateless — when it dies, anything inside dies with it. |
| **Volume** | A folder on the host machine mounted into a container, used for data that needs to survive container restarts. |

---

## How Role Tracker is packaged

We use a **single-container** design: one image runs both the FastAPI
backend and serves the React frontend. See the project README for why
this is the right call at our scale.

The build is **multi-stage** — a common Docker pattern where you use one
disposable image to compile/build things, and a second clean image to
actually run the result. This keeps the final image small (no Node.js,
no build tools, no source-code-only files like tests).

### Stage 1 — `frontend-builder` (Node 20)

```
node:20-slim → npm ci → npm run build → frontend/dist/
```

Builds the React app into static HTML/JS/CSS. This stage gets thrown
away after the build; only `frontend/dist/` is kept.

### Stage 2 — `python-deps` (Python 3.12)

```
python:3.12-slim + uv → /opt/venv/ with all backend deps
```

Resolves Python dependencies from `pyproject.toml` + `uv.lock` into a
virtual environment at `/opt/venv`. The project itself (`src/`) is
installed into that venv with `--no-deps` so layer caching is maximised
(changing source code doesn't reinstall every dep).

### Stage 3 — `runtime` (Python 3.12)

```
python:3.12-slim
  + /opt/venv from stage 2
  + frontend/dist from stage 1
  + src/ + users/ + config.yaml
  + non-root user "app"
  → uvicorn role_tracker.api.production:app
```

This is the image that ships. ~383 MB total.

The `production:app` ASGI module wraps the existing API:

- `/api/*` → the FastAPI app (routes, auth, all unchanged from dev)
- `/assets/*` → hashed Vite bundle (JS / CSS) served as static files
- `/<anything else>` → falls back to `index.html` so React Router's
  client-side routes work after a hard refresh

### Why these choices

| Choice | Reason |
|--------|--------|
| `python:3.12-slim` not `alpine` | Slim handles native deps (`lxml`, `trafilatura`) without the musl libc compatibility headaches Alpine sometimes brings. |
| `node:20-slim` only in build stage | Production image doesn't need Node.js — the SPA is just static files. Throwing the Node stage away saves ~200 MB. |
| `uv` not `pip` | Faster, lockfile-aware, and matches what we use locally. |
| Non-root user (`app`, uid 1000) | Web servers should never run as root. Limits the blast radius if the app is exploited. |
| `data/` excluded via `.dockerignore` | Resumes, applied records, letters, usage rollups are *runtime* data — they belong on a mounted volume, not baked into the image. |
| Bearer auth lives on the API only | The SPA itself doesn't need protection (it's just JS files). Auth is enforced when JS calls `/api/*`. |

---

## Day-to-day commands

All commands assume you're running them from the project root.

### Build the image

```bash
docker build -t role-tracker:local .
```

`-t role-tracker:local` tags the image so you can refer to it by name.
First build pulls base images (~3–5 min). Subsequent builds reuse
cached layers and finish in seconds when only source code changes.

### Run the container

```bash
docker run -d \
  --name role-tracker-test \
  -p 8000:8000 \
  --env-file .env \
  -v "$PWD/data:/app/data" \
  role-tracker:local
```

Flag-by-flag:

| Flag | What it does |
|------|--------------|
| `-d` | Detached — runs in background, doesn't tie up your terminal. |
| `--name role-tracker-test` | Give the container a memorable name so we can stop / inspect it later. |
| `-p 8000:8000` | Map host port 8000 → container port 8000. Visit `http://localhost:8000` in a browser. |
| `--env-file .env` | Load secrets (Anthropic / OpenAI / JSearch keys) from your local `.env`. |
| `-v "$PWD/data:/app/data"` | Bind-mount the host `data/` folder into the container. Lets the container read/write your real data without baking it into the image. |

Once it's running, open `http://localhost:8000` in a browser — the SPA
will load and call `/api/*` for data.

### Watch the logs

```bash
docker logs -f role-tracker-test
```

`-f` "follows" the log like `tail -f`. Hit Ctrl-C to detach (the
container keeps running — `-f` only stops the *log stream*, not the
container itself).

### Stop & remove the container

```bash
docker stop role-tracker-test
docker rm role-tracker-test
```

Or do both at once:

```bash
docker rm -f role-tracker-test
```

### Open a shell inside the running container

Useful when something's misbehaving and you want to poke at the
filesystem:

```bash
docker exec -it role-tracker-test bash
```

Type `exit` to leave; the container keeps running.

### List images / containers

```bash
docker images               # what's built
docker ps                   # what's running
docker ps -a                # what's running OR exited
```

### Clean up disk space

Docker images can quietly eat tens of GB if you build often. Periodic
cleanup:

```bash
docker system prune          # removes stopped containers + dangling images
docker system prune -a       # also removes unused images (more aggressive)
```

---

## Files involved

| File | Role |
|------|------|
| [`Dockerfile`](../Dockerfile) | Build instructions — three stages described above. |
| [`.dockerignore`](../.dockerignore) | What NOT to copy into the build context. Mirrors `.gitignore` plus extras like `data/`, `tests/`, and `.env`. |
| [`src/role_tracker/api/production.py`](../src/role_tracker/api/production.py) | The ASGI app the container runs. Mounts the API at `/api` and serves the SPA at `/`. |
| [`frontend/dist/`](../frontend/dist/) | The built SPA. Generated by `npm run build` (or by Stage 1 inside Docker). Gitignored. |

---

## Common pitfalls

**"executable file not found in $PATH" when starting the container.**
Means the venv didn't get the deps installed. We hit this once when
`uv sync --no-install-project` produced an empty venv — fixed by
exporting deps to `requirements.txt` first.

**Browser shows the SPA but API calls 404.**
Probably hit `127.0.0.1:8000` while a different process (your dev
backend?) is bound there. Use `localhost:8000` or stop the other
process first.

**Container starts then immediately exits.**
Run without `-d` to see the error inline:
```bash
docker run --rm --env-file .env -p 8000:8000 role-tracker:local
```

**Changes to my code aren't showing up in the container.**
Containers run the image you built, not your live source files. Rebuild
with `docker build -t role-tracker:local .` after every change. (For dev,
it's almost always faster to use `uv run uvicorn ...` directly and skip
Docker — only use Docker when verifying the production setup.)

---

## Mental model: dev vs Docker

| | Dev | Docker |
|---|-----|--------|
| **Backend** | `uv run uvicorn role_tracker.api.main:app --reload` | Inside container, runs `production:app` which wraps `main:app` |
| **Frontend** | `npm run dev` on port 5173, proxies `/api/*` to backend on 8000 | Pre-built `frontend/dist/`, served by the same FastAPI process |
| **Data** | `./data/` directly | Same `./data/` mounted as volume into `/app/data` |
| **Hot reload** | Yes | No — rebuild the image |
| **Used for** | Daily development | Verifying the prod setup before deploying |

Both paths share the same source code. Docker just adds the production
wrapper and bakes everything into one shippable artefact.
