# lisa

## Reference and local adaptations

The chart follows the scaffold in
[this-is-tobi/helm-charts/template](https://github.com/this-is-tobi/helm-charts/tree/main/template)
(reference inspected at commit
[`73fafdaf`](https://github.com/this-is-tobi/helm-charts/tree/73fafdaf3fa61ea0a1d7dd11081fc73b145027f7/template)).
It keeps the per-component directories, shared naming and pod helpers, `global`
settings, and chart-level jobs, CronJobs, and extra objects.

The following are **LiSA-specific extensions**, not features supplied by that
upstream scaffold:

- [`componentDefaults`](./values.yaml) holds defaults shared by the nine LiSA
  components.
- [`templates/_components.tpl`](./templates/_components.tpl) defines the resource
  macros and resolves each component's effective values.
- Files in each component directory are small includes of those macros.
- `helper.componentNames` is the shared component list used by validation and
  release notes.

Upstream has full resource templates per component and a helm-docs documentation
template. This guide is maintained manually; the current LiSA CI leaves
`LINT_DOCS` disabled. When adopting an upstream fix, apply shared resource logic
once in the local macros, rather than copying full templates into all nine
component directories. Update this guide when changing the local interface.

## Requirements and installation

- Helm 3 and Kubernetes 1.25 or newer.
- An Ingress controller if Ingress is enabled.
- Gateway API CRDs and a compatible controller if Gateway API resources are used.
- Prometheus Operator CRDs if ServiceMonitors are enabled.

From the repository root, with an environment-specific values file:

```sh
# Restore the dependencies pinned by Chart.lock if they are not already present.
helm dependency build deploy/helm/lisa
helm lint deploy/helm/lisa -f values-production.yaml
helm template lisa deploy/helm/lisa -f values-production.yaml
helm upgrade --install lisa deploy/helm/lisa \
  --namespace lisa --create-namespace -f values-production.yaml
```

Use `helm dependency build`, not `helm dependency update`, to retain the locked
dependency versions. Redis, CNPG (PostgreSQL), and RustFS are bundled
dependencies; Redis and CNPG are enabled by default.

The default credentials and `.local` URLs are for development, **not production**.
Replace `secrets.serviceToken`, `secrets.keycloakClientSecret`, database/cache/S3
credentials, application URLs, and identity-provider settings as appropriate.
Keep real secrets out of version control.

The bundled services currently use fixed names (`lisa-redis`, `lisa-pg-cluster`,
`lisa-rustfs`) referenced by the component environment variables. When replacing
them with external services or changing those names, also update every affected
component's connection settings. Disabling a dependency alone does not configure
an external connection.

## Values: change only what differs

The complete option shapes and examples are in [`values.yaml`](./values.yaml).
The component keys are:

`backend`, `frontend`, `anonymize`, `safety`, `ner`, `relation`, `classification`,
`imageClassification`, and `parser`.

### Shared settings versus component defaults

| Section | Purpose |
| --- | --- |
| `global` | Shared environment variables, image registry, image pull secrets, and chart-level routing. These settings are consumed by the relevant helpers and templates; they are not a generic defaults map. |
| `componentDefaults` | Default workload, probes, resources, security contexts, scheduling, service, routing, RBAC, and observability options for the nine components. |
| `<component>` | Only the settings that differ from `componentDefaults`, including its image repository and application configuration. |
| `jobs`, `cronjobs` | Independent workload definitions; they do **not** inherit `componentDefaults`. |
| `extraObjects` | Additional manifests keyed by an arbitrary unique name, with Helm templating supported. |
| `redis`, `cnpg`, `rustfs` | Dependency-specific settings; they do **not** inherit `componentDefaults`. |

There are two stages of value resolution:

1. Helm merges the chart values with the supplied `-f` files and `--set` flags.
   Later files and command-line overrides take precedence.
2. Each LiSA component is resolved by merging its resulting block over
   `componentDefaults`. An explicit component value takes precedence over a
   default, even if that component value came from the chart's own
   [`values.yaml`](./values.yaml), not the environment file.

Nested maps merge recursively. Lists replace inherited lists; they do not append.
An empty map does not clear an inherited map. Do not rely on `null` to remove a
default: Helm's own coalescing and the local merge are separate stages. Use
explicit supported switches such as `service.enabled: false`.

**The complete `probes` block is the exception:** if a component defines it, it
replaces the shared block rather than merging with it. This prevents combining
an `exec` handler with an `httpGet` handler. When overriding probes on a worker,
provide all probes you want to retain. Backend and frontend already define their
own HTTP probes in the chart values.

For example, put only the differences in your environment file:

```yaml
global:
  env:
    LOG_LEVEL: "INFO"

componentDefaults:
  nodeSelector:
    workload: lisa
  image:
    pullPolicy: Always

backend:
  replicaCount: 2
  resources:
    limits:
      memory: "2Gi"

ner:
  resources:
    requests:
      cpu: "1"
  envCm:
    NER_THRESHOLD: "0.7"
```

Here, the backend retains its existing CPU limit and requests. The NER component
retains its other environment entries and resource settings. The common node
selector and image pull policy apply to all nine components.

For a single override:

```sh
helm template lisa deploy/helm/lisa --set backend.replicaCount=2
```

`global.env` and `global.envFrom` are placed before the component's entries.
`global.envCm` and `global.envSecret` are rendered into each component's ConfigMap
and Secret; avoid defining the same key globally and locally in these maps.
Use `global.envFrom` or the component's `envFrom` to reference existing ConfigMaps
and Secrets.

### Optional resources

Enable component routing and its Service together. Keep the Kubernetes API field
names in routing values: Ingress paths use `backend`, while HTTPRoute and GRPCRoute
rules use `backendRefs`, regardless of the component name.

Use the separate `global.ingress` or `global.httpRoute` settings when several
services share one entry point; these require explicit backend service names.
`gateway.create` controls creation of a Gateway, not installation of its
controller or CRDs.

The top-level `jobs`, `cronjobs`, and `extraObjects` maps are empty by default.
See their commented examples in [`values.yaml`](./values.yaml). Jobs and CronJobs
need their own image and security settings; they do not inherit worker defaults.

`enabled: false` disables LiSA's own resources. To disable the whole release's
resources, also set `redis.enabled`, `cnpg.enabled`, and `rustfs.enabled` to
`false`, since the dependencies have independent switches.

## Maintaining or adding a component

For an existing component, change only its values block unless the resource
logic itself needs changing. Update a shared default only if it should apply to
all components that do not override it.

To add a component:

1. Add its camelCase key and specific values to [`values.yaml`](./values.yaml),
   including `image.repository`.
2. Add the key to `helper.componentNames` in
   [`templates/_components.tpl`](./templates/_components.tpl).
3. Copy an existing component template directory and replace the `"name"`
   argument in **every** include with the new key. Retain the ConfigMap and Secret
   templates, which the pod helper also uses for rollout checksums.
4. Add the application-specific image, queue, environment variables, and any
   registration required by the application. Helm does not create application
   code or register the service automatically.
5. Update this guide's component list, then lint and inspect the rendered
   manifests with the component's optional features enabled.

For example, the new component's deployment template would contain:

```gotemplateinclude "helper.component.deployment" (dict "root" . "name" "newComponent")
```

For changes to shared templates, check the default render as well as Deployment,
StatefulSet, DaemonSet, routing, and relevant optional resources. `helm lint` and
`helm template` validate local rendering; they do not replace validation against
a Kubernetes cluster with the required CRDs installed.

## Complete values reference

### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| commonLabels | object | `{}` | Add labels to all the deployed resources |
| cronjobs | object | `{}` | Map of CronJobs to create (e.g. periodic archiving, cleanup, reports...). Each key is used as the cronjob name and as its `app.kubernetes.io/component` label. Every entry accepts the same fields as a `jobs` entry (see above, minus `hook`) plus the scheduling fields documented in the commented example below. |
| enabled | bool | `true` | Master switch for the whole chart. When `false`, every template renders nothing - use this to keep a release/namespace registered with a deployment system (e.g. an ArgoCD Application that always gets generated for every app/env combination) without actually deploying any resource into it. Note this does NOT cover subchart dependencies added via `Chart.yaml` (e.g. a bundled database/cache) - those still need their own `enabled: false` alongside this one. |
| extraObjects | object | `{}` | Map of extra specs to dynamically add to this chart. Each key is a unique, arbitrary name for the object (only used so `-f` values files/overrides can add, override or remove a single entry by key instead of the whole list - lists don't merge across values files in Helm). |
| fullnameOverride | string | `""` | String to fully override the default application name. |
| jobs | object | `{}` |  |
| nameOverride | string | `""` | Provide a name in place of the default application name. |
| s3 | object | `{"bucket":"lisa-files"}` | S3 bucket the files, screenshots and blurred images are stored in (on the bundled RustFS). |
| secrets | object | `{"keycloakClientSecret":"change-me-keycloak-secret","postgresPassword":"change-me-postgres","postgresUsername":"lisa","serviceToken":"change-me-service-token"}` | Secrets shared by several components (rendered into their `envSecret`). These defaults are for local testing only: override them, or reference a Secret you manage through `envFrom`. |

### Global

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| global.env | object | `{}` | Map or array of environment variables to inject into all containers (`valueFrom` supported). |
| global.envCm | object | `{}` | Map of environment variables to inject into a configmap loaded by all containers (`valueFrom` not supported). |
| global.envFrom | list | `[]` | List or map of `configMapRef`/`secretRef` entries to load into every container's `envFrom` (merged with each component's own `envFrom`, global entries first). |
| global.envSecret | object | `{}` | Map of environment variables to inject into a secret loaded by all containers (`valueFrom` not supported). |
| global.httpRoute.annotations | object | `{}` | Additional HTTPRoute annotations. |
| global.httpRoute.enabled | bool | `false` | Whether or not the chart-level HTTPRoute should be enabled. |
| global.httpRoute.hostnames | list | `[]` | Hostnames for the HTTPRoute to match. |
| global.httpRoute.labels | object | `{}` | Additional HTTPRoute labels. |
| global.httpRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the HTTPRoute to. |
| global.httpRoute.rules | list | `[]` | Routing rules for the HTTPRoute. Required when `enabled` is true, and every `backendRefs` entry must carry a `name`. |
| global.imagePullSecrets | list | `[]` | Image credentials applied to every component in addition to any component-specific `imagePullSecrets`. |
| global.imageRegistry | string | `""` | Global Docker image registry |
| global.ingress.annotations | object | `{}` | Additional ingress annotations. |
| global.ingress.className | string | `""` | Defines which ingress controller will implement the resource. |
| global.ingress.enabled | bool | `false` | Whether or not the chart-level ingress should be enabled. |
| global.ingress.hosts | list | `[]` | Hosts and paths served by the chart-level ingress. Each path's `backend.serviceName` is required (see above); `backend.portNumber` defaults to 80. |
| global.ingress.labels | object | `{}` | Additional ingress labels. |
| global.ingress.tls | list | `[]` | TLS configuration for the chart-level ingress. |

### Anonymize

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| anonymize.image | object | `{"repository":"mitchou10/lisa/anonymize"}` | Overrides on top of `componentDefaults` above - only what makes this component different needs to be listed here. |

#### EnvCm

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| anonymize.envCm.AWS_S3_BUCKET | string | `"{{ .Values.s3.bucket }}"` |  |
| anonymize.envCm.AWS_S3_ENDPOINT_URL | string | `"http://lisa-rustfs:9000"` |  |
| anonymize.envCm.AWS_S3_REGION | string | `"us-east-1"` |  |
| anonymize.envCm.CELERY_QUEUE | string | `"llm-guard-anonymize"` |  |
| anonymize.envCm.LISA_API_URL | string | `"http://{{ include \"helper.fullname\" . }}-backend:8000"` |  |
| anonymize.envCm.REDIS_URL | string | `"redis://:{{ .Values.redis.auth.password }}@lisa-redis:6379/0"` |  |

#### EnvSecret

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| anonymize.envSecret.AWS_ACCESS_KEY_ID | string | `"{{ .Values.rustfs.auth.accessKey }}"` |  |
| anonymize.envSecret.AWS_SECRET_ACCESS_KEY | string | `"{{ .Values.rustfs.auth.secretKey }}"` |  |
| anonymize.envSecret.LISA_SERVICE_TOKEN | string | `"{{ .Values.secrets.serviceToken }}"` |  |

### Backend

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.containerPort | int | `8000` |  |
| backend.image | object | `{"repository":"mitchou10/lisa/backend"}` | Overrides on top of `componentDefaults` above - only what makes this component different needs to be listed here. |

#### EnvCm

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.envCm.BACKEND_PUBLIC_URL | string | `"https://lisa.local/api"` |  |
| backend.envCm.CORS_ORIGINS | string | `"[\"https://lisa.local\"]"` |  |
| backend.envCm.DATABASE_URL | string | `"postgresql+asyncpg://{{ .Values.secrets.postgresUsername }}:{{ .Values.secrets.postgresPassword }}@lisa-pg-cluster-rw:5432/{{ .Values.cnpg.cluster.initdb.database }}"` |  |
| backend.envCm.FRONTEND_URL | string | `"https://lisa.local"` |  |
| backend.envCm.KEYCLOAK_ADMIN_ROLE | string | `"admin"` |  |
| backend.envCm.KEYCLOAK_CLIENT_ID | string | `"lisa-frontend"` |  |
| backend.envCm.KEYCLOAK_INTERNAL_URL | string | `"https://keycloak.local"` |  |
| backend.envCm.KEYCLOAK_REALM | string | `"lisa"` |  |
| backend.envCm.KEYCLOAK_SERVER_URL | string | `"https://keycloak.local"` |  |
| backend.envCm.REDIS_URL | string | `"redis://:{{ .Values.redis.auth.password }}@lisa-redis:6379/0"` |  |
| backend.envCm.S3_BUCKET | string | `"{{ .Values.s3.bucket }}"` |  |
| backend.envCm.S3_ENDPOINT_URL | string | `"http://lisa-rustfs:9000"` |  |
| backend.envCm.S3_REGION | string | `"us-east-1"` |  |
| backend.envCm.SESSION_COOKIE_SECURE | string | `"true"` |  |

#### EnvSecret

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.envSecret.KEYCLOAK_CLIENT_SECRET | string | `"{{ .Values.secrets.keycloakClientSecret }}"` |  |
| backend.envSecret.S3_ACCESS_KEY | string | `"{{ .Values.rustfs.auth.accessKey }}"` |  |
| backend.envSecret.S3_SECRET_KEY | string | `"{{ .Values.rustfs.auth.secretKey }}"` |  |
| backend.envSecret.SERVICE_TOKEN | string | `"{{ .Values.secrets.serviceToken }}"` |  |

#### Ingress

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.ingress.hosts[0].name | string | `"domain.local"` |  |
| backend.ingress.hosts[0].paths[0].backend.portNumber | string | `nil` |  |
| backend.ingress.hosts[0].paths[0].backend.serviceName | string | `""` |  |
| backend.ingress.hosts[0].paths[0].path | string | `"/health"` |  |
| backend.ingress.hosts[0].paths[0].pathType | string | `"Prefix"` |  |

#### PodSecurityContext

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.podSecurityContext.fsGroup | int | `1000` |  |
| backend.podSecurityContext.runAsGroup | int | `1000` |  |
| backend.podSecurityContext.runAsUser | int | `1000` |  |

#### Probes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.probes.livenessProbe.failureThreshold | int | `3` |  |
| backend.probes.livenessProbe.httpGet.path | string | `"/health"` |  |
| backend.probes.livenessProbe.httpGet.port | int | `8000` |  |
| backend.probes.livenessProbe.initialDelaySeconds | int | `30` |  |
| backend.probes.livenessProbe.periodSeconds | int | `30` |  |
| backend.probes.livenessProbe.successThreshold | int | `1` |  |
| backend.probes.livenessProbe.timeoutSeconds | int | `5` |  |
| backend.probes.readinessProbe.failureThreshold | int | `2` |  |
| backend.probes.readinessProbe.httpGet.path | string | `"/health"` |  |
| backend.probes.readinessProbe.httpGet.port | int | `8000` |  |
| backend.probes.readinessProbe.initialDelaySeconds | int | `10` |  |
| backend.probes.readinessProbe.periodSeconds | int | `10` |  |
| backend.probes.readinessProbe.successThreshold | int | `2` |  |
| backend.probes.readinessProbe.timeoutSeconds | int | `5` |  |
| backend.probes.startupProbe.failureThreshold | int | `10` |  |
| backend.probes.startupProbe.httpGet.path | string | `"/health"` |  |
| backend.probes.startupProbe.httpGet.port | int | `8000` |  |
| backend.probes.startupProbe.initialDelaySeconds | int | `0` |  |
| backend.probes.startupProbe.periodSeconds | int | `10` |  |
| backend.probes.startupProbe.successThreshold | int | `1` |  |
| backend.probes.startupProbe.timeoutSeconds | int | `5` |  |

#### Resources

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.resources.limits.cpu | string | `"1"` |  |
| backend.resources.limits.memory | string | `"1Gi"` |  |
| backend.resources.requests.cpu | string | `"100m"` |  |
| backend.resources.requests.memory | string | `"256Mi"` |  |

#### SecurityContext

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.securityContext.readOnlyRootFilesystem | bool | `true` |  |
| backend.securityContext.runAsGroup | int | `1000` |  |
| backend.securityContext.runAsUser | int | `1000` |  |

#### Service

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backend.service.enabled | bool | `true` |  |
| backend.service.port | int | `8000` |  |

### Classification

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| classification.image | object | `{"repository":"mitchou10/lisa/classification"}` | Overrides on top of `componentDefaults` above - only what makes this component different needs to be listed here. |

#### EnvCm

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| classification.envCm.CELERY_QUEUE | string | `"classification"` |  |
| classification.envCm.CLASSIFIER_BACKEND | string | `"gliner2"` |  |
| classification.envCm.CLASSIFIER_MODEL | string | `"fastino/gliner2.5-multi-v1"` |  |
| classification.envCm.LISA_API_URL | string | `"http://{{ include \"helper.fullname\" . }}-backend:8000"` |  |
| classification.envCm.REDIS_URL | string | `"redis://:{{ .Values.redis.auth.password }}@lisa-redis:6379/0"` |  |

#### EnvSecret

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| classification.envSecret.LISA_SERVICE_TOKEN | string | `"{{ .Values.secrets.serviceToken }}"` |  |

### Cnpg

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| cnpg.enabled | bool | `true` |  |
| cnpg.fullnameOverride | string | `"lisa-pg-cluster"` |  |
| cnpg.mode | string | `"standalone"` |  |
| cnpg.type | string | `"postgresql"` |  |

#### Cluster

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| cnpg.cluster.enableSuperuserAccess | bool | `true` |  |
| cnpg.cluster.imageName | string | `"ghcr.io/cloudnative-pg/postgresql:17.7"` |  |
| cnpg.cluster.initdb.database | string | `"lisa"` |  |
| cnpg.cluster.initdb.owner | string | `"lisa"` |  |
| cnpg.cluster.initdb.secret.name | string | `"lisa-db-appuser"` |  |
| cnpg.cluster.instances | int | `1` |  |
| cnpg.cluster.resources.limits.cpu | string | `"500m"` |  |
| cnpg.cluster.resources.limits.memory | string | `"1Gi"` |  |
| cnpg.cluster.resources.requests.cpu | string | `"250m"` |  |
| cnpg.cluster.resources.requests.memory | string | `"512Mi"` |  |
| cnpg.cluster.storage.size | string | `"3Gi"` |  |
| cnpg.cluster.superuserSecret | string | `"lisa-db-superuser"` |  |
| cnpg.cluster.walStorage.enabled | bool | `true` |  |
| cnpg.cluster.walStorage.size | string | `"2Gi"` |  |

#### Version

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| cnpg.version.postgresql | string | `"17"` |  |

### ComponentDefaults

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.affinity | object | `{}` | Affinity used for app pod. |
| componentDefaults.args | list | `[]` | Anonymize container command args. |
| componentDefaults.automountServiceAccountToken | bool | `false` | Mount the ServiceAccount token into the app pods. Defaults to false so a compromised container holds no API credentials; the API server does not need the token unless the app actually talks to the Kubernetes API. Applied at pod level so it holds even when `serviceAccount.name` points at an SA that automounts. |
| componentDefaults.command | list | `[]` | Anonymize container command. |
| componentDefaults.containerPort | string | `nil` | Anonymize container port number. Set to `null`/`0` (and disable `service`/probes) for components that don't listen on any port (e.g. a queue consumer). |
| componentDefaults.containerPortName | string | `"http"` | Anonymize container port name. |
| componentDefaults.deploymentType | string | `"Deployment"` | Workload kind to deploy the app as. One of "Deployment", "StatefulSet" or "DaemonSet" (validated at render time - an unknown value fails instead of producing a release with no workload). Use the top-level `jobs` / `cronjobs` maps for one-off or scheduled workloads. Some values only apply to certain kinds: `replicaCount`/`autoscaling` and `strategy` are Deployment-only (`autoscaling` also works on a StatefulSet), `volumeClaims`/`extraVolumeClaims` are StatefulSet-only, and `updateStrategy` covers StatefulSet and DaemonSet. |
| componentDefaults.dnsConfig | object | `{}` | Pod DNS configuration, merged with `dnsPolicy` by the kubelet. |
| componentDefaults.dnsPolicy | string | `""` (`ClusterFirstWithHostNet` when `hostNetwork` is true) | Pod DNS policy. Left empty, it defaults to `ClusterFirstWithHostNet` when `hostNetwork` is true (otherwise a hostNetwork pod silently stops resolving cluster DNS) and to the Kubernetes default `ClusterFirst` when it isn't. |
| componentDefaults.enableServiceLinks | bool | `false` | Inject the legacy `{SVC}_SERVICE_HOST`/`_PORT` environment variables for every Service in the namespace. Defaults to false: the variables are rarely used, leak the namespace's topology into every container, and can collide with the app's own configuration. Set to true only for an app that genuinely reads them. |
| componentDefaults.env | object | `{}` | Map or array of environment variables to inject into the app container (`valueFrom` supported). |
| componentDefaults.envCm | object | `{}` | Map of environment variables to inject into a configmap loaded by the app container (`valueFrom` not supported). |
| componentDefaults.envFrom | list | `[]` | Anonymize container env variables loaded from configmap or secret reference. List or map (merged with `global.envFrom` above, global entries first); see `global.envFrom` for both forms. |
| componentDefaults.envSecret | object | `{}` | Map of environment variables to inject into a secret loaded by the app container (`valueFrom` not supported). Values placed here are stored in plain text in the values file AND in the Helm release secret, so use it for non-sensitive-but-secret-shaped config only. For real credentials prefer referencing a Secret you manage elsewhere via `envFrom`, or have an operator materialise it (see the `VaultStaticSecret` example under `extraObjects`). |
| componentDefaults.extraContainers | list | `[]` | Extra containers to add to the app pod as sidecars. |
| componentDefaults.extraPorts | list | `[]` | Anonymize extra container ports. |
| componentDefaults.extraVolumeClaims | list | `[]` | Additional volumeClaims to add, concatenated with `volumeClaims` above at render time. |
| componentDefaults.extraVolumeMounts | list | `[]` | Additional volumeMounts to add, concatenated with `volumeMounts` above at render time. |
| componentDefaults.extraVolumes | list | `[]` | Additional volumes to add, concatenated with `volumes` above at render time (e.g. to mount a cert or config from a values override without repeating the chart's own volumes). |
| componentDefaults.hostAliases | list | `[]` | Host aliases that will be injected at pod-level into /etc/hosts. |
| componentDefaults.hostNetwork | bool | `false` | Share the host network namespace. Container ports then bind directly on the node, so they must not collide with anything else running there. |
| componentDefaults.hostPID | bool | `false` | Share the host PID namespace (lets the container see and signal host processes). |
| componentDefaults.imagePullSecrets | list | `[]` | Image credentials configuration. |
| componentDefaults.initContainers | list | `[]` | Init containers to add to the app pod. |
| componentDefaults.nodeSelector | object | `{}` | Default node selector for app. |
| componentDefaults.podAnnotations | object | `{}` | Annotations for the app deployed pods. |
| componentDefaults.podLabels | object | `{}` | Labels for the app deployed pods. |
| componentDefaults.podSecurityContext | object | `{"fsGroup":10001,"fsGroupChangePolicy":"OnRootMismatch","runAsGroup":10001,"runAsNonRoot":true,"runAsUser":10001,"seccompProfile":{"type":"RuntimeDefault"}}` | Pod-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard. Rendered via `toYaml`, so any `PodSecurityContext` field is accepted. Adjust the UID/GID to whatever your image actually ships with - `runAsNonRoot` makes the kubelet refuse to start a container that would run as root, which is the intended failure mode rather than something to switch off. Set to `null` to omit the block entirely. |
| componentDefaults.priorityClassName | string | `""` | PriorityClass to schedule the pods with (e.g. `system-node-critical` for a node agent that must not be evicted under pressure). |
| componentDefaults.replicaCount | int | `1` | The number of application controller pods to run. Ignored when `deploymentType` is "DaemonSet" (one pod per node) or when `autoscaling.enabled` is true. |
| componentDefaults.revisionHistoryLimit | int | `10` | Revision history limit for the app. |
| componentDefaults.securityContext | object | `{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"privileged":false,"readOnlyRootFilesystem":false,"runAsGroup":10001,"runAsNonRoot":true,"runAsUser":10001}` | Container-level security context. Defaults to a hardened baseline that satisfies the `restricted` Pod Security Standard: no privilege escalation, no capabilities, immutable root filesystem. Rendered via `toYaml`, so any `SecurityContext` field is accepted. Note `readOnlyRootFilesystem` requires the app to write only to mounted volumes - the default `volumes`/`volumeMounts` below provide an `emptyDir` on /tmp for that reason. Set to `null` to omit the block entirely. |
| componentDefaults.terminationGracePeriodSeconds | int | `null` (Kubernetes default of 30) | Grace period, in seconds, given to the pod to shut down cleanly before it is killed. |
| componentDefaults.tolerations | list | `[]` | Default tolerations for app. |
| componentDefaults.topologySpreadConstraints | list | `[]` | Topology spread constraints used to spread the pods across failure domains. |
| componentDefaults.updateStrategy | object | `{}` | Update strategy applied when `deploymentType` is "StatefulSet" or "DaemonSet" (ignored for a Deployment, which uses `strategy` above). Rendered verbatim via `toYaml`, so it takes the native `StatefulSetUpdateStrategy`/`DaemonSetUpdateStrategy` shape of the selected kind; left empty, Kubernetes applies its own default (`RollingUpdate` for both). |
| componentDefaults.volumeClaims | list | `[]` | List of volumeClaims to add, rendered as the StatefulSet's `volumeClaimTemplates`. Requires `deploymentType: "StatefulSet"` - setting it on a Deployment or DaemonSet fails at render time rather than being silently dropped (use `volumes`/`extraVolumes` there instead). |
| componentDefaults.volumeMounts | list | `[{"mountPath":"/tmp","name":"tmp"}]` | List of mounts to add (normally used with `volumes` or `volumeClaims`). Prefer this for mounts the chart itself always needs; use `extraVolumeMounts` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to the `/tmp` mount backing the hardened `readOnlyRootFilesystem` default (see `volumes` above). |
| componentDefaults.volumes | list | `[{"emptyDir":{},"name":"tmp"}]` | List of volumes to add. Prefer this for volumes the chart itself always needs (e.g. security-hardening `emptyDir`s); use `extraVolumes` below for anything you add on top, so overriding one doesn't require repeating the other. Defaults to a `/tmp` `emptyDir`, which is what makes the default `securityContext.readOnlyRootFilesystem: false` usable - drop it only if you also relax that. Helm replaces lists wholesale rather than merging them, so overriding this key means restating the entries you want to keep. |

#### Autoscaling

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.autoscaling.enabled | bool | `false` | Enable Horizontal Pod Autoscaler for the app. |
| componentDefaults.autoscaling.maxReplicas | int | `3` | Maximum number of replicas for the app. |
| componentDefaults.autoscaling.minReplicas | int | `1` | Minimum number of replicas for the app. |
| componentDefaults.autoscaling.targetCPUUtilizationPercentage | int | `80` | Average CPU utilization percentage for the app. |
| componentDefaults.autoscaling.targetMemoryUtilizationPercentage | int | `80` | Average memory utilization percentage for the app. |

#### GrpcRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.grpcRoute.annotations | object | `{}` | Additional GRPCRoute annotations. |
| componentDefaults.grpcRoute.enabled | bool | `false` | Enable a GRPCRoute resource for this service. |
| componentDefaults.grpcRoute.hostnames | list | `[]` | Hostnames for the GRPCRoute to match. |
| componentDefaults.grpcRoute.labels | object | `{}` | Additional GRPCRoute labels. |
| componentDefaults.grpcRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the GRPCRoute to. |
| componentDefaults.grpcRoute.rules | list | `[]` | Routing rules for the GRPCRoute. |

#### HttpRoute

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.httpRoute.annotations | object | `{}` | Additional HTTPRoute annotations. |
| componentDefaults.httpRoute.enabled | bool | `false` | Enable an HTTPRoute resource for this service. |
| componentDefaults.httpRoute.hostnames | list | `[]` | Hostnames for the HTTPRoute to match. |
| componentDefaults.httpRoute.labels | object | `{}` | Additional HTTPRoute labels. |
| componentDefaults.httpRoute.parentRefs | list | `[]` | Parent references (Gateways) to attach the HTTPRoute to. |
| componentDefaults.httpRoute.rules | list | `[]` | Routing rules for the HTTPRoute. |

#### Image

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.image.digest | string | `""` | Image digest (`sha256:...`). When set it takes precedence over `tag`, pinning the exact image content so the same release can never resolve to a different build - preferred over a mutable tag for anything you deploy to production. |
| componentDefaults.image.pullPolicy | string | `"IfNotPresent"` | Image pull policy for the app. |
| componentDefaults.image.registry | string | `"ghcr.io"` | Registry to use for the app. |
| componentDefaults.image.repository | string | `""` | Repository to use for the app. |
| componentDefaults.image.tag | string | `""` | Tag to use for the app. Overrides the image tag whose default is the chart appVersion. |

#### Ingress

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.ingress.annotations | object | `{}` | Additional ingress annotations. |
| componentDefaults.ingress.className | string | `""` | Defines which ingress controller will implement the resource. |
| componentDefaults.ingress.enabled | bool | `false` | Whether or not ingress should be enabled. |
| componentDefaults.ingress.hosts[0].name | string | `"domain.local"` | Name of the host record. |
| componentDefaults.ingress.hosts[0].paths | list | `[{"backend":{"portNumber":null,"serviceName":""},"path":"/","pathType":"Prefix"}]` | Paths of the host record to manage routing (avoids repeating the same host for multiple paths/backends). |
| componentDefaults.ingress.hosts[0].paths[0].backend.portNumber | string | `nil` | Port used by the backend service linked to the path (leave null to use the app service port). |
| componentDefaults.ingress.hosts[0].paths[0].backend.serviceName | string | `""` | Name of the backend service linked to the path (leave empty to use the app service). |
| componentDefaults.ingress.hosts[0].paths[0].path | string | `"/"` | Path of the host record to manage routing. |
| componentDefaults.ingress.hosts[0].paths[0].pathType | string | `"Prefix"` | Path type of the host record. |
| componentDefaults.ingress.labels | object | `{}` | Additional ingress labels. |
| componentDefaults.ingress.tls | list | `[]` | Enable TLS configuration. |

#### Metrics

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.metrics.enabled | bool | `false` | Deploy metrics service. |
| componentDefaults.metrics.service.annotations | object | `{}` | Metrics service annotations. |
| componentDefaults.metrics.service.labels | object | `{}` | Metrics service labels. |
| componentDefaults.metrics.service.port | int | `9000` | Metrics service port. |
| componentDefaults.metrics.service.portName | string | `"metrics"` | Metrics service port name. |
| componentDefaults.metrics.service.targetPort | int | `9000` | Metrics service target port. |
| componentDefaults.metrics.service.type | string | `"ClusterIP"` | Type of metrics service to create. |
| componentDefaults.metrics.serviceMonitor.annotations | object | `{}` | Prometheus ServiceMonitor annotations. |
| componentDefaults.metrics.serviceMonitor.enabled | bool | `false` | Enable a prometheus ServiceMonitor. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].basicAuth.password | string | `""` | The secret in the service monitor namespace that contains the password for authentication. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].basicAuth.username | string | `""` | The secret in the service monitor namespace that contains the username for authentication. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.key | string | `""` | Secret key to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].bearerTokenSecret.name | string | `""` | Secret name to mount to read bearer token for scraping targets. The secret needs to be in the same namespace as the service monitor and accessible by the Prometheus Operator. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].honorLabels | bool | `false` | When true, honorLabels preserves the metric’s labels when they collide with the target’s labels. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].interval | string | `"30s"` | Prometheus ServiceMonitor interval. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].metricRelabelings | list | `[]` | Prometheus MetricRelabelConfigs to apply to samples before ingestion. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].path | string | `"/metrics"` | Path used by the Prometheus ServiceMonitor to scrape metrics. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].relabelings | list | `[]` | Prometheus RelabelConfigs to apply to samples before scraping. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].scheme | string | `""` | Prometheus ServiceMonitor scheme. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].scrapeTimeout | string | `"10s"` | Prometheus ServiceMonitor scrapeTimeout. If empty, Prometheus uses the global scrape timeout unless it is less than the target's scrape interval value in which the latter is used. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].selector | object | `{}` | Prometheus ServiceMonitor selector. |
| componentDefaults.metrics.serviceMonitor.endpoints[0].tlsConfig | object | `{}` | Prometheus ServiceMonitor tlsConfig. |
| componentDefaults.metrics.serviceMonitor.labels | object | `{}` | Prometheus ServiceMonitor labels. |

