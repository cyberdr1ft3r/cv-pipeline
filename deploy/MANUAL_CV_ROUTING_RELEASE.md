# Manual CV routing — controlled release

Target: issue #12. This change uses the **existing** manual-upload endpoint, staging
scanner, extractor, CV_Theque layout, and PostgreSQL candidate registration.

## Source of truth and deployment caution

The branch is based on commit `9d2ba6137d4a741f595a710f6e3957529a2f984a`
(the head of the hotfix/security branch, matching the VPS release directory suffix).
That suffix is **not proof** that the running image contains every server-only hotfix.
Do not deploy until the running image digests, server-side Compose overlays and any
relevant source/config changes have been reconciled with this branch.

Preserve these server-side overlays and settings as applicable:

- `compose.prod.yml`
- `deploy/compose.api-hotfix.yml`
- `deploy/compose.ui-hotfix.yml`
- `deploy/compose.hermes-lab.yml`
- `deploy/.env.prod` and `deploy/hermes/.env` (**secrets: never commit or paste**)

Hermes stays a disabled, opt-in shadow experiment. Keep the watcher stopped during
development, code review, and deployment preparation. Do not run `docker compose down -v`,
remove the `cv-pipeline_cv_storage` volume, reinitialize Postgres, or replace the
current release with an image built from `cv-upload-fixes` alone.

## Routing contract

- The manual uploader requires **both** existing canonical profile and seniority.
- Each queued CV can override batch defaults and folder-derived prefill.
- API writes atomically without overwriting to:
  `staging/{profile}/{seniority}/{filename}`.
- A recognized two-level staging route is authoritative for *both* classification
  labels, regardless of extracted years/title/internship classification. This applies
  to explicitly routed Google Drive imports too.
- Flat and profile-only staged files retain existing automatic seniority inference.
- Extraction and validation are unchanged; original is retained in:
  `CV_Theque/{profile}/{seniority}/originals/`, JSON in `extracted/`, then candidate
  metadata is upserted in PostgreSQL and staging original moved to `processed/`.
- No new worker, database table, upload endpoint, or Hermes production integration.

## Profile catalog hotfix

On 2026-09-21 the VPS persistent volume `cv-pipeline_cv_storage` was given six
previously missing top-level profile folders:
`Frontend`, `Mobile`, `Cloud`, `Cybersecurity`, `Data`, `ERP`.
The active DB reference table was verified to contain all six.
This catalog is **volume data**, not part of an application image: preserve it in
storage backups and provision the same folders when initializing a new CV storage
volume. Do not delete/recreate existing folders.

`Solutions_Architect` was present in the live folder list but absent from the active
`ref.profiles` rows observed on the VPS; reconcile this separately before relying
on its reference ID for candidate filtering.

## Pre-deploy gates

1. Compare current container image digests, release-file hashes, effective Compose
   configuration (redacted; never share env secrets), volume mounts, and watcher
   state against the intended build. Reconcile any drift.
2. Review the focused PR and inspect its diff against the current live hotfix
   source. Confirm no regression to atomic staging writes or job access checks.
3. Run API/watchers tests and a production-equivalent frontend TypeScript/build
   check in CI or an isolated build environment. Record the exact commit/image tags.
4. Back up relevant config, DB and CV volume with the organization's approved
   retention/privacy policy and test restoration of the rollback target.
5. Validate merged Compose config before a controlled deployment. Do not start
   the watcher to test the UI or staging upload alone.
6. With watcher deliberately enabled only in an authorized maintenance window,
   test two consented/synthetic CVs with different routing: `DevOps/Junior`
   and `FullStack/Senior`; assert files/JSON/DB agree even if source CV says
   otherwise. Verify Google Drive auto behavior, duplicate filenames and retries.
7. If a check fails, restore the previous immutable API/frontend images and
   Compose config without removing persistent volumes. Leave the watcher in
   its pre-deployment state.

Do not promote this PR based solely on GitHub tests: VPS-only hotfix drift must
still be checked before any live deploy.
