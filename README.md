# FreshTrack

A household food expiry tracker designed to help people remember what they have, use food earlier, and reduce avoidable waste.

FreshTrack is Samson's DevOps, Cloud, and SRE portfolio project, with his own household as the first intended user. It connects a practical food-storage problem with hands-on work in testing, container security, continuous integration, Kubernetes, and operations.

**Current stage:** Milestones 1 and 2 are done: container CI publishes the api image to Docker Hub, and the Kubernetes basics run on Minikube, with the api Ready and connected to PostgreSQL. Milestone 3 (household tracking) has started: the api's grocery routes are written on a feature branch and not merged yet. The web pages and email reminders are planned.

## Contents

- [Project status](#project-status)
- [Version 1 plan](#version-1-plan)
- [Architecture](#architecture)
- [Run locally](#run-locally)
- [Configuration and endpoints](#configuration-and-endpoints)
- [Run checks](#run-checks)
- [CI pipeline](#ci-pipeline)
- [Security and current limits](#security-and-current-limits)
- [Roadmap](#roadmap)
- [Repository layout](#repository-layout)
- [Project documentation](#project-documentation)

## Project status

| Area | Current state |
|---|---|
| API skeleton | Flask app with `/health` and database-aware `/ready` endpoints |
| Tests | Four pytest tests covering health and readiness responses; successful database access is mocked |
| Container | Gunicorn server, digest-pinned Python base image, hash-locked dependencies, non-root UID `10001` |
| CI | Ruff, pytest, Bandit, Trivy source scan, image build, startup smoke test, and image scans |
| Registry publishing | [`samayohub/freshtrack-api`](https://hub.docker.com/r/samayohub/freshtrack-api) on Docker Hub, tagged with the commit SHA, pushed only from `main` |
| Household features | In progress (feature branch, not merged): items table, add / list / mark used-or-discarded api routes with tests. Planned: web pages and the morning reminder |
| Platform add-ons | Calico is installed with the Minikube profile and enforces NetworkPolicies. Planned: Ingress with TLS and basic auth, NetworkPolicies, OpenBao + External Secrets Operator + Reloader (milestone 4); Prometheus, Grafana, Loki with Grafana Alloy, Alertmanager and Argo CD (milestone 6) |
| Deployment | Built on Minikube (PR #12): plain manifests in `deploy/k8s/` for the Namespace, api Deployment, api Service, and PostgreSQL 18 (headless Service + StatefulSet with a persistent volume), plus a database Secret created by hand (values not in Git), applied to a Minikube lab. The api Pod is Ready, `/ready` reaches the database through the Service, and data survived deleting the database Pod (journal Entry 9). Then Helm, and later a short k3s trial on AWS |

On `main`, the api has only its probe endpoints. The grocery routes and database schema are in review on a feature branch; there are no web pages or reminder worker yet. See the [architecture status rules](docs/architecture.md) for what qualifies as Built.

## Version 1 plan

The first release serves one household:

- Add food with a name, quantity, storage location (`fridge`, `freezer`, or `cupboard`), label date, and date type (`best_before` or `expiration`).
- Show active items with the closest label dates first.
- Mark items as used or discarded, retaining their records for the household trial.
- Send one morning email in `America/Toronto`, listing active items within three days of their label date or already past it.
- Use distinct wording for best-before and expiration dates.

FreshTrack organises reminders; it never determines whether food is safe to eat.

Account registration, multiple households, native mobile apps, barcode or receipt scanning, recipes, and automatic grocery ordering are outside version 1.

## Architecture

The following is the **planned application architecture**. Today the api (probe endpoints) and PostgreSQL run on Minikube; the other parts are planned. The [system map](docs/system-map.html) draws this, the delivery pipeline, the Kubernetes objects and the platform tools, each marked Built, In progress, or Planned.

```mermaid
flowchart LR
    household[Household browser] --> edge[TLS + basic authentication]
    edge --> web[Web: Flask + HTML templates]
    web --> api[API: Flask]
    api --> db[(PostgreSQL)]
    checker[Expiry checker: Kubernetes CronJob] --> api
    checker --> mail[Mailpit in development / email provider for trial]
```

Only the API will access PostgreSQL. The web app and expiry checker will call the API so validation and reminder rules stay in one place. Mailpit will capture development email without sending it to real recipients.

The deployment plan uses Minikube as the main lab, Helm for packaging, and Argo CD for deployment from Git. A short AWS trial will use k3s on EC2 in `ca-central-1`, with infrastructure managed in the separate `terraform-aws-platform` repository. Plain Kubernetes manifests were written first in `deploy/k8s/` as a Minikube rehearsal (milestone 2, done), to learn each object before packaging them with Helm. The Minikube profile matches the k3s trial: Kubernetes 1.36, containerd, and Calico so NetworkPolicies are enforced.

### Platform tools and where they run

Each tool gets its own namespace, so the application and the tools that look after it stay separate.

| Namespace | What runs there | Job | Status |
|---|---|---|---|
| `freshtrack` | web, api, PostgreSQL, expiry checker | The application | api and PostgreSQL built; others planned |
| ingress controller's own | Ingress controller (Traefik proposed, confirmed against current docs first) | TLS and basic authentication at the edge | Planned (milestone 4) |
| `openbao` | OpenBao | Stores the secrets | Planned (milestone 4) |
| `external-secrets` | External Secrets Operator | Copies secrets from OpenBao into Kubernetes Secrets | Planned (milestone 4) |
| `reloader` | Reloader | Restarts Pods when a Secret they use changes | Planned (milestone 4) |
| `monitoring` | Prometheus, Alertmanager, Loki, Grafana; Grafana Alloy as a DaemonSet on every node | Metrics (Prometheus), logs (Loki, collected by Alloy), dashboards (Grafana), alerts (Alertmanager) | Planned (milestone 6) |
| `argocd` | Argo CD | Deploys from Git (GitOps) | Planned (milestone 6) |
| every node | Calico CNI | Pod networking; enforces NetworkPolicies | Installed with the Minikube profile |

## Run locally

Run these commands from the repository root. The Docker option requires Docker; the Python option requires Python 3.12 with virtual-environment support.

### Option A: Docker

```bash
docker build -t freshtrack-api:local ./api
docker run --rm --name freshtrack-api -p 127.0.0.1:8000:8000 freshtrack-api:local
```

In another terminal:

```bash
curl -i http://localhost:8000/health
curl -i http://localhost:8000/ready
```

`/health` returns HTTP `200` with `{"status":"ok"}`. Without a configured PostgreSQL connection, `/ready` returns HTTP `503` with `{"status":"not ready"}`. This is expected: the process is running, but its database dependency is unavailable.

Press `Ctrl+C` in the container terminal to stop it. `--rm` removes the stopped container.

### Option B: Python virtual environment

```bash
python3.12 -m venv api/.venv
source api/.venv/bin/activate
python -m pip install --only-binary :all: --require-hashes -r api/requirements-dev.txt
python -m flask --app api/app.py run --host 127.0.0.1 --port 8000
```

This starts Flask's development server. The Docker image uses Gunicorn instead. Use the same curl commands above to check either option.

## Configuration and endpoints

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string read when the app is created | Empty; readiness fails |

The API reads configuration from the process environment. It does not load `.env` files automatically. For Docker, pass an existing environment variable with `-e DATABASE_URL` before the image name. The database hostname must be reachable from inside the container; `localhost` there refers to the container itself.

On Minikube, PostgreSQL runs as a StatefulSet (see `deploy/k8s/`); no application schema or migrations are supplied yet. Readiness currently opens a connection and runs `SELECT 1`; it does not check an application schema.

| Method | Path | Result |
|---|---|---|
| `GET` | `/health` | `200`, `{"status":"ok"}`; no database check |
| `GET` | `/ready` | `200`, `{"status":"ready"}` when PostgreSQL responds; otherwise `503`, `{"status":"not ready"}` |

Separating these checks lets a future Kubernetes deployment stop routing traffic during a database outage without restarting a healthy API process.

## Run checks

After installing the development dependencies and activating the virtual environment:

```bash
ruff check api/
ruff format --check api/
python -m pytest -v api/tests
bandit -r api/ -x api/tests
```

The tests need no running PostgreSQL instance. They mock the successful readiness result and exercise missing configuration and an unreachable database. Real PostgreSQL integration tests are planned alongside the first SQL implementation.

Runtime dependencies are declared in `api/requirements.in`; development tools are declared in `api/requirements-dev.in`. The corresponding `.txt` files contain pinned versions and hashes and are used for installation by CI and the Docker build.

## CI pipeline

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every branch push and every pull request. The `checks` job runs the first four stages in order; the `ship` job runs only after a push to `main`, once `checks` has passed:

| Stage | Checks |
|---|---|
| Check | Ruff lint and formatting, pytest, Bandit, Trivy filesystem scan for vulnerabilities and secrets |
| Build | Build the API image tagged with the Git commit SHA |
| Prove | Start the image and require `/health` to respond successfully |
| Scan | Save the image to a tar file; run a full Trivy report, then a gate for fixable HIGH/CRITICAL vulnerabilities with secret scanning enabled |
| Ship | `main` only: receive the scanned image tar from `checks` as a one-day artifact, load it, tag it `samayohub/freshtrack-api:<commit SHA>`, log in with a token from the `main`-only `dockerhub` environment, push, log out |

A failed step blocks subsequent normal steps. Container logs are requested even after failure. The full image report shows findings at all severities; the vulnerability gate uses `--severity HIGH,CRITICAL --ignore-unfixed --exit-code 1`.

SonarCloud is documented as running separately through its GitHub app's Automatic Analysis. It is not a step in this workflow. Deployment is not automated yet: manifests are applied by hand with `kubectl` after a server-side dry run. Argo CD is planned.

The `main` branch is protected by a repository ruleset: changes need a pull request, the `checks` job and SonarCloud must pass, the branch must be up to date, and force pushes and deletion are blocked, with no bypass. The image that ships is the exact file that was scanned; it is not rebuilt.

The [engineering journal](docs/journal.md) records a failure drill where an old base image passed the build and health check but failed the image vulnerability gate. Those historical scan results are evidence from that run, not a claim about today's vulnerability status.

## Security and current limits

- The API image uses a digest-pinned base, installs hash-verified wheels, and runs as non-root UID `10001` with Gunicorn's control socket disabled.
- GitHub Actions are pinned to commit SHAs. The workflow token has read-only repository access, and checkout does not persist credentials.
- Trivy scans the saved image through a read-only file mount without receiving the Docker socket.
- The Docker Hub token (Read & Write, with an expiry date) is stored only in the GitHub environment `dockerhub`, which only the `main` branch can use. Feature branches and pull requests never receive it. Images are tagged only with the commit SHA, never `latest`.
- Secrets belong in environment variables or a secret store; never commit credentials or bake them into an image.
- In Kubernetes, the api is exposed only through a `ClusterIP` Service and PostgreSQL only through a headless Service, so neither can be reached from outside the cluster. Both run as non-root users with all Linux capabilities dropped, and the official PostgreSQL image is pinned by digest.
- The database credentials are a Kubernetes Secret created by hand from a file outside the repository; no Secret values are stored in Git. OpenBao with External Secrets Operator is planned to replace this manual step.
- The API currently has no authentication. Before any public exposure, the deployment must provide TLS and basic authentication at the Ingress or Gateway.
- The filesystem dependency scan currently covers runtime requirements; development dependency scanning, Git history secret scanning, and misconfiguration scanning are not implemented.
- Image scans run on code changes. Unfixed vulnerabilities may pass the image gate and remain visible in the full report; scheduled rescanning is planned.

## Roadmap

These are planned milestones, not completed features or promised dates. Milestones 1 (ship the API image) and 2 (Kubernetes basics on Minikube) are done. The order was changed on 2026-10-31: the Kubernetes basics are rehearsed on Minikube before the household features, and sequencing can still be refined.

| Milestone | Planned work | Completion evidence |
|---|---|---|
| 1. Ship the API image (**done**) | Publish to Docker Hub after successful checks, only on `main`, tagged with the commit SHA | Pull the published image and verify `/health` (verified 2026-10-24, see journal Entry 6) |
| 2. Kubernetes basics on Minikube (**done**) | Plain manifests: Namespace, api Deployment with probes and resource settings, ClusterIP Service, database Secret, PostgreSQL StatefulSet with persistent storage. Each container also has ephemeral-storage requests and limits. Merged in PR #12 |  api Pod Ready, `/health` reachable through the Service from inside the cluster, data kept after the database Pod is deleted (verified 2026-11-03, see journal Entry 9) |
| 3. Implement household tracking (**in progress**) | PostgreSQL schema, item validation, add/list/status API routes, Flask HTML interface, integration tests | Add groceries, see date ordering, mark used/discarded, and verify retained records |
| 4. Package and protect | Helm chart with Minikube and AWS values, Ingress with TLS and basic authentication, NetworkPolicies, OpenBao + External Secrets Operator + Reloader | Demo the application behind TLS and a login prompt, and verify recovery through failure drills |
| 5. Add reminders | Expiry checker as a CronJob, date-type wording, three-day window, Mailpit tests, morning schedule | Inspect captured emails for due, past-date, and no-due-item cases |
| 6. Add delivery and operations | Argo CD, Prometheus metrics, Loki logs collected by Grafana Alloy, Grafana dashboards, Alertmanager alerts, scheduled image rescanning, resource sizing | Demonstrate a Git-driven rollout and a failed-reminder alert |
| 7. Run the household trial | Short k3s/AWS hosting window within a two-week household trial | Record reminder accuracy, ease of use, and real examples of food remembered; remove AWS resources after the trial |

Failure drills (including the CHECK-stage drills for Ruff, pytest, Bandit, and Trivy secret scanning) are grouped into a game-day stage once FreshTrack is fully deployed with monitoring and the api runs 3 replicas. Open decisions include the edge networking implementation, trial email provider, exact morning send time, and whether days with nothing due should produce an email. See [architecture decisions](docs/architecture.md#12-open-decisions).

## Repository layout

```text
freshtrack/
├── .github/workflows/ci.yml  # Code checks, image build, smoke test, scans, ship to Docker Hub
├── api/
│   ├── app.py                # Flask application factory and probe endpoints
│   ├── Dockerfile            # API image served by Gunicorn
│   ├── .dockerignore         # Excludes local files from the build context
│   ├── requirements.in       # Runtime dependency declarations
│   ├── requirements.txt      # Runtime dependency lock file
│   ├── requirements-dev.in   # Development dependency declarations
│   ├── requirements-dev.txt  # Development dependency lock file
│   └── tests/                # Test fixtures and health/readiness tests
├── deploy/k8s/               # Plain Kubernetes manifests for the Minikube rehearsal
│   ├── namespace.yaml        # freshtrack Namespace
│   ├── api-deployment.yaml   # api Deployment: digest-pinned image, probes, resources, security context
│   ├── api-service.yaml      # api ClusterIP Service (internal only)
│   ├── postgres-service.yaml # PostgreSQL headless Service (stable DNS name)
│   └── postgres-statefulset.yaml # PostgreSQL 18 StatefulSet with a 1Gi PVC
├── docs/
│   ├── architecture.md       # Design, status, deployment plans, decisions
│   ├── journal.md            # Implementation evidence and lessons
│   └── system-map.html       # Illustrated overview for demos and interviews
└── CLAUDE.md                 # Project scope and collaboration guidance
```

## Project documentation

- [Architecture](docs/architecture.md): component boundaries, proposed data model, Kubernetes design, tool choices, and open decisions.
- [Engineering journal](docs/journal.md): problems, decisions, implementation, verification, troubleshooting, lessons, and next steps.
- [System map](docs/system-map.html): illustrated overview of how FreshTrack works and how code reaches the cluster, with each part marked Built, In progress, or Planned. Download and open it in a browser; GitHub shows HTML as source.

Keep status claims tied to merged, verified work. Develop changes on small feature branches and require CI to pass before merging.