#### NetworkPolicy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.networkPolicy.annotations | object | `{}` | Annotations to be added to the app NetworkPolicy. |
| componentDefaults.networkPolicy.create | bool | `false` | Create NetworkPolicy object for the app. The policy always selects this component's pods only (via its selector labels), never the whole namespace. |
| componentDefaults.networkPolicy.egress | list | `[]` | Egress rules for the NetworkPolicy object. |
| componentDefaults.networkPolicy.ingress | list | `[]` | Ingress rules for the NetworkPolicy object. |
| componentDefaults.networkPolicy.labels | object | `{}` | Labels to be added to the app NetworkPolicy. |
| componentDefaults.networkPolicy.policyTypes | list | `["Ingress"]` | Policy types used in the NetworkPolicy object. |

#### Pdb

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.pdb.annotations | object | `{}` | Annotations to be added to app pdb. |
| componentDefaults.pdb.enabled | bool | `false` | Deploy a PodDisruptionBudget for the app |
| componentDefaults.pdb.labels | object | `{}` | Labels to be added to app pdb. |
| componentDefaults.pdb.maxUnavailable | string | `""` | Number of pods that are unavailable after eviction as number or percentage (eg.: 50%). Has higher precedence over `frontend.pdb.minAvailable`. |
| componentDefaults.pdb.minAvailable | string | `""` | Number of pods that are available after eviction as number or percentage (eg.: 50%). One of `minAvailable` / `maxUnavailable` must be set when `pdb.enabled` is true - a budget of 0 is the same as having no budget at all, so leaving both empty fails at render time. |

