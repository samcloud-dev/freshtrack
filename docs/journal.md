# FreshTrack — Engineering Journal

Each entry: Problem → Decision → Implementation → Verification → Troubleshooting → Lesson → Next step.

---

## Entry 1 — 2026-10-09 — Project kick-off

**Problem**
Households throw food away because they forget what is in the fridge, freezer or
cupboard, buy the same item twice, or find food after its label date has passed.
I need a portfolio project that solves a real problem for a real user (my household)
and lets me practise DevOps, Kubernetes and SRE end to end.

**Decision**
- Build FreshTrack v1 with a small scope: add items, a sorted active list,
  mark used/discarded, and one morning email listing items due within 3 days or past.
- Four parts: web (Flask templates), api (Flask), expiry-checker (CronJob), PostgreSQL.
  Mailpit for dev and test email.
- No user accounts in v1. TLS + basic auth at the edge before any public exposure.
- Minikube is the main lab. AWS k3s only for the ~1 week trial, then destroy.

**Implementation**
- Created the project folder with `CLAUDE.md` (working rules and scope).
- Initialised a Git repository on branch `main`.
- Created `docs/architecture.md` (every component marked Planned) and this journal.

**Verification**
- `git status` shows branch `main`, no commits yet, files untracked.

**Troubleshooting**
- Tool check: Git 2.43, Python 3.12.3 and gh 2.45 are present. `docker --version`
  returned nothing, and minikube, kubectl and helm are not installed. To fix in a later step.

**Lesson**
- Write the plan down before building: an honest architecture doc (Planned vs Built) and a journal
  make every decision traceable, like batch records in food production.
- `.gitignore` is a safety net, not a lock. If a secret is ever committed, rotate it first, then clean history.

**Next step**
- Review `docs/architecture.md` and settle the open decisions.
- Add `.gitignore`, make the first commit, and create the GitHub repo.

---

## Entry 2 — 2026-10-10 — api skeleton with /health and /ready

**Problem**
The DevOps work (Dockerfile, CI, Kubernetes probes) needs a real application to package.
Every app must expose `/health` (liveness) and `/ready` (readiness, checks the database).

**Decision**
- Start the api with only `/health` and `/ready`, with no food items yet.
- `/health` never checks the database; `/ready` does (2-second connection timeout, `SELECT 1`).
- On failure, `/ready` logs the reason but returns only `{"status": "not ready"}` (no internal details).
- Database address comes only from the `DATABASE_URL` environment variable.
- Versions checked on PyPI (2026-10-10): Flask 3.1.3, psycopg 3.3.6, gunicorn 26.2.0, pytest 9.1.1.

**Implementation**
- Branch `feat/api-skeleton`.
- `api/app.py`, `api/tests/test_health.py` (4 tests), `api/tests/conftest.py`,
  `api/requirements.in` (runtime), `api/requirements-dev.in` (adds pytest).
- Local virtual environment `api/.venv` (git-ignored).

**Verification**
- `.venv/bin/pytest -v`: 4 passed in 0.26s.
- `git status` confirmed `.venv/`, `__pycache__/` and `.pytest_cache/` are ignored.

**Troubleshooting — failure drill (Predict → Break → Observe → Fix → Verify)**
- Predict: if `/health` checks the database, Kubernetes restarts the Pods during a database outage.
  I first predicted that test 3 would fail; the correct answer was test 1, because it is the only test that calls `/health`.
- Break: changed `/health` to call `database_is_reachable(...)`.
- Observe: `test_health_is_always_ok` FAILED, the other 3 passed.
- Fix: restored the original `/health` and its explanatory comments.
- Verify: 4 passed.
- Side note: `gh` CLI login is invalid (HTTP 401). Pushing works over SSH. Re-login is needed before using `gh pr create`.

**Lesson**
- Liveness (`/health`) answers "should Kubernetes restart me?"; readiness (`/ready`) answers
  "can I serve traffic now?". Putting a database check in liveness causes restart loops
  (CrashLoopBackOff) during a database outage, and restarts cannot fix the database.
- To predict which test breaks, ask: which tests call the code I changed?

**Next step**
- Open the pull request for `feat/api-skeleton` (do not merge until CI exists).
- Samson builds the CI pipeline: Check → Build → Prove → Scan → Ship, starting with lint + test.

---

## Entry 3 — 2026-10-10 — CI check stage (lint ∥ test)

