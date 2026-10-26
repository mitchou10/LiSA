# Vault Secrets — LiSA

LiSA uses [Vault Secrets Operator (VSO)](https://developer.hashicorp.com/vault/docs/platforms/k8s/vso)
to materialize Kubernetes `Secret` resources from Vault KV-v2 paths. The Helm
chart (`deploy/helm/lisa`) declares `VaultStaticSecret` objects in
`values/common-values.yaml` that reference the paths below.

All secrets live under the Vault KV-v2 mount named after `global.project`
(default: `exploration`), at the path `<env>/lisa/<name>` where `<env>` is
`global.vault.env` (default: `dev`).

> **Example path**: `exploration/dev/lisa/s3`

## Secrets to create in Vault

### 1. `lisa-s3` — S3 / RustFS object storage

Used by: **backend**, **anonymize**, **image-classification**, **parser**.

The backend reads `S3_*` keys, the anonymize service reads `AWS_*` keys, and
the parser / image-classification services read `S3_*` keys. All four must be
present in the same secret so every consumer gets what it needs.

| Key | Example | Consumed by |
|---|---|---|
| `S3_ENDPOINT_URL` | `http://lisa-rustfs:9000` | backend, parser, image-classification |
| `S3_ACCESS_KEY` | `rustfsadmin` | backend, parser, image-classification |
| `S3_SECRET_KEY` | `rustfsadmin` | backend, parser, image-classification |
| `S3_BUCKET` | `lisa-files` | backend, parser, image-classification |
| `S3_REGION` | `us-east-1` | backend, parser, image-classification |
| `AWS_S3_ENDPOINT_URL` | `http://lisa-rustfs:9000` | anonymize |
| `AWS_ACCESS_KEY_ID` | `rustfsadmin` | anonymize |
| `AWS_SECRET_ACCESS_KEY` | `rustfsadmin` | anonymize |
| `AWS_S3_BUCKET` | `lisa-files` | anonymize |

> `S3_REGION` / `AWS_S3_REGION` are set as plain `env` in the chart
> (`us-east-1`), not from the secret — but having them in Vault too is fine.

**Vault path**: `<project>/<env>/lisa/s3`

---

### 2. `lisa-keycloak` — Keycloak OIDC (BFF)

Used by: **backend** only.

The backend is a confidential OIDC client: it holds the client secret and
runs the Authorization Code + PKCE flow server-side. Tokens never reach the
browser.

| Key | Example | Notes |
|---|---|---|
| `KEYCLOAK_SERVER_URL` | `https://keycloak.example.org` | Browser-facing URL (used for redirects) |
| `KEYCLOAK_INTERNAL_URL` | `http://keycloak.default.svc:8080` | In-cluster URL for JWKS / token exchange (optional, falls back to `KEYCLOAK_SERVER_URL`) |
| `KEYCLOAK_CLIENT_SECRET` | `dev-only-secret-not-for-prod` | Confidential client secret |

> `KEYCLOAK_REALM` (`lisa`), `KEYCLOAK_CLIENT_ID` (`lisa-frontend`) and
> `KEYCLOAK_ADMIN_ROLE` (`admin`) are set as plain `env` in the chart.

**Vault path**: `<project>/<env>/lisa/keycloak`

---

### 3. `lisa-redis` — Redis (sessions + Celery broker)

Used by: **backend**, **all 7 services**, **redis subchart** (auth), **KEDA** (trigger auth).

The VSO `transformation` in `common-values.yaml` automatically derives
`REDIS_URL` from `REDIS_PASSWORD`, so you only need to store the password.

| Key | Example | Notes |
|---|---|---|
| `REDIS_PASSWORD` | `change-me` | Required — used by the redis subchart (`auth.existingSecret`), KEDA (`TriggerAuthentication`), and the computed `REDIS_URL` |

> `REDIS_URL` is **auto-generated** by the VSO transformation template:
> `redis://:<REDIS_PASSWORD>@lisa-redis:6379/0` — do **not** store it manually.

**Vault path**: `<project>/<env>/lisa/redis`

---

### 4. `lisa-db-superuser` — PostgreSQL superuser (CNPG)

Used by: **CNPG cluster** (`superuserSecret`).

CNPG requires a `kubernetes.io/basic-auth` secret (the VSO `destination.type`
in the chart handles this). Store exactly two keys:

| Key | Example | Notes |
|---|---|---|
| `username` | `postgres` | CNPG superuser |
| `password` | `change-me-super` | CNPG superuser password |

**Vault path**: `<project>/<env>/lisa/db-superuser`

---

### 5. `lisa-db-appuser` — PostgreSQL application user (CNPG initdb)

Used by: **CNPG cluster** (`initdb.secret`).

Same `kubernetes.io/basic-auth` format. This is the user the backend connects
as (via `DATABASE_URL` derived in `lisa-db-infos`).

| Key | Example | Notes |
|---|---|---|
| `username` | `lisa` | CNPG app/owner user |
| `password` | `change-me-app` | CNPG app/owner password |

**Vault path**: `<project>/<env>/lisa/db-appuser`

---

### 6. `lisa-db-infos` — Computed DATABASE_URL for the backend

Used by: **backend**, **migration job**.

The VSO `transformation` in `common-values.yaml` reads `username` and
`password` from this secret and builds `DATABASE_URL` automatically:

```
postgresql+asyncpg://<username>:<password>@lisa-pg-cluster-rw:5432/lisa
```

Store the same `username` / `password` as `lisa-db-appuser` (they must match):

| Key | Example | Notes |
|---|---|---|
| `username` | `lisa` | Must match `lisa-db-appuser` |
| `password` | `change-me-app` | Must match `lisa-db-appuser` |

> `DATABASE_URL` is **auto-generated** — do **not** store it manually.

**Vault path**: `<project>/<env>/lisa/db-infos`

---

### 7. `lisa-db-backups` — S3 backups for CNPG (Barman + WAL archive)

Used by: **CNPG cluster** (`backups.secret`, `recovery.secret`).

CNPG uses Barman to push backups and WAL archives to S3. The keys must match
CNPG's expected format:

| Key | Example | Notes |
|---|---|---|
| `ACCESS_KEY_ID` | `SCWxxxxxxxx` | S3 access key (Scaleway / RustFS / etc.) |
| `SECRET_ACCESS_KEY` | `change-me` | S3 secret key |
| `AWS_REGION` | `fr-par` | S3 region (optional, some providers ignore it) |

> The backup endpoint (`endpointURL: https://s3.fr-par.scw.cloud`) and
> `provider: s3` are hardcoded in `common-values.yaml` — override them in the
> environment values file if using a different S3 provider.

**Vault path**: `<project>/<env>/lisa/db-backups`

---

## Summary table

| Secret name | Vault path | Keys | Type |
|---|---|---|---|
| `lisa-s3` | `<project>/<env>/lisa/s3` | `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`, `S3_REGION`, `AWS_S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET` | Opaque |
| `lisa-keycloak` | `<project>/<env>/lisa/keycloak` | `KEYCLOAK_SERVER_URL`, `KEYCLOAK_INTERNAL_URL`, `KEYCLOAK_CLIENT_SECRET` | Opaque |
| `lisa-redis` | `<project>/<env>/lisa/redis` | `REDIS_PASSWORD` | Opaque (+ VSO computes `REDIS_URL`) |
| `lisa-db-superuser` | `<project>/<env>/lisa/db-superuser` | `username`, `password` | `kubernetes.io/basic-auth` |
| `lisa-db-appuser` | `<project>/<env>/lisa/db-appuser` | `username`, `password` | `kubernetes.io/basic-auth` |
| `lisa-db-infos` | `<project>/<env>/lisa/db-infos` | `username`, `password` | Opaque (+ VSO computes `DATABASE_URL`) |
| `lisa-db-backups` | `<project>/<env>/lisa/db-backups` | `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY`, `AWS_REGION` | Opaque |

## Quick start (Vault CLI)

```bash
# Adjust PROJECT, ENV and values to your environment.
PROJECT="exploration"
ENV="dev"
KV="${PROJECT}"

# S3 / RustFS
vault kv put "${KV}/${ENV}/lisa/s3" \
  S3_ENDPOINT_URL="http://lisa-rustfs:9000" \
  S3_ACCESS_KEY="rustfsadmin" \
  S3_SECRET_KEY="rustfsadmin" \
  S3_BUCKET="lisa-files" \
  S3_REGION="us-east-1" \
  AWS_S3_ENDPOINT_URL="http://lisa-rustfs:9000" \
  AWS_ACCESS_KEY_ID="rustfsadmin" \
  AWS_SECRET_ACCESS_KEY="rustfsadmin" \
  AWS_S3_BUCKET="lisa-files"

# Keycloak
vault kv put "${KV}/${ENV}/lisa/keycloak" \
  KEYCLOAK_SERVER_URL="https://keycloak.example.org" \
  KEYCLOAK_INTERNAL_URL="http://keycloak.default.svc:8080" \
  KEYCLOAK_CLIENT_SECRET="dev-only-secret-not-for-prod"

# Redis
vault kv put "${KV}/${ENV}/lisa/redis" \
  REDIS_PASSWORD="change-me"

# DB superuser (CNPG)
vault kv put "${KV}/${ENV}/lisa/db-superuser" \
  username="postgres" \
  password="change-me-super"

# DB app user (CNPG initdb + backend connection)
vault kv put "${KV}/${ENV}/lisa/db-appuser" \
  username="lisa" \
  password="change-me-app"

# DB infos (must match db-appuser — VSO derives DATABASE_URL from these)
vault kv put "${KV}/${ENV}/lisa/db-infos" \
  username="lisa" \
  password="change-me-app"

# DB backups (S3 for CNPG Barman)
vault kv put "${KV}/${ENV}/lisa/db-backups" \
  ACCESS_KEY_ID="SCWxxxxxxxx" \
  SECRET_ACCESS_KEY="change-me" \
  AWS_REGION="fr-par"
```

## Notes

- **`lisa-db-appuser` and `lisa-db-infos` must have the same `username`/`password`**:
  CNPG creates the database owner from `db-appuser`, and the backend connects
  using `DATABASE_URL` derived from `db-infos`. If they diverge, the backend
  cannot authenticate.
- **`REDIS_URL` and `DATABASE_URL` are never stored in Vault** — they are
  computed by VSO transformation templates at materialization time.
- **`lisa-db-superuser` and `lisa-db-appuser` are `kubernetes.io/basic-auth`**
  secrets (not Opaque): CNPG requires this exact type, and the chart's VSO
  `destination.type` handles the conversion.
- The `registry-pull-secret` (for Harbor image pulls) is **not** a Vault
  secret — it is created manually or via the chart's `imagePullSecrets` mechanism.