#### Probes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.probes.livenessProbe.exec.command[0] | string | `"sh"` |  |
| componentDefaults.probes.livenessProbe.exec.command[1] | string | `"-c"` |  |
| componentDefaults.probes.livenessProbe.exec.command[2] | string | `"celery -A app.celery_app.celery_app inspect ping -d celery@$HOSTNAME"` |  |
| componentDefaults.probes.livenessProbe.failureThreshold | int | `3` |  |
| componentDefaults.probes.livenessProbe.initialDelaySeconds | int | `60` |  |
| componentDefaults.probes.livenessProbe.periodSeconds | int | `60` |  |
| componentDefaults.probes.livenessProbe.timeoutSeconds | int | `20` |  |
| componentDefaults.probes.readinessProbe | string | `nil` |  |
| componentDefaults.probes.startupProbe.exec.command[0] | string | `"sh"` |  |
| componentDefaults.probes.startupProbe.exec.command[1] | string | `"-c"` |  |
| componentDefaults.probes.startupProbe.exec.command[2] | string | `"celery -A app.celery_app.celery_app inspect ping -d celery@$HOSTNAME"` |  |
| componentDefaults.probes.startupProbe.failureThreshold | int | `30` |  |
| componentDefaults.probes.startupProbe.initialDelaySeconds | int | `30` |  |
| componentDefaults.probes.startupProbe.periodSeconds | int | `10` |  |
| componentDefaults.probes.startupProbe.timeoutSeconds | int | `20` |  |

