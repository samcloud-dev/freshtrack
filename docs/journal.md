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

---

## Entry 7 — 2026-10-31 — Minikube dress rehearsal begins: verified image, new cluster, Namespace and api Deployment

**Problem**
- The api image was on Docker Hub, but I had not yet checked that the published image is the one CI scanned.
- FreshTrack will run for one week on k3s on AWS. I want to find problems at home on Minikube first,
  so the AWS week costs as little as possible.
- My Minikube (v1.38.1) only supported Kubernetes up to v1.35.1, while the k3s `stable` channel is v1.36.5+k3s1.
  Its default network plugin also ignores NetworkPolicies, while k3s enforces them.

**Decision**
- Plan agreed for the rehearsal: plain YAML first (Namespace, api Deployment, Service, Secret, PostgreSQL),
  then app milestone A (items table and routes), then a Helm chart with `values-minikube.yaml` and `values-aws.yaml`,
  then Traefik, cert-manager, basic auth, NetworkPolicy, OpenBao + External Secrets Operator + Reloader,
  Argo CD, and finally a memory measurement with `kubectl top`.
- The Ingress will route only `/` to web. The api stays internal (ClusterIP); a mobile app is out of scope for v1.
- Upgrade Minikube to v1.39.0 (released 2026-09-02, past the cooldown): it supports Kubernetes 1.36 and uses containerd by default, like k3s.
- A new profile `freshtrack` instead of deleting the old ones: Kubernetes v1.36.4 (the newest 1.36 that Minikube offers;
  same minor version as k3s, only the patch differs), containerd, Calico, 6 GB / 4 CPUs as a ceiling, metrics-server.
- The api image is referenced by tag **and** digest, so the cluster runs exactly the bytes CI scanned.

**Implementation**
- Branch `deploy/k8s-basics` (not pushed yet; one PR after the plain-YAML steps).
- Minikube v1.39.0 installed from the GitHub release after a SHA-256 check.
- `minikube start -p freshtrack --kubernetes-version=v1.36.4 --container-runtime=containerd --cni=calico --memory=6g --cpus=4`,
  `minikube addons enable metrics-server`, `minikube profile freshtrack`. Old profiles `minikube` and `netpol-lab` kept.
- `deploy/k8s/namespace.yaml` (`03c6ded`): Namespace `freshtrack` with the recommended labels.
- `deploy/k8s/api-deployment.yaml` (`13d708c`): 1 replica; image `samayohub/freshtrack-api:e6c9f93…@sha256:adb7d02f…`;
  no service account token; non-root user 10001, seccomp `RuntimeDefault`, no privilege escalation, all capabilities dropped;
  requests 50m CPU / 96Mi, limits 250m CPU / 192Mi; startup probe `/health`, readiness probe `/ready` (timeout 3 s,
  because the app waits up to 2 s for the database), liveness probe `/health`. No `DATABASE_URL` yet (on purpose).

**Verification**
- Image: `docker pull` of tag `e6c9f93…`, then `docker inspect` showed `sha256:adb7d02f…c4aa9`, the same digest as Docker Hub.
  Ran it with `-p 127.0.0.1:8000:8000`: `/health` → 200 `{"status":"ok"}`, `/ready` → 503 `{"status":"not ready"}` (no database).
- Minikube download: `sha256sum --check` → `OK` (`b738496d…5aa4`); `minikube version` → v1.39.0; old profiles still listed.
- Cluster: node `freshtrack` `Ready`, v1.36.4, `containerd://2.3.4`; `calico-node` and `calico-kube-controllers` Running.
  Empty-cluster baseline from `kubectl top nodes`: 219m CPU, **1350Mi** memory (Kubernetes + Calico + metrics-server, no FreshTrack yet).
- Namespace: before, 4 system namespaces; `apply` → `created`; second `apply` → `unchanged`; labels shown with `--show-labels`.
- Deployment: Pod `Running`, READY `0/1`, 0 restarts; events show readiness `statuscode: 503`. A server-side dry run passed before every apply.
- After adding the startup probe: startup probe failed 3 times while gunicorn booted (15 allowed), then passed; no liveness failures.

**Failure drills**
- *Drift (Namespace).* Predict: `apply` prints `configured` and the label comes back. Break:
  `kubectl label ns freshtrack app.kubernetes.io/part-of=oops --overwrite`. Observe: label shows `oops`.
  Fix: `kubectl apply -f deploy/k8s/namespace.yaml` → `configured`. Verify: label back to `freshtrack`. Both predictions right.
  Note: `apply` only restores fields written in the file; a label added by hand that is not in the file would stay.
- *No database (Deployment).* Predicted 0/1, no restarts, `/health` passing and `/ready` failing: right.
  Predicted STATUS "Not Ready": wrong, STATUS shows `Running` (the process); READY shows the probe result.

**Troubleshooting**
1. *`docker: command not found` in WSL.* Docker Desktop was not running. Minikube (Docker driver) was down for the same reason.
2. *The container "stopped" after `docker run`.* It had not stopped: without `-d` it runs in the foreground and waits.
   `docker ps` showed it Up. I used a second terminal for `curl`.
3. *`rm: remove write-protected regular file`.* The downloaded binary belonged to root (the download had run with `sudo`).
   In `/tmp` (sticky bit) only the owner can delete a file, so `sudo rm`. Only the `install` step needs `sudo`.
4. *Second `kubectl apply` printed `unchanged`, not `created`.* `apply` is declarative: it compares the file with the cluster
   and only changes what differs.