**Problem**
There was no CI. PR #1 (api skeleton) was merged after local tests only, so nothing
automatically stopped broken or messy code from reaching `main`.

**Decision**
- Start the pipeline with stage 1 of Check → Build → Prove → Scan → Ship: `lint` and `test` as two parallel jobs.
- Triggers: `pull_request` and `push` to `main` only. Pushing a feature branch alone does not run CI;
  open a (draft) PR for early feedback. This avoids running CI twice for the same commit.
- Least privilege: `permissions: contents: read`, `persist-credentials: false`.
- Fixed runner `ubuntu-24.04`, `timeout-minutes: 5`, `concurrency` with `cancel-in-progress`.
- Actions pinned to full commit SHAs, verified on 2026-10-10 with the GitHub releases API and `git ls-remote`:
  `actions/checkout` v7.0.1 = `3d3c42e5aac5ba805825da76410c181273ba90b1`,
  `actions/setup-python` v7.0.0 = `5fda3b95a4ea91299a34e894583c3862153e4b97`.
- Ruff 0.17.0 (latest on PyPI on 2026-10-10), same version locally and in CI.

**Implementation**
- Branch `ci/check-stage`, file `.github/workflows/ci.yml` (typed by me, with a comment per stage).
- Ruff installed in `api/.venv` to reproduce CI locally.

**Verification**
- First CI run: `test` passed; `lint` failed at `ruff check` (see Troubleshooting).
- Locally after the fix: `ruff check api/` → All checks passed; `ruff format --check api/` → 3 files
  already formatted; `pytest` → 4 passed.
- PR #2 was merged on 2026-10-10, but the workflow file was invalid, so lint and test never ran
  (see Troubleshooting 6).
- After the fix in PR #3, CI was green on the PR (run `38034944465`) and on `main` after the merge
  (run `38035053448`, commit `6f6db79`).

**Troubleshooting**

1. *`git add` did nothing; `git status` showed `../.github/`.*
   - Why: I ran Git from inside `api/`. Git paths are relative to the current folder, so
     `.github/workflows/ci.yml` pointed to a file that does not exist there.
   - Fix: `cd ~/Projects/freshtrack` (or `cd "$(git rev-parse --show-toplevel)"`), then `git add`.

2. *CI lint failed: `I001 Import block is un-sorted or un-formatted` in `api/tests/test_health.py`.*
   - Why: the test file was written without running Ruff first. CI caught what the author missed.
   - Fix: reproduced locally with the same Ruff version, then `ruff check --fix api/`.

3. *Hidden problems: the `ruff format --check` step was skipped.*
   - Why: steps in a job run in order and stop at the first failure. Jobs are independent, so `test` still passed.
   - Running `ruff format --check` locally showed 2 more problems: a line longer than 88 characters
     in the test file, and an extra blank line in `api/app.py` left over from the Entry 2 failure drill.
   - Fix: `ruff format api/`, reviewed with `git diff`, re-ran lint and tests.
   - Possible improvement: `if: ${{ !cancelled() }}` on the format step, so one CI run shows all lint problems.

4. *History note:* commit `209fbb8` ("add") accidentally added a stray `..` line to `ci.yml`, removed
   again in `3fa88a8`. Squash-merging the PR will combine these into one clean commit on `main`.

5. *SonarCloud quality gate failed: security hotspot on `pip install` without `--only-binary`.*
   - Why: a source package (sdist) runs its own build scripts during install, so it can execute code on the runner.
   - Fix: `pip install --only-binary :all:` (ready-made wheels only), fixed in code rather than marked "Safe".