#### Resources

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.resources.limits.cpu | string | `"2"` | CPU limit for the app. |
| componentDefaults.resources.limits.memory | string | `"4Gi"` | Memory limit for the app. |
| componentDefaults.resources.requests.cpu | string | `"2"` | CPU request for the app. |
| componentDefaults.resources.requests.memory | string | `"1Gi"` | Memory request for the app. |

#### Service

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.service.enabled | bool | `false` | Whether or not to create a Service for the app (a queue consumer takes no traffic). |
| componentDefaults.service.extraPorts | list | `[]` | Extra service ports. |
| componentDefaults.service.nodePort | int | `null` (allocated by Kubernetes) | Port used when type is `NodePort` to expose the service on the given node port. Left empty, Kubernetes allocates one from the configured node-port range, which avoids two releases of this chart colliding on the same hardcoded port. |
| componentDefaults.service.port | int | `80` | Port used by the service. |
| componentDefaults.service.portName | string | `"http"` | Port name used by the service. |
| componentDefaults.service.protocol | string | `"TCP"` | Protocol used by the service. |
| componentDefaults.service.type | string | `"ClusterIP"` | Type of service to create for the app. |

#### ServiceAccount

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.serviceAccount.annotations | object | `{}` | Annotations applied to created service account. |
| componentDefaults.serviceAccount.automountServiceAccountToken | bool | `false` | Should the service account access token be automount in the pod. |
| componentDefaults.serviceAccount.clusterRole.create | bool | `false` | Should the clusterRole be created. |
| componentDefaults.serviceAccount.clusterRole.rules | list | `[]` | ClusterRole rules associated with the service account. |
| componentDefaults.serviceAccount.create | bool | `false` | Create a service account. |
| componentDefaults.serviceAccount.enabled | bool | `false` | Enable the service account. |
| componentDefaults.serviceAccount.name | string | `""` | Service account name. |
| componentDefaults.serviceAccount.role.create | bool | `false` | Should the role be created. |
| componentDefaults.serviceAccount.role.rules | list | `[]` | Role rules associated with the service account. |