5. *Liveness probe failed once with `connection refused`.* Probes started at once, before gunicorn was listening.
   1 failure out of 3 allowed, so no restart. Added a startup probe, which holds off liveness and readiness until the app has booted.
6. *Two Pods, both 0/1, after adding the startup probe.* A changed Pod template makes a new ReplicaSet (rolling update).
   With 1 replica, `maxSurge 25%` rounds up to 1 and `maxUnavailable 25%` rounds down to 0, so the old Pod is only removed
   once the new one is Ready. Without a database it never is, so the rollout waits. It should finish in Step 5.
7. *The cluster pulled the image again (25.6 s)* although my laptop's Docker had it: Minikube's containerd has its own image store.

**Lesson**
- I check the digest, not just the tag: the digest proves I run the exact image CI scanned.
- `127.0.0.1` keeps a port reachable only from my laptop. The api has no login and will hold personal data, so it stays closed to others.
- A rehearsal is only useful if it matches the real thing, so I matched the Kubernetes version, container runtime
  and network-policy enforcement of k3s.
- `kubectl apply` describes what I want, not what to do. Running it again is safe, which is what GitOps relies on.
- Running is not Ready. Readiness failures stop traffic; only liveness failures restart a container. A startup probe protects slow starts.
- A stuck rollout is a safety feature: Kubernetes will not replace a working version with one that is not Ready.
- I only use `sudo` for the step that needs it.

**Next step**
- Step 3: api Service (ClusterIP), then Step 4: database Secret, Step 5: PostgreSQL StatefulSet + PVC (the rollout should then finish).
- Later on this branch's PR: update `docs/architecture.md` (open decision 2: Traefik Ingress; OpenBao chosen; monitoring stays on Minikube
  during the AWS week; Minikube profile details) and the README roadmap order.
- Small refinement for the Helm step: give the startup probe `timeoutSeconds: 2`.
- Still owed: Entry 6 explain-back (artifact vs rebuild; two locks), CHECK-stage drills, Trivy 0.76.0 upgrade,
  confirm the Docker Hub token expiry date.

## Entry 8 — 2026-11-02 — api Service (ClusterIP) and the database Secret

**Problem**
- Pods get a new IP every time they are replaced, so web and the expiry-checker need one stable address to reach the api.
- The api (and soon PostgreSQL) needs a database password, which must never be baked into an image or committed to Git.
- Before starting: Docker Desktop was off again, so the `freshtrack` Minikube profile was down.

**Decision**
- A `ClusterIP` Service named `api`: reachable only inside the cluster, because the api has no login.
  Port 80 for callers, `targetPort: http` (the named container port 8000), so a port change only touches the Deployment.