6. *An invalid workflow was merged to `main`, and lint and test never ran.*
   - Why: a step was missing its `- ` before `run:`, and YAML read the `: ` inside `:all: ruff` as a key/value pair.
     GitHub could not read the file, so each push only showed a failed run named after the file path
     (`.github/workflows/ci.yml`) instead of `CI`, and no job started.
   - Fix (PR #3): split the pip step into its own `- run:` and quoted the commands.

7. *SonarCloud quality gate failed: security hotspot on installing from unlocked requirements.*
   - Why: without exact versions and hashes, every install can pick up a different (or tampered) package.
   - Fix: `pip-compile` 7.6.1 with `--generate-hashes --strip-extras` creates `requirements*.txt` from the
     `.in` files; CI installs with `--require-hashes`.
   - Note: SonarCloud runs through Automatic Analysis (its GitHub app), not as a step in `ci.yml`.

**Lesson**
- CI is the quality-control gate, not a formality: it caught 3 issues that both the author and I missed.
- Reproduce a CI failure locally with the same tool version before fixing it; fix, review the diff, re-verify, then push.
- A failed step hides the steps after it, so "1 error" in CI can mean more problems underneath.
- Manual fixes after an incident (the drill) can leave small leftovers; automated checks find them.
- Clear commit messages matter: "add" tells a reviewer nothing.
- No green is not the same as passed: before merging, I check that the jobs actually ran.

**Next step**
- Record the result of the second CI run, then squash-merge the PR once it is green.
- Decide on `!cancelled()` for the format step.
- Add the Trivy repo scan (secrets, vulnerable dependencies, misconfiguration) to the CHECK stage.

---

## Entry 4 — 2026-10-16 — Simpler CI: one job with security scans before the build

**Problem**
- The CI only checked style and tests. Nothing looked for risky code, vulnerable packages
  or committed secrets, and no Docker image exists yet to scan.
- A first proposal (three jobs, check → test → scan, linked with `needs:`) was too hard to explain:
  each job runs on a clean runner, so every job repeated the same setup (download code, install
  Python, install packages), and the real checks were hidden among the copies.

**Decision**
- One job, `checks`, with named steps that run top to bottom: CHECK (Ruff) → TEST (pytest) →
  SCAN (bandit, then Trivy). A failed step stops the steps after it, so the order still works as stages.
- Scanners:
  - bandit 1.9.4 (2026-02-25): risky patterns in our own Python code. Tests are excluded because they use `assert` on purpose.
  - Trivy 0.75.0 (2026-10-01): known vulnerabilities in our packages and secrets in our files, in one tool.
    The same tool will scan the Docker image after the BUILD stage, so I learn one scanner and use it twice.
  - Considered pip-audit (packages) + gitleaks (secrets, including Git history). Kept as alternatives.
    pip-audit depends on `pip` itself, so the lock would need `--allow-unsafe`.
- Trivy runs from its official image **pinned by digest**, not through `aquasecurity/trivy-action`:
  - In March 2026, `trivy-action` tags were hijacked and malicious Trivy releases were published
    (advisory GHSA-69fq-xp46-6x23). The advisory says images referenced by digest were not affected.
  - Version 0.75.0 because it includes the fix for GHSA-mcj4-mphf-j9ff (fixed in 0.71.1), is about 2 weeks old
    (release cooldown; 0.76.0 was 1 day old), and is an immutable GitHub release.
  - Digest `sha256:af6acf9a6b85dfe389a1941505c0ce9efef52a4719635e1a962f022a3d855daa`, the same on
    ghcr.io and Docker Hub (checked 2026-10-15).
- Kept: `permissions: contents: read`, `persist-credentials: false`, actions pinned to verified SHAs
  (`checkout` v7.0.1, `setup-python` v7.0.0, the same as Entry 3), `--only-binary :all: --require-hashes`,
  `timeout-minutes: 10`.
- Concurrency changed: `cancel-in-progress` only for `pull_request` events, so a run on `main` is never cancelled.
- Removed the pip cache to keep the file short.
- Triggers in PR #4: unchanged (`pull_request` and `push` to `main`).
- Follow-up (same day): `push` now runs on every branch (`branches: ["**"]`), so CI gives feedback
  as soon as a branch is pushed, before any PR exists.
  - Trade-off: once a PR is open, each push starts two runs for the same code (`push` and `pull_request`).
    They are in different concurrency groups (`refs/heads/<branch>` vs `refs/pull/<n>/merge`), so neither
    cancels the other. Accepted: a run takes about 30 seconds and the repo is small.
  - Alternative considered: keep `push` on `main` only and open a draft PR early (the Entry 3 decision).

**Implementation**
- Branch `ci/simple-pipeline`, PR #4.
- `api/requirements-dev.in`: added `bandit==1.9.4`; regenerated `api/requirements-dev.txt`
  (bandit plus pyyaml, stevedore, rich, markdown-it-py, mdurl, all with hashes; other pins unchanged).
- `.github/workflows/ci.yml`: rewritten as one job with a plain-English comment and a `name:` per step.

**Verification**
- Before pushing: the YAML parses, and every step has exactly one `uses:` or `run:`.
- Prediction: green. Result: green.
- PR #4: CI run `38850082116` green (about 30 seconds), SonarCloud quality gate passed.
- Merged on 2026-10-16 (squash commit `4337fc3`). Run `38851009996` (`push` to `main`) green.
- Trivy's log listed only `api/requirements.txt` as a package file.
- Follow-up (push on every branch), PR #5:
  - Predicted 1 run after the push, then 2 in total after opening the PR. Correct.
  - Run `38852861207`: event `push`, branch `ci/push-all-branches`, before any PR existed. Green.
  - Run `38852940271`: event `pull_request`, same commit `f57f9bf`. Green.
  - Merged as `5c3644e`; run `38853010653` (`push` to `main`) green.
  - Deleting 5 old branches on GitHub started no CI runs.

**Troubleshooting**
1. *An uncommitted edit would have been lost.*
   - The planned tidy-up included `git reset --hard origin/main`, which discards uncommitted changes, and
     `api/requirements-dev.in` had an uncommitted edit.
   - Fix: `git restore` the file on purpose, tidy up, then redo the edit on the new branch.
2. *The lock file header showed `--no-index`, which I did not type.*
   - No pip config or environment variable sets it, and the new packages were still downloaded from PyPI,
     so it had no effect. Cause not found; only the header comment is affected.
3. *Trivy scanned `api/requirements.txt` but not `api/requirements-dev.txt`.*
   - Result: the runtime packages (what will ship in the image) are checked; the dev-only tools
     (pytest, Ruff, bandit) are not. Acceptable for now, because the dev tools never go into the image.
4. *Does pushing a feature branch run CI? (before the follow-up)*
   - Not by itself. The run for `ci/simple-pipeline` came from the `pull_request` event; there was no `push` run.
   - In the Entry 3 history, `push` runs on a feature branch did appear, named `.github/workflows/ci.yml`:
     with an invalid file, GitHub cannot read the `on:` filters or the `name:`.
5. *The follow-up commit landed on the already-merged branch, and no PR appeared.*
   - Why: I committed on `ci/simple-pipeline` (PR #4, already squash-merged). GitHub never opens a PR by itself,
     and a merged PR does not reopen. That branch was also built on the pre-squash history (`828d024`),
     not on `main` (`4337fc3`), so a new PR from it would have shown all of PR #4 again.
   - Fix: a new branch from the latest `main`, then `git cherry-pick d2e42af` to copy only that one commit
     (the copy got a new ID, `f57f9bf`). After switching to `main`, Entry 4 seemed to vanish from the journal;
     it was only inside the commit on the other branch.

**Lesson**
- Simple beats clever when I have to explain it: one job with named steps reads like a checklist.
- Each job runs on a clean runner. Separate jobs give separate results, but each one has to set itself up again.
- Anything that can move (a tag, a "latest" image) can be swapped by an attacker. A SHA or a digest cannot.
- Before choosing a tool's version, I read its security advisories, not just its release list.
- Before `git reset --hard`, I run `git status`: it throws away uncommitted work without asking.
- Once a PR is merged, its branch is finished. New work starts on a new branch from the latest `main`.

**Next step**
- Done: `docs/architecture.md` section 9 updated (CHECK stage marked Built).
- Still owed: failure drills for this pipeline (Predict → Break → Observe → Fix → Verify):
  Ruff, pytest, bandit, Trivy secret. Deferred so we can start the BUILD stage.
- Next: the BUILD stage, starting with the Dockerfile for the api.

## Entry 5 — 2026-10-16 — BUILD stage: hardened api image, built, proven and scanned in CI

**Problem**
- The api had no Docker image, so there was nothing to deploy to Kubernetes later.
- The CHECK stage's Trivy `fs` scan only reads `api/requirements.txt`. It cannot see what the base
  image adds (Debian packages, the Python interpreter, Python's own tools), yet all of that ships.

**Decision**
- Single-stage Dockerfile. Multi-stage was considered, but every package installs as a ready-made wheel,
  so there is nothing to compile and no build tools to leave behind.
- Base: `python:3.12.15-slim-trixie`, pinned by digest (`sha256:a6e34c59…11b1`, checked on Docker Hub 2026-10-16;
  the tag was last updated 2026-10-09, so it respects the release cooldown).
- Same locked install as CI (`--only-binary :all: --require-hashes`), no pip cache in the image.
- Runs as a numeric non-root user (uid 10001, no home, no login shell), so Kubernetes can enforce `runAsNonRoot` later.
- gunicorn with `--no-control-socket`: Kubernetes manages the process, so gunicorn's admin socket is not needed
  (less attack surface, and it fixed the error in Troubleshooting 1).
- CI (same single job, after the CHECK steps): BUILD (tag = commit SHA) → PROVE (start the container, call `/health`)
  → SCAN IMAGE. Kept in one job: the image built in one step is still there for the next steps.
- Image scan with the same pinned Trivy 0.75.0 image:
  - `docker save` the image to a tar file and give it to Trivy read-only (`--input`), so Trivy never gets
    the Docker socket (which is root-level control of the runner).
  - Report step: every severity, never fails. Gate step: `--severity HIGH,CRITICAL --ignore-unfixed --exit-code 1`,
    scanners `vuln,secret`.
  - A shared cache folder (`--cache-dir`): the report step downloads the vulnerability database,
    the gate reuses it (`--skip-db-update`).
  - Flags checked in Trivy's own docs at tag `v0.75.0` (the `trivy.dev/latest` pages showed older docs, around v0.67).
  - Stayed on 0.75.0: 0.76.0 was released 2026-10-14, only 2 days earlier (release cooldown).

**Implementation**
- Branch `build/api-image`, PR #7, squash-merged as `83024f7`.
- `api/Dockerfile` and `api/.dockerignore`.
- `.github/workflows/ci.yml`: steps "Build the api image", "Prove the image starts (/health)",
  "Save the image to a file", "Scan the image - full report (Trivy)", "Scan the image - gate (Trivy)",
  and "Show container logs" (`if: always()`). Header comment updated to list every stage.

**Verification**
- Local: image 216 MB; `/health` → 200; `/ready` → 503 without `DATABASE_URL` (expected: no database);
  `id` inside the container → uid 10001.
- CI run `38953043940` (image scan added): all steps green, job about 40 s. Report step 8 s, gate 1 s
  (the gate reused the cached database). Debian 13.7 (87 packages): 0 vulnerabilities; every Python package: 0.
- Run `38961064042` (header update) green. After the merge, run `38961293971` (`push` to `main`) green.

**Failure drill: the recalled base image** (Predict → Break → Observe → Fix → Verify)
- Break: on a throwaway branch `drill/old-base-image`, `FROM` changed to `python:3.12.1-slim-bookworm`
  (digest `sha256:a64ac5be…573e`, from 2024). `requirements.txt` unchanged.
- Predict (all correct): fs scan passes, build passes, `/health` passes, report runs, gate fails, logs are shown.
  Refined reasons: the fs scan passes because it only reads `requirements.txt`; the gate fails because of
  fixable HIGH vulnerabilities, not just because the image is old.
- Observe (run `38955673523`): every step green except the gate.
  - Full report: Debian 12.4 = 557 findings; pip 23.2.1 = 7; setuptools 69.0.3 = 3; wheel 0.42.0 = 1.
    setuptools and wheel are not in our requirements at all: they came with the old base image.
  - Gate, Python packages: setuptools CVE-2024-6345 (fixed in 70.0.0) and CVE-2025-47273 (fixed in 78.1.1),
    wheel CVE-2026-24049 (fixed in 0.46.2), all HIGH.
  - Debian HIGH rows with a fix were also seen, for example glibc (`libc-bin`) CVE-2024-2961 and
    xz (`liblzma5`) CVE-2025-31115. The gate's Debian count was not recorded.
- Fix: back to `build/api-image` (the good `FROM` line was never changed there); drill branch deleted
  locally and on GitHub, never merged.
- Verify: back on the trixie digest; run #25 on `build/api-image` was already green.
- Explain-back: the gate counted those rows because they were HIGH severity and a fix already existed.
  The other ~565 were removed by two filters: most were LOW or MEDIUM (`--severity`), and the remaining
  HIGH/CRITICAL ones had no fix yet (`--ignore-unfixed`). The full report still lists them all.

**Troubleshooting**
1. *gunicorn: "Control server error: Permission denied: '/home/freshtrack'".*
   - gunicorn 26 (since 25.1) opens a control socket in `$HOME/.gunicorn`, and our user has no home folder.
   - Fix: `--no-control-socket`.
2. *First CI PROVE run failed in 0 seconds (run `38859526216`): curl error 56, connection reset.*
   - curl called before gunicorn was listening, and `--retry-connrefused` does not retry error 56.
   - Fix: `--retry-all-errors` (up to 10 tries, 1 s apart; about 1 was needed), plus a separate
     "Show container logs" step that always runs. Run `38860539500` green.
3. *Docker cache predictions.* I confused pip's download cache with Docker's layer cache. A change to `CMD` only
   rebuilds nothing heavy: `CMD` is metadata, so every layer came from the cache.
4. *After pushing the drill branch, GitHub offered "Compare & pull request".* That is only an offer;
   no PR existed (checked: 0 PRs for the branch). The CI run came from the `push` trigger.
5. *The Dockerfile was not visible under `api/` on GitHub.* GitHub shows `main` by default, and the Dockerfile
   lived only on `build/api-image` until PR #7 was merged. After the merge it was on `main`.

**Lesson**
- "It runs" is not "it is safe": in the drill, lint, tests, the build and `/health` were all green,
  yet the image carried fixable HIGH vulnerabilities. Only the image scan saw them.
- I scan the finished image, not just my recipe card: the base image brings packages I never asked for.
- A gate should block only what I can fix (fixable HIGH/CRITICAL), and a full report keeps the rest visible.
  Ignored is not gone: unfixed problems still ship, so they need a regular re-scan and a rebuild when a fix appears.
- An old base image is old flour: same recipe, 557 more findings. Keep the base pinned and refreshed.
- Give a scanner only what it needs: a read-only tar file, not the Docker socket.
- A branch is a separate test kitchen; GitHub's homepage shows `main`. A PR exists only when someone opens it.

**Next step**
- Done: `docs/architecture.md` section 9 updated (BUILD, PROVE, SCAN marked Built for the api).
- SHIP: push the image to Docker Hub tagged with the git SHA, only on `main`, token as a GitHub secret.
- Later: a weekly scheduled re-scan, so new fixes are noticed without a code push.
- Still owed: CHECK-stage drills (Ruff, pytest, bandit, Trivy secret). Later todo: gunicorn access logs.

---

## Entry 6 — 2026-10-24 — SHIP stage: protect `main`, then push the scanned api image to Docker Hub

**Problem**
- The api image was built, proven and scanned in CI, but it was thrown away at the end of every run.
  Nothing could be pulled later by Kubernetes.
- `main` had no protection. Two commits ("Added README" `b0c4250` and its revert `73e24a6`) had gone
  straight to `main` without a PR. Once SHIP exists, every push to `main` publishes an image,
  so a direct push could ship code that never went through the PR checks.

**Decision**
- Protect `main` first, then add SHIP.
- Ruleset `protect-main` (Active, empty bypass list, target: default branch): restrict deletions,
  block force pushes, require a pull request (0 approvals because I work alone, squash only),
  require status checks `checks` and `SonarCloud Code Analysis`, branch must be up to date.
- A separate `ship` job instead of more steps in `checks`:
  - the Docker Hub token is only in a job that runs on a push to `main`;
  - the image reaches it as an artifact (`image.tar`, kept 1 day), so the exact scanned file is pushed, not a rebuild.
- The token lives in a GitHub **environment** `dockerhub` that only the `main` branch may use.
  A repository secret would be available to any branch, because CI runs on every push.
- Docker Hub token: Repo Read & Write (no Delete), 90-day expiry. A Docker Hub token cannot be limited to one
  repository, so the environment lock matters. The username is an environment variable, not a secret.
- `docker login --password-stdin` in a plain step instead of `docker/login-action`: one less third-party action.
- Tag = commit SHA only, no `latest`.
- New actions pinned to full SHAs, checked against their release tags, both released 2026-10-07 (past the cooldown):
  `actions/upload-artifact` v7.0.2 → `cf430e03…`, `actions/download-artifact` v8.0.2 → `9000827c…`.
  Each tag commit is the current tip of that repo's `main` and is signed (verified by GitHub). Inputs checked in each `action.yml`.
- Docker Hub repository `samayohub/freshtrack-api`, public (no secrets inside; interviewers can pull it).

**Implementation**
- Ruleset and environment created in the GitHub settings (no code).
- Branch `ship/dockerhub`, PR #10, squash-merged as `4530ec1`.
- `.github/workflows/ci.yml`: header updated; new step "Hand the image to the ship job" after the Trivy gate
  (only on a push to `main`); new job `ship` (`needs: checks`, same `if`, `environment: dockerhub`):
  get the scanned image → load → tag → log in → push → log out (`if: always()`).

**Verification**
- Ruleset: GitHub's API for `main` lists `deletion`, `non_fast_forward`, `pull_request` (0 approvals, squash),
  `required_status_checks` (`checks`, `SonarCloud Code Analysis`, strict).
- Environment: API shows `dockerhub` with a custom branch rule allowing only the branch `main`.
- Branch run `40141555540` (`9585cb0`): `checks` green, hand-off step skipped, `ship` skipped (as predicted).
- `main` run `40141996431` (`4530ec1`): `checks` 49 s → `ship` 26 s, all green, artifact `api-image` 49.9 MB.
- Docker Hub: 0 tags before, 1 tag after: `4530ec151d4f2542353a5ef544fbbe65f95a83a5`
  (digest `sha256:1f337e0a…89e2`, 52.5 MB compressed). The tag is the squash merge commit, not the branch commit.
- Pulled on my laptop and ran it: `/health` → 200 `{"status":"ok"}` (`Server: gunicorn`);
  `/ready` → 503 `{"status":"not ready"}` (expected: no database yet).

**Failure drill: a direct push to `main`** (Predict → Break → Observe → Fix → Verify)
- Predict: the commit succeeds locally, the push fails because of the rules, the commit stays only on my laptop,
  and being the owner does not let me through. All correct. Refined: GitHub's server refuses the push
  (Git on my laptop knows nothing about rules), and owners are blocked because the bypass list is empty.
- Break: `git commit --allow-empty -m "drill: direct push to main"` then `git push origin main`.
- Observe: `remote: error: GH013: Repository rule violations found for refs/heads/main`,
  "Changes must be made through a pull request", "2 of 2 required status checks are expected",
  `! [remote rejected] main -> main`. Local `main` was "ahead 1" (`c6e015b`); GitHub stayed on `933aa09`.
- Fix: `git reset --hard origin/main` (safe: the working tree was clean, only the empty commit was dropped).
- Verify: `## main...origin/main`, `933aa09`.
- Explain-back: a direct push to `main` would skip the checks; refined to "once SHIP exists, it would publish
  an unchecked image". "Server side" refined to "enforced by GitHub, where everyone pushes, not by memory".
- SHIP predictions (branch push and after merge): 5 of 6 fully right; corrected that `ship` shows as *skipped*,
  and that the whole `checks` job runs again on `main` before `ship` starts.

**Troubleshooting**
1. *GitHub API answered 301 for `s12samola-wft/freshtrack`.* The repository had moved to `samcloud-dev/freshtrack`.
   The local remote already pointed to the new name, and CI and SonarCloud still worked.
2. *The ruleset screenshot did not show SonarCloud, but the API listed it as required.* The check list was cut off in
   the screenshot. The API is the source of truth for what is enforced.
3. *Which tag to look for on Docker Hub?* A squash merge makes a new commit on `main`, so the tag is `4530ec1…`,
   not the branch commit `9585cb0`.
4. *Deleting merged branches.* After a squash merge, `git branch -d` refuses ("not fully merged"), because the branch
   commits are not on `main`. I first confirmed each branch had no difference from its squash commit
   (`git diff`), then used `git branch -D` and `git push origin --delete`.

**Lesson**
- A pipeline's order only protects me if nobody can walk around it. Branch protection is what makes
  "only checked code ships" true, and I proved it with a rejected push, not just a settings page.
- I keep the key in a locker that opens only for `main`: an environment secret, not a repository secret,
  because my CI runs on every branch.
- I ship the exact image I scanned. Rebuilding would give me a new, unscanned image with the same name.
- A green CI run proves I pushed the image; pulling it and calling `/health` proves someone can use it.
- One tag per commit, never `latest`: I always know which code is running, and rolling back means picking an older SHA.

**Next step**
- Done: `docs/architecture.md` (SHIP Built, ruleset and token security) and README status updated.
- Still to answer (explain-back): why does `ship` load an artifact instead of rebuilding, and which two locks stop a branch from shipping?
- Next stage: Minikube deploy of the api with PostgreSQL (StatefulSet, PVC, Secret, probes), pulling `samayohub/freshtrack-api:<SHA>`.
- Later: renew the Docker Hub token before it expires (with the planned 90 days: about 2027-01-22; confirm the date on Docker Hub).
  Weekly scheduled re-scan. Trivy 0.76.0 is now past the cooldown (upgrade in a small PR).
- Still owed: CHECK-stage drills (Ruff, pytest, bandit, Trivy secret).