#### Strategy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| componentDefaults.strategy.rollingUpdate.maxSurge | int | `1` | The maximum number of pods that can be scheduled above the desired number of pods. |
| componentDefaults.strategy.rollingUpdate.maxUnavailable | int | `1` | The maximum number of pods that can be unavailable during the update process. |
| componentDefaults.strategy.type | string | `"RollingUpdate"` | Strategy type used to replace old Pods by new ones, can be `Recreate` or `RollingUpdate`. Only applied when `deploymentType` is "Deployment". |

### ExtraObjects

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| extraObjects.lisa-db-appuser | string | `"apiVersion: v1\nkind: Secret\nmetadata:\n  name: lisa-db-appuser\ntype: kubernetes.io/basic-auth\nstringData:\n  username: \"{{ .Values.secrets.postgresUsername }}\"\n  password: \"{{ .Values.secrets.postgresPassword }}\"\n"` |  |
| extraObjects.lisa-db-superuser | string | `"apiVersion: v1\nkind: Secret\nmetadata:\n  name: lisa-db-superuser\ntype: kubernetes.io/basic-auth\nstringData:\n  username: \"postgres\"\n  password: \"{{ .Values.secrets.postgresPassword }}\"\n"` |  |

### Frontend

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.containerPort | int | `8080` |  |
| frontend.image | object | `{"repository":"mitchou10/lisa/frontend"}` | Overrides on top of `componentDefaults` above - only what makes this component different needs to be listed here. |