- The selector uses only the two `app.kubernetes.io/*` labels, never `pod-template-hash`, so it keeps matching across rollouts.
- The Secret is created by hand with `kubectl create secret` from a file **outside the repo**. Nothing is committed.
  OpenBao + External Secrets Operator replace this step after the Helm stage (option A). I considered installing them first,
  but they need Helm, OpenBao dev mode keeps data only in memory (this morning's restart would have wiped it),
  and the Pod side (`secretKeyRef`) stays exactly the same, so only one command is replaced later.
- Password from `openssl rand -hex 24`: hex characters only, so nothing breaks the `DATABASE_URL`
  (`@`, `/` and `:` mean something in a URL).

**Implementation**
- `deploy/k8s/api-service.yaml`: Service `api`, namespace `freshtrack`, type `ClusterIP`, port `http` 80 → `targetPort: http`, TCP.
  Written by me; a final newline was added after review.
- `~/.freshtrack/` (mode 700) holds `db.env` (mode 600, created with `umask 077`) with the keys
  `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` and `DATABASE_URL` (host `postgres:5432`, the Step 5 Service name).
- `kubectl create secret generic postgres-credentials -n freshtrack --from-env-file=$HOME/.freshtrack/db.env`,
  after a `--dry-run=server` check.

**Verification**
- Service: server dry run → `created (server dry run)`; apply → `created`; ClusterIP `10.109.109.221`, `80/TCP`.
- EndpointSlice `api-…`: port 8000 (the named port resolved), 2 addresses (`10.244.23.134`, `10.244.23.138`),
  both `ready=false serving=false`.
- `curl` from a temporary Pod (`curlimages/curl:8.17.0`) to `http://api/health`: DNS resolved `api` to `10.109.109.221`,
  then `Connection refused` after 12 ms. Expected until Step 5: no Pod is Ready, so there is nothing to forward to.
- Secret: `kubectl describe` shows only key names and byte sizes, which match the expected lengths without showing any value:
  `POSTGRES_USER` 10, `POSTGRES_DB` 10, `POSTGRES_PASSWORD` 48 (24 random bytes as hex), `DATABASE_URL` 97
  (13 + 10 + 1 + 48 + 15 + 10). Type `Opaque`.
- File permissions: `~/.freshtrack` `drwx------`, `db.env` `-rw-------`.

**Failure drills**
- *Prediction check (Service).* Predicted 2 endpoints and `curl` failing because there is no database.
  Half right: 2 addresses are listed, but 0 are ready, which `-o wide` does not show.
  My first explanation (the startup probe was still running) was wrong: both Pods showed `started=true`.
  The **readiness** probe fails (no database), so kube-proxy has no ready endpoint and refuses the connection before Flask is reached.
  That is why even `/health` failed.
- *Prediction check (Secret).* Predicted `describe` shows the name and keys, not values: right (I listed one key twice and missed `POSTGRES_PASSWORD`).
- Still to do for this stage: a Break drill on the Service (for example a wrong selector label → empty EndpointSlice).

**Troubleshooting**
1. *Each api Pod showed `RESTARTS 1` after Minikube came back.* The last state was reason `Unknown`, exit code 255:
   the node had shut down with Docker Desktop, and the kubelet started the containers again on boot. Not a liveness kill
   (that shows reason `Error` and a `Killing` event).
2. *The old Pod (no startup probe) logged a liveness `connection refused` again during boot; the new Pod logged startup-probe
   failures instead*, including one `context deadline exceeded` (default 1 s timeout). This confirms the startup probe and the planned `timeoutSeconds: 2`.
3. *The `curl` output appeared twice.* curl finished before `kubectl run -it` could attach, so kubectl fell back to printing the logs.
   It was one attempt: the same source port (38358) in both copies.

**Lesson**
- A Service finds Pods by labels, and forwards only to **Ready** ones. A listed endpoint is not the same as a ready endpoint.
- Liveness failure restarts the container; readiness failure stops traffic. A failed readiness probe blocks every request, not just `/ready`.
- `Connection refused` in milliseconds means "nothing ready behind this address"; a timeout would point to something dropping packets.
- Kubernetes Secrets are base64-encoded, not encrypted. RBAC and etcd encryption protect them, and Git must never contain the values.
- I can verify a Secret without exposing it by comparing byte sizes with the expected lengths.
- Doing the Secret by hand first shows me what OpenBao + ESO will automate; only the creation step changes later.

**Next step**
- Step 5: PostgreSQL as a StatefulSet with a headless Service and a PVC (new terms: StatefulSet, headless Service, PV, PVC, StorageClass).
  Check the current supported PostgreSQL versions first. Then wire `DATABASE_URL` into the api Deployment with `secretKeyRef`.
  Expected result: `/ready` → 200, both EndpointSlice addresses `ready=true`, the stuck rollout finishes, the same `curl` test succeeds.
- Optional: label the Secret with `app.kubernetes.io/part-of=freshtrack` and `app.kubernetes.io/name=postgres` (not done yet).
- Still owed: Entry 6 explain-back, CHECK-stage drills, Trivy 0.76.0 upgrade, confirm the Docker Hub token expiry date.

## Entry 9 — 2026-11-03 — PostgreSQL StatefulSet, api connected, data survives a Pod deletion

**Problem**
- The api Pods stayed `0/1` (not Ready) since Entry 7: `/ready` returned 503 because there was no database and the api had no `DATABASE_URL`.
- The rollout from Entry 7 was stuck with two ReplicaSets, one Pod each, neither Ready.
- The database must keep its data when its Pod is replaced, and must have a stable address.
- Before starting: Docker Desktop was off again, so the cluster was down. Restarted Docker Desktop and `minikube start -p freshtrack`.

**Decision**
- **PostgreSQL 18.6.** Checked the official [versioning policy](https://www.postgresql.org/support/versioning/) on 2026-11-03:
  supported majors are 14–18; 14 reaches end of life on 2026-11-12; 19 is only a release candidate. 18 has support until November 2030.
- **Official image pinned by digest:** `postgres:18.6-trixie@sha256:3a4264520e121176619f54ff867d12774bc81e95e7b84db58d63bccdb6144b81`
  (the same digest as `18.6`; covers amd64 and arm64; tag last rebuilt 2026-10-31 for OS updates).
- **StatefulSet, not Deployment:** stable Pod name `postgres-0` and its own disk (PVC `data-postgres-0`) that is reattached when the Pod is replaced.
- **Headless Service** `postgres` (`clusterIP: None`): DNS points straight at the Pod. Matches `postgres:5432` in the Secret's `DATABASE_URL`.
- **Mount at `/var/lib/postgresql`:** the [image docs](https://hub.docker.com/_/postgres) say version 18+ changed the volume path
  (data now in `/var/lib/postgresql/18/docker`). The old `/var/lib/postgresql/data` would have left the data off the PVC.
- **Only the three keys the database needs** (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) via `secretKeyRef`, not `envFrom`,
  so the database does not receive `DATABASE_URL`. The api gets only `DATABASE_URL`.
- No `storageClassName`, so the cluster default is used (`standard` on Minikube, `local-path` on k3s): one file for both clusters.
- `persistentVolumeClaimRetentionPolicy: Retain` written out (it is the default) so it is visible in reviews.
- `terminationGracePeriodSeconds: 60` so PostgreSQL can shut down cleanly.
- Probes: startup and readiness run `pg_isready -h 127.0.0.1` (TCP, so it fails during first-time setup); liveness only checks the TCP port,
  so a busy database is not restarted.
- `readOnlyRootFilesystem` left out for now (PostgreSQL writes to `/var/run/postgresql` and `/tmp`); revisit in Helm.
- Replicas stay at 1 for now. Scaling the api to 3 waits for the Helm chart and the game-day stage.
- Failure drills for every stage are moved to one game-day stage after FreshTrack is fully deployed with monitoring (CLAUDE.md updated).

**Implementation**
- `deploy/k8s/postgres-service.yaml`: headless Service `postgres`, port 5432 → named port `postgres`.
- `deploy/k8s/postgres-statefulset.yaml`: 1 replica, `serviceName: postgres`, `runAsUser/runAsGroup/fsGroup 999`, `runAsNonRoot`,
  seccomp `RuntimeDefault`, no privilege escalation, all capabilities dropped, no service account token,
  requests 100m / 256Mi, limits 500m / 512Mi, `volumeClaimTemplates` `data` 1Gi `ReadWriteOnce`.
- `deploy/k8s/api-deployment.yaml`: added `env` `DATABASE_URL` from Secret `postgres-credentials` with `secretKeyRef`.
- I typed all three files and applied them myself. I applied them before the review step; the review afterwards found the YAML valid,
  the live objects matching the files (`kubectl diff` empty), and only whitespace-only blank lines to tidy, which were removed.

**Verification**
- Service `postgres`: `CLUSTER-IP None`. EndpointSlice was empty (`<unset>`) until the database Pod existed, then `10.244.23.150:5432`.
- PVC `data-postgres-0` `Bound`, 1Gi, `RWO`, `standard`; PV reclaim policy `Delete`.
- `postgres-0` `1/1 Running`, 0 restarts. Inside the Pod: `uid=999(postgres)`; `show data_directory` → `/var/lib/postgresql/18/docker`; `PostgreSQL 18.6`.
- api rollout: `deployment "api" successfully rolled out`. New ReplicaSet `api-5b47557d66` 1/1; both old ReplicaSets scaled to 0 (kept as history, 3 revisions).
- From inside the cluster, through the Service `api.freshtrack.svc.cluster.local`: `/health` → `200 {"status":"ok"}`, `/ready` → `200 {"status":"ready"}`.
- **Data survival check:**
  - Wrote a test row (`proof` table) at 03:14:04 UTC.
  - Before: `postgres-0` IP `10.244.23.150`, age 51m.
  - `kubectl delete pod postgres-0`: `Terminating` → `Completed` (clean exit) → new `postgres-0` → `1/1` in about 5 s, new IP `10.244.23.152`.
  - New Pod log: `Database directory appears to contain a database; Skipping initialization`, and `database system was shut down at 03:18:27` (clean shutdown, no crash recovery).
  - `SELECT * FROM proof` returned the same row and timestamp. PVC unchanged: same volume `pvc-360eabc1-…`, age 55m (older than the new Pod).
  - api stayed `1/1`, 0 restarts.

**Failure drills**
- *Prediction check (rollout).* Predicted 2 api Pods once settled. Wrong: it settles at 1 (`replicas: 1`); I saw 2 only because the Entry 7 rollout was stuck.
  Right that old Pods go only after the new one is Ready (`maxSurge 1`, `maxUnavailable 0`).
- *Prediction check (delete `postgres-0`).* Same name: right. Same IP: wrong (Pod IPs change; the name and DNS stay stable).
  api not Ready: it stayed Ready, because the database was back in about 5 s and readiness needs 3 failures in a row (about 15 s).
  Data survives: right; the reason is that the PVC is kept and reattached by Pod name.
- Break drills are moved to the game-day stage after full deployment.

**Troubleshooting**
1. *`FailedScheduling … pod has unbound immediate PersistentVolumeClaims` on first create.* The PVC was still being provisioned; scheduled within a second. Normal.
2. *One startup-probe failure on `postgres-0` (`127.0.0.1:5432 - no response`).* During first-time setup the image runs a temporary server without TCP. 1 of 30 allowed failures.
3. *`received fast shutdown request` in the first log.* Not a crash: the temporary setup server stopping before the real one starts.
4. *Two startup-probe failures on the api after the cluster restart, and `RESTARTS 3`.* The restarts were the node shutting down with Docker Desktop
   (reason `Unknown`, exit code 255, `SandboxChanged`). The probe failed 2 of 15 allowed times, so it never restarted anything.
5. *The terminal sat at a `>` prompt.* I typed into a heredoc (`<<'SQL'`) without the closing `SQL` line. `Ctrl+C` cancelled it (nothing was sent); I used `kubectl exec -it` and `psql` interactively instead.
6. *Finding:* during the delete check the api logged one readiness failure as a **timeout** (`context deadline exceeded`), not a 503.
   *(Corrected 2026-11-03.)* At first I wrote that the database check has no connect timeout. That was wrong: `app.py` already uses
   `connect_timeout=2`. The probe's 3 s still ran out once, so the exact cause is not confirmed yet. Possible causes to test later:
   the DNS lookup of `postgres` is not covered by `connect_timeout`, or libpq tried more than one address. To investigate in the game-day stage.
7. *Minikube `hostpath` storage does not enforce size or `fsGroup`.* `df` inside the Pod showed the node disk (1007G), and the folder is `drwxrwxrwx root`.
   PostgreSQL then set its own data folder to `drwx------ postgres`. Cloud disks enforce the size.

**Lesson**
- A StatefulSet gives a database a stable name and its own disk. The data lives in the PVC, outside the Pod, so deleting the Pod does not delete the data.
- Pod IPs always change. Applications must use the Service DNS name, never an IP.
- Readiness handles start-up order: the api does not need a "wait for the database" script; it is simply not Ready until the database answers.
- `secretKeyRef` puts only a pointer in Git. Secret values in env are read at container start, so a changed Secret needs a restart (Reloader, later).
- The official image's own docs matter: the PostgreSQL 18 mount path changed, and old guides would have silently lost data.
- Review before apply: my YAML worked, but checking first is the habit that catches mistakes before they reach the cluster.

**Next step**
- Open one pull request for milestone 2 (`deploy/k8s-basics` → `main`). After CI passes and it is merged, mark the Kubernetes basics as Built.
- Milestone 3: items table and routes in the api. Drop the `proof` test table before the schema work.
- Optional: label the Secret with `app.kubernetes.io/part-of=freshtrack` and `app.kubernetes.io/name=postgres`.
- Still owed: Entry 6 explain-back, Trivy 0.76.0 upgrade, confirm the Docker Hub token expiry date.

**Addendum (2026-11-03): SonarCloud gate, ephemeral storage, merge**
- *Problem.* The SonarCloud quality gate failed on PR #12: "Specify a storage request / storage limit for this container" on both the api and postgres containers.
  We had set CPU and memory, but not **ephemeral storage** (the container's scratch disk: its writable layer and its logs).
  Without a limit, one container could fill the node disk and get every Pod on that node evicted.
- *Decision.* Starting values, to be measured in the operations stage: api request 64Mi, limit 256Mi; postgres request 128Mi, limit 512Mi.
  The database files are on the PVC, which does not count as ephemeral storage.
- *Troubleshooting.* My first edit added a second `resources:` block to the api container (YAML keeps only the last one, silently),
  and pasted the postgres block at the end of the file, inside `volumeClaimTemplates`, where it replaced `storage: 1Gi`.
  The YAML parser said both files were fine. The **server-side dry run** caught it:
  `The StatefulSet "postgres" is invalid: spec: Forbidden: updates to statefulset spec for fields other than 'replicas', 'ordinals', 'template', ...`
  (`volumeClaimTemplates` cannot change after creation). Fixed by adding two lines inside each container's existing `resources:` block.
- *Verification.* `kubectl apply --dry-run=server` → both `configured`; after apply both Pods `1/1`; `postgres-0` shows
  `ephemeral-storage` 128Mi / 512Mi in its resources. Commit `b74965d`. SonarCloud then passed.
- *Merge.* PR #12 squash-merged as `03ce114`. The file snapshot (tree) of `main` is identical to the branch tip.
  `main` CI: `checks`, `SonarCloud Code Analysis` and `ship` all passed; Docker Hub tag `03ce114…` (same app code as `e6c9f93`).
- *Lesson.* A YAML syntax check only proves the file parses. `kubectl diff` or `--dry-run=server` proves the cluster accepts it. Edit inside an existing block; do not paste a new one.

## Entry 10 — 2026-11-07 — Milestone 3: items api built, shipped and running on Minikube with real groceries

**Problem**
- Until now the api only had `/health` and `/ready`. FreshTrack could not store a grocery.
- Version 1 needs: add an item, list active items soonest date first, and mark an item used or discarded without deleting it.
- Once built and shipped, the new image had to replace the old one in the cluster, and the cluster database needed the `items` table.

**Decision**
- One `items` table (`api/schema.sql`) with CHECK constraints, so the database itself rejects a bad location, date type or status.
- Input checked in Python first (`validation.py`), returning `400` with every field error at once, not only the first.
- All SQL in `db.py`, with values passed as parameters (never pasted into the SQL text), which prevents SQL injection.
- Used and discarded items get `status` and `closed_at`; rows are never deleted (trial data).
- Any database error returns `503 "Database unavailable."` and logs only the error class name, never connection details.
- Table creation by `init_db.py`, safe to run more than once. Running it as a Kubernetes Job is planned; for now it is run by hand.
- Deploy by changing the image tag + digest in `deploy/k8s/api-deployment.yaml` on a feature branch (`deploy/items-api-image`), so Git stays the source of truth.

**Implementation**
- *Build (2026-11-04, PR #14, merged as `627d2a6`):* `schema.sql` → `validation.py` → `db.py` → `app.py`, explained file by file.
  Endpoints: `GET /items`, `POST /items`, `PATCH /items/<id>`. Dockerfile `COPY` extended to the new files. README updated.
- *Ship:* CI pushed `samayohub/freshtrack-api:627d2a69ed029891a637a40a50e1d161f31b7849`,
  digest `sha256:75618b3ff72a2814b61d18e873047c451758350c8a3168e28eea98364f8f5976` (2026-11-05 03:45 UTC).
- *Deploy (2026-11-07):* started the stopped cluster (`minikube start -p freshtrack`), replaced the image line, `kubectl apply`.
  Created the table with `kubectl exec -n freshtrack deploy/api -- python init_db.py`.
  Dropped the Entry 9 `proof` test table after checking its contents (`DROP TABLE proof;`).
  `psql` was run with the container's own `$POSTGRES_USER` / `$POSTGRES_DB`, so no credential was printed.

**Verification**
- Build: 61 tests passed (unit + integration against a throwaway `postgres:18.6`). Smoke test: `/health` 200, `/ready` 503 without a database.
- Rollout: `deployment "api" successfully rolled out`; new Pod `api-657b677b4c-…` 1/1 on the `627d2a6…` image; old ReplicaSets kept at 0 Pods (history for rollback).
- Before the table existed: `/ready` → `200`, `/items` → `503`; api log `Database error: UndefinedTable`.
- After `init_db.py`: `/items` → `200 {"items":[]}`.
- Added two real groceries with `POST /items` (`201`). `GET /items` returned them **soonest date first**:
  milk (best before 2026-11-01, already past, added second) before juice (best before 2026-11-10, added first). Both `status: active`, `closed_at: null`.
- `\dt` after the cleanup: only `items`.

**Troubleshooting**
1. *Trivy gate failed on the build:* HIGH CVE-2026-109518 in `apt` 3.0.3 (fixed in 3.0.4, DSA-6607-1). The newest `python:3.12.16-slim-trixie`
   still had 3.0.3. Temporary fix: the Dockerfile upgrades `apt` and `libapt-pkg7.0` to 3.0.4, with a comment to remove it when the base image catches up.
2. *One integration test failed:* a bug in the test helper (a `name` argument clash), not in the app. Fixed with `item.update(changes)` → 61 passed.
3. *Dockerfile edited in the wrong folder:* I changed it in the main folder instead of the `freshtrack-items` worktree. Moved with `cp` + `git restore`.
4. *Cluster down at start:* `connection refused` from kubectl; `minikube profile list` showed `freshtrack` `Stopped`. Started it; data was intact.
5. *`port-forward` failed: `bind: address already in use` on 8080.* `docker ps` showed a Jenkins container from another lab holding 8080.
   Fix: stop Jenkins (or use another local port such as `8081:80`; the left number is my laptop, the right one the Service).
6. *`/items` returned `404`, not the expected error.* The Pod behind the Service was the **old** image again.
   `kubectl rollout history` showed revision 4 gone and revision 6 new, and the last change came from plain `kubectl`, not `kubectl apply`:
   the signature of a `kubectl rollout undo`. The cluster had drifted from the YAML in Git. Fix: `kubectl apply -f deploy/k8s/api-deployment.yaml` again.
7. *Predicted `500`, got `503`.* The app's error handler turns every database error into 503. The log line `UndefinedTable` gave the real cause.

**Lesson**
- `kubectl get deploy` shows the desired state (the order); `kubectl get pods` shows the actual state (the kitchen). A controller works until they match.
- A rolling update with 1 replica starts the new Pod first and removes the old one only when the new one is Ready, so there is no downtime.
- Readiness checked that the database answers, not that my table exists. A Pod can be Ready and still not able to do its job.
- The HTTP status code says something failed; the logs say what. Check `kubectl logs` before trusting a guess.
- Manual commands like `rollout undo` make the cluster drift from Git. Argo CD will later detect and correct this automatically.
- 400 = my request broke the rules; 404 = the thing does not exist; 5xx = the server side failed.

**Next step**
- Open the pull request for `deploy/items-api-image` (image bump + this entry). After merge, mark the items api Built in `docs/architecture.md`.
- Add a PostgreSQL service container to CI so the integration tests run on every pull request.
- Turn `init_db.py` into a Kubernetes Job (to run before the api needs the table).
- Then: web pages (Flask templates).
- Watch for a `python:3.12-slim-trixie` base image with `apt` 3.0.4, then remove the temporary apt fix.
- Future idea (out of scope, not planned): quick-add from history, then barcode photo + Open Food Facts lookup, decided by trial feedback.
- Still owed: `db.py` explain-back, Entry 6 explain-back, Trivy upgrade after cooldown.

## Entry 11 — 2026-11-11 — Trivy gate catches zlib CVEs; patched image built, shipped and rolled out

**Problem**
- The PR for Entry 10 (image bump + journal only, no app or Dockerfile change) failed CI at **Scan the image - gate (Trivy)**.
- Trivy found 2 HIGH vulnerabilities in `zlib1g` `1:1.3.dfsg+really1.3.1-1+b1` (the compression library in the Debian base image):
  CVE-2026-76844 and CVE-2026-85091, both with status `fixed`.
- The image had not changed. Trivy's vulnerability database had: new CVEs were published for a package already in the image.

**Decision**
- Patch, do not ignore. The gate fails only on *fixable* HIGH/CRITICAL, and a fix existed, so ignoring it would weaken the gate.
- Checked the Debian security tracker (zlib source package): both CVEs fixed for trixie in `1:1.3.dfsg+really1.3.1-1+deb13u1` (DSA-6613-1).
- Trivy's title for CVE-2026-76844 said "webpack-dev-middleware". The tracker, package name and fixed version all point to zlib, so I trusted those.
- Did not switch the base image: the newest `python:3.12-slim-trixie` was 2 days old (inside the release cooldown) and not confirmed to contain the fix.
- Same pattern as the `apt` fix: upgrade only that package, pinned to the exact fixed version, with a comment saying when to remove it.

**Implementation**
- `api/Dockerfile`: the temporary security step now upgrades `zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1` next to `apt` and `libapt-pkg7.0`,
  with one comment line per fix (CVE, fixed version, DSA).
- Built locally as `freshtrack-api:zlib-test`; `dpkg -s zlib1g` showed `Version: 1:1.3.dfsg+really1.3.1-1+deb13u1`.
- Commit `8850dab` on `deploy/items-api-image`; PR #15 squash-merged as `de3370c`.
- `main` CI shipped `samayohub/freshtrack-api:de3370cedcf6a3f67e6ace5cadfb5043f7a6bc65`,
  digest `sha256:68b67bd36071d0ab6b9f572d90ac8d0514035ec722af2108cf1c47b4208570a6`.
- Branch `deploy/zlib-patched-image`: replaced the image line (line 32) in `deploy/k8s/api-deployment.yaml`, `kubectl apply`. PR #16 merged as `f06e39f`.

**Verification**
- Gate before: `/image.tar (debian 13.7)` 2 HIGH (zlib), `exit code 1`. Gate after: 0, passed. (Screenshots of both.)
- The full report still lists 47 HIGH, all without a released fix; the gate ignores unfixed ones by design and the report keeps them visible.
- Digest confirmed in two places: the CI `ship` log and Docker Hub (`docker buildx imagetools inspect`).
- `digest-mismatch: error` in the `ship` log is a setting (fail if the artifact changed between jobs); the downloaded artifact matched its expected digest.
- Cluster: `kubectl get deploy api -o wide` shows the `de3370c…@sha256:68b67bd3…` image, 1/1 available. New ReplicaSet `api-98b46599` has 1 Pod Ready
  (`api-98b46599-rns65`); the previous one, `api-657b677b4c` (`627d2a6…`), is at 0. `kubectl rollout history` shows revision 8; revision 7 is the old image.

**Troubleshooting**
1. *Gate failed on a PR with no image change:* new CVEs, not new code. Fixed by patching zlib (above).
2. *Server-side dry run failed: `dial tcp 127.0.0.1:8080: connection refused`.* kubectl falls back to localhost:8080 when no context is set.
   `minikube profile list` showed `freshtrack` `Stopped`, and `kubectl config current-context` said `current-context is not set`. Fixed with `minikube start -p freshtrack`.
3. *Forgot the before screenshot.* The old image is still on record: `kubectl get rs -n freshtrack -l app.kubernetes.io/name=api -o wide`
   lists every ReplicaSet with its image (old ones at 0 Pods), and `kubectl rollout history deployment/api -n freshtrack --revision=7` shows the old image.

**Lesson**
- An image that passed yesterday can fail today without any change: the list of known vulnerabilities grows. That is why the gate runs on every build and why weekly re-scans matter.
- A security gate is only useful if I fix what it finds. Patching one package to a pinned fixed version is a small, reversible change; an ignore list hides the problem.
- I check the distribution's own security tracker before trusting a scanner's title, because scanner data can be mislabelled.
- Kubernetes keeps old ReplicaSets at 0 Pods. They are the history `rollout undo` uses, and evidence of what ran before.
- Next time: open `kubectl get pods --watch` and `kubectl get rs --watch` before `kubectl apply`, to see the new Pod become Ready before the old one is removed.

**Next step**
- Add a PostgreSQL service container to CI so the integration tests run on every pull request.
- Turn `init_db.py` into a Kubernetes Job.
- Then: web pages (Flask templates).
- Remove the temporary `apt` and `zlib` patches when a base image (past the cooldown) contains both fixes.
- Upgrade Trivy (0.75.0 → 0.76.x) in its own PR after the cooldown.
- Still owed: `db.py` explain-back, Entry 6 explain-back.

## Entry 12 — 2026-11-11 — CI runs the integration tests against a real PostgreSQL

**Problem**
- CI only ran the unit tests, which replace the database with fakes. The 11 integration tests (real PostgreSQL) were skipped:
  the last `main` run before this change ended with `50 passed, 11 skipped`.
- They skip on purpose when `TEST_DATABASE_URL` is not set (`skipif` in `api/tests/test_db_integration.py`). They only ran on my laptop, when I remembered.
- So CI could stay green with broken SQL: wrong sorting, a missing CHECK rule, or an `init_db.py` that fails on a second run.

**Decision**
- Add a **service container** to the `checks` job: GitHub Actions starts a throwaway PostgreSQL next to the job and removes it afterwards.
- Same image as the cluster: `postgres:18.6-trixie@sha256:3a4264520e121176619f54ff867d12774bc81e95e7b84db58d63bccdb6144b81`
  (`deploy/k8s/postgres-statefulset.yaml`). Docker Hub's `18.6-trixie` tag had moved to a newer build (2026-11-06, inside the cooldown);
  CI and the cluster will be updated together later.
- A `pg_isready` health check, so the tests start only when the database is ready (no random failures).
- The password `test` is written in the workflow: the database is empty, lives for one run on a disposable runner, and never holds real data.

**Implementation**
- Branch `ci/postgres-service`, `.github/workflows/ci.yml`:
  - `services: postgres:` with the pinned image, `POSTGRES_PASSWORD` / `POSTGRES_DB`, port `5432:5432`,
    and `--health-cmd pg_isready --health-interval 5s --health-timeout 5s --health-retries 10`.
  - Test step renamed "Tests (unit + integration)" and given `TEST_DATABASE_URL: postgresql://postgres:test@localhost:5432/freshtrack_test`.
- README line 28 updated: the integration tests now run in CI (it said "not run in CI yet").
- Commits `51a1eb5` and `2c4cc95`; PR #18 squash-merged as `9b86685`.

**Verification**
- Before pushing: the YAML parsed, and the parsed `checks` job had `services` next to `steps`, with the image, env, ports, options and test step as intended.
- Branch run `42963082306`: `docker pull postgres:18.6-trixie@sha256:3a426452…`, `postgres service is healthy.`,
  11 × `test_db_integration.py::… PASSED`, `61 passed`, 0 `SKIPPED`.
- PR #18 checks: `checks` pass, SonarCloud pass, `ship` skipped (ships only from `main`).
- `main` run `42964848904`: `postgres service is healthy.`, `61 passed`, `checks` and `ship` success.
  Shipped `9b86685…@sha256:7555657c…`; same app code as the `de3370c` image on Minikube, so no redeploy needed.
- (Screenshots: the test step with `61 passed`, and "Initialize containers" with `postgres service is healthy.`)

**Troubleshooting**
1. *Comment indentation:* the first comment line above `services:` was at column 0 while the next was indented. YAML ignores comments, so nothing broke.
   After the fix commit both lines are at column 0, still to the left of `services:`. Cosmetic; to indent by 4 spaces the next time I edit `ci.yml`.
2. *No PR at first:* pushing the branch ran CI, but the PR still had to be opened with `gh pr create`.

**Lesson**
- Fake-database tests prove my Python logic; only a real database proves my SQL, constraints and sorting. CI needs both.
- A service container gives each CI run its own fresh database, so tests never depend on leftovers from an earlier run.
- A health check turns "wait and hope" into "wait until ready". Without it, tests can fail randomly because the database is still starting.
- Testing against the same pinned image as the cluster means "it passed in CI" says something about what runs in Minikube.

**Next step**
- Turn `init_db.py` into a Kubernetes Job, so the `items` table is created automatically instead of with `kubectl exec`.
- Then: web pages (Flask templates).
- Update the PostgreSQL digest in CI and the StatefulSet together, after the cooldown.
- Remove the temporary `apt` and `zlib` patches when a base image (past the cooldown) contains both fixes.
- Upgrade Trivy (0.75.0 → 0.76.x) in its own PR after the cooldown.
- Still owed: `db.py` explain-back, Entry 6 explain-back.

## Entry 13 — 2026-11-11 — The items table is created by a Kubernetes Job

**Problem**
- In Entry 10 the `items` table was created by hand: `kubectl exec -n freshtrack deploy/api -- python init_db.py`.
- That depends on someone remembering. On a fresh cluster (or the AWS trial) the api would start, `/ready` would pass
  (it checks the connection, not the table), and `/items` would return `503` until someone ran the command.

**Decision**
- A Kubernetes **Job**: it runs a Pod until the task succeeds once, then stops. A Deployment would keep restarting a finished script.
- Same image and same Secret as the api Deployment: the image already contains `init_db.py`, so no new image and no new secret.
- `init_db.py` exits `0` on success and `1` on failure, which is exactly what the Job uses to decide Complete or retry.
- Safe to run again: `api/schema.sql` uses `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`, with no `DROP`;
  CI checks this with `test_schema_can_be_applied_twice`.
- Settings: `backoffLimit: 3` (retries), `activeDeadlineSeconds: 120` (overall time limit), `ttlSecondsAfterFinished: 3600`
  (delete the finished Job after one hour; a Job's Pod template cannot be changed, so it must be gone before it is applied again),
  `restartPolicy: Never` (each retry is a new Pod, and a failed Pod keeps its logs).
- Same hardening as the api: non-root UID 10001, no privilege escalation, all capabilities dropped, seccomp `RuntimeDefault`,
  no ServiceAccount token, CPU / memory / ephemeral-storage requests and limits. No ports or probes: nothing connects to it.

**Implementation**
- `deploy/k8s/init-db-job.yaml` on branch `deploy/init-db-job`; `command: ["python", "init_db.py"]` replaces the image's gunicorn command
  (the image's working directory is `/app`, where the script is).
- Image `samayohub/freshtrack-api:de3370c…@sha256:68b67bd3…`, `DATABASE_URL` from Secret `postgres-credentials`.
- PR #20 squash-merged as `849db43`.

**Verification**
- Before: `kubectl get jobs -n freshtrack` → `No resources found in freshtrack namespace.`
- File check: YAML parsed as `batch/v1 Job`; image and `env` identical to the api Deployment;
  `kubectl apply --dry-run=server` → `job.batch/init-db created (server dry run)`.
- Watch: Pod `init-db-lgx2j` went `Pending → ContainerCreating → Running (1/1) → Completed (0/1)`, `RESTARTS 0`.
- `kubectl get jobs` → `init-db  Complete  1/1  15s` (started `18:45:47Z`, completed `18:46:02Z`).
- `kubectl logs -n freshtrack job/init-db` → `INFO Schema is ready`.
- Data check (read-only `SELECT`): the 2 items from 2026-11-07 (juice, milk) still there, both `active`.

**Troubleshooting**
1. *Branch named like a file:* the branch was created as `deploy/k8s/init-db-job.yml`. Renamed before pushing with
   `git branch -m deploy/init-db-job` (safe because it was only local).
2. *Wrong prediction:* I expected the Job to remove the two items, because they were added by hand earlier. They stayed:
   the table and rows live in PostgreSQL on its PersistentVolume, and the script only creates the table if it is missing.

**Lesson**
- A Job runs a task to completion and stops; `Completed 0/1` is success, not a broken Pod.
- The exit code is the contract between my script and Kubernetes: 0 means done, anything else means retry.
- Two different protections: the PersistentVolume keeps data when Pods disappear; idempotent SQL (`IF NOT EXISTS`, no `DROP`)
  keeps data when a setup task runs again. A volume does not protect data from a bad command.
- A Job's Pod template is immutable, so `ttlSecondsAfterFinished` (or deleting the old Job) is needed before running it again.

**Next step**
- Web pages (Flask templates): add an item, see the list soonest first, mark used or discarded. The web app calls the api, never the database.
- Later: run `init-db` automatically before the api on each deploy (a Helm hook, or an Argo CD sync hook).
- Update the PostgreSQL digest in CI and the StatefulSet together, after the cooldown.
- Remove the temporary `apt` and `zlib` patches when a base image (past the cooldown) contains both fixes.
- Upgrade Trivy (0.75.0 → 0.76.x) in its own PR after the cooldown.
- Still owed: `db.py` explain-back, Entry 6 explain-back.