#### PodSecurityContext

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.podSecurityContext.fsGroup | int | `101` |  |
| frontend.podSecurityContext.runAsGroup | int | `101` |  |
| frontend.podSecurityContext.runAsUser | int | `101` |  |

#### Probes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.probes.livenessProbe.failureThreshold | int | `3` |  |
| frontend.probes.livenessProbe.httpGet.path | string | `"/"` |  |
| frontend.probes.livenessProbe.httpGet.port | int | `8080` |  |
| frontend.probes.livenessProbe.initialDelaySeconds | int | `30` |  |
| frontend.probes.livenessProbe.periodSeconds | int | `30` |  |
| frontend.probes.livenessProbe.successThreshold | int | `1` |  |
| frontend.probes.livenessProbe.timeoutSeconds | int | `5` |  |
| frontend.probes.readinessProbe.failureThreshold | int | `2` |  |
| frontend.probes.readinessProbe.httpGet.path | string | `"/"` |  |
| frontend.probes.readinessProbe.httpGet.port | int | `8080` |  |
| frontend.probes.readinessProbe.initialDelaySeconds | int | `10` |  |
| frontend.probes.readinessProbe.periodSeconds | int | `10` |  |
| frontend.probes.readinessProbe.successThreshold | int | `2` |  |
| frontend.probes.readinessProbe.timeoutSeconds | int | `5` |  |
| frontend.probes.startupProbe.failureThreshold | int | `10` |  |
| frontend.probes.startupProbe.httpGet.path | string | `"/"` |  |
| frontend.probes.startupProbe.httpGet.port | int | `8080` |  |
| frontend.probes.startupProbe.initialDelaySeconds | int | `0` |  |
| frontend.probes.startupProbe.periodSeconds | int | `10` |  |
| frontend.probes.startupProbe.successThreshold | int | `1` |  |
| frontend.probes.startupProbe.timeoutSeconds | int | `5` |  |

#### Resources

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.resources.limits.cpu | string | `"500m"` |  |
| frontend.resources.limits.memory | string | `"256Mi"` |  |
| frontend.resources.requests.cpu | string | `"50m"` |  |
| frontend.resources.requests.memory | string | `"64Mi"` |  |

#### SecurityContext

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.securityContext.readOnlyRootFilesystem | bool | `true` |  |
| frontend.securityContext.runAsGroup | int | `101` |  |
| frontend.securityContext.runAsUser | int | `101` |  |

#### Service

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| frontend.service.enabled | bool | `true` |  |

### Gateway

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| gateway.addresses | list | `[]` | Gateway addresses configuration. |
| gateway.annotations | object | `{}` | Additional gateway annotations. |
| gateway.className | string | `""` | GatewayClass name. Required when creating a Gateway. |
| gateway.create | bool | `false` | Create a Gateway resource. Usually, you reference an existing Gateway managed by the infrastructure team. |
| gateway.labels | object | `{}` | Additional gateway labels. |
| gateway.listeners | list | `[]` | Gateway listeners configuration. |
| gateway.name | string | `""` | Name of the Gateway resource. If not set, uses the release fullname. |

### ImageClassification

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| imageClassification.image | object | `{"repository":"mitchou10/lisa/image-classification"}` | Overrides on top of `componentDefaults` above - only what makes this component different needs to be listed here. |

#### EnvCm

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| imageClassification.envCm.CELERY_QUEUE | string | `"image-classification"` |  |
| imageClassification.envCm.IMAGE_MODEL | string | `"openai/clip-vit-base-patch32"` |  |
| imageClassification.envCm.LISA_API_URL | string | `"http://{{ include \"helper.fullname\" . }}-backend:8000"` |  |
| imageClassification.envCm.REDIS_URL | string | `"redis://:{{ .Values.redis.auth.password }}@lisa-redis:6379/0"` |  |
| imageClassification.envCm.S3_BUCKET | string | `"{{ .Values.s3.bucket }}"` |  |
| imageClassification.envCm.S3_ENDPOINT_URL | string | `"http://lisa-rustfs:9000"` |  |
| imageClassification.envCm.S3_REGION | string | `"us-east-1"` |  |

#### EnvSecret

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| imageClassification.envSecret.LISA_SERVICE_TOKEN | string | `"{{ .Values.secrets.serviceToken }}"` |  |
| imageClassification.envSecret.S3_ACCESS_KEY | string | `"{{ .Values.rustfs.auth.accessKey }}"` |  |
| imageClassification.envSecret.S3_SECRET_KEY | string | `"{{ .Values.rustfs.auth.secretKey }}"` |  |

### Ner

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| ner.image | object | `{"repository":"mitchou10/lisa/ner"}` | Overrides on top of `componentDefaults` above - only what makes this component different needs to be listed here. |

#### EnvCm

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| ner.envCm.CELERY_QUEUE | string | `"ner"` |  |
| ner.envCm.LISA_API_URL | string | `"http://{{ include \"helper.fullname\" . }}-backend:8000"` |  |
| ner.envCm.NER_MODEL | string | `"fastino/gliner2.5-multi-v1"` |  |
| ner.envCm.NER_THRESHOLD | string | `"0.5"` |  |
| ner.envCm.REDIS_URL | string | `"redis://:{{ .Values.redis.auth.password }}@lisa-redis:6379/0"` |  |

#### EnvSecret

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| ner.envSecret.LISA_SERVICE_TOKEN | string | `"{{ .Values.secrets.serviceToken }}"` |  |

### Parser

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| parser.image | object | `{"repository":"mitchou10/lisa/parser"}` | Overrides on top of `componentDefaults` above - only what makes this component different needs to be listed here. |

#### EnvCm

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| parser.envCm.CELERY_QUEUE | string | `"liteparse-ocr"` |  |
| parser.envCm.LISA_API_URL | string | `"http://{{ include \"helper.fullname\" . }}-backend:8000"` |  |
| parser.envCm.OCR_LANGUAGE | string | `"eng+fra"` |  |
| parser.envCm.REDIS_URL | string | `"redis://:{{ .Values.redis.auth.password }}@lisa-redis:6379/0"` |  |
| parser.envCm.S3_BUCKET | string | `"{{ .Values.s3.bucket }}"` |  |
| parser.envCm.S3_ENDPOINT_URL | string | `"http://lisa-rustfs:9000"` |  |
| parser.envCm.S3_REGION | string | `"us-east-1"` |  |

#### EnvSecret

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| parser.envSecret.LISA_SERVICE_TOKEN | string | `"{{ .Values.secrets.serviceToken }}"` |  |
| parser.envSecret.S3_ACCESS_KEY | string | `"{{ .Values.rustfs.auth.accessKey }}"` |  |
| parser.envSecret.S3_SECRET_KEY | string | `"{{ .Values.rustfs.auth.secretKey }}"` |  |

#### Resources

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| parser.resources.limits.memory | string | `"2Gi"` |  |
| parser.resources.requests.cpu | string | `"250m"` |  |
| parser.resources.requests.memory | string | `"512Mi"` |  |

### Redis

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| redis.enabled | bool | `true` |  |
| redis.fullnameOverride | string | `"lisa-redis"` |  |

#### Auth

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| redis.auth.enabled | bool | `true` |  |
| redis.auth.password | string | `"change-me-redis"` |  |

### Relation

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| relation.image | object | `{"repository":"mitchou10/lisa/relation"}` | Overrides on top of `componentDefaults` above - only what makes this component different needs to be listed here. |

#### EnvCm

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| relation.envCm.CELERY_QUEUE | string | `"relation"` |  |
| relation.envCm.LISA_API_URL | string | `"http://{{ include \"helper.fullname\" . }}-backend:8000"` |  |
| relation.envCm.REDIS_URL | string | `"redis://:{{ .Values.redis.auth.password }}@lisa-redis:6379/0"` |  |
| relation.envCm.RELATION_MODEL | string | `"fastino/gliner2.5-multi-v1"` |  |
| relation.envCm.RELATION_THRESHOLD | string | `"0.5"` |  |

#### EnvSecret

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| relation.envSecret.LISA_SERVICE_TOKEN | string | `"{{ .Values.secrets.serviceToken }}"` |  |

### Rustfs

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| rustfs.enabled | bool | `true` |  |
| rustfs.fullnameOverride | string | `"lisa-rustfs"` |  |

#### Auth

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| rustfs.auth.accessKey | string | `"rustfsadmin"` |  |
| rustfs.auth.secretKey | string | `"change-me-rustfs"` |  |

#### ConsoleIngress

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| rustfs.consoleIngress.enabled | bool | `false` |  |

#### Ingress

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| rustfs.ingress.enabled | bool | `false` |  |

### Safety

#### General

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| safety.image | object | `{"repository":"mitchou10/lisa/safety"}` | Overrides on top of `componentDefaults` above - only what makes this component different needs to be listed here. |

#### EnvCm

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| safety.envCm.CELERY_QUEUE | string | `"safety"` |  |
| safety.envCm.LISA_API_URL | string | `"http://{{ include \"helper.fullname\" . }}-backend:8000"` |  |
| safety.envCm.REDIS_URL | string | `"redis://:{{ .Values.redis.auth.password }}@lisa-redis:6379/0"` |  |
| safety.envCm.SAFETY_MODEL | string | `"fastino/GLiNER2-Guardrails-PII-Multi"` |  |

#### EnvSecret

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| safety.envSecret.LISA_SERVICE_TOKEN | string | `"{{ .Values.secrets.serviceToken }}"` |  |
