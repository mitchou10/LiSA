# LiSA Helm chart

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
dependency versions. Redis, Postgres, and RustFS are bundled dependencies and are
enabled by default.

The default credentials and `.local` URLs are for development, **not production**.
Replace `secrets.serviceToken`, `secrets.keycloakClientSecret`, database/cache/S3
credentials, application URLs, and identity-provider settings as appropriate.
Keep real secrets out of version control.

The bundled services currently use fixed names (`lisa-redis`, `lisa-postgres`,
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
| `redis`, `postgres`, `rustfs` | Dependency-specific settings; they do **not** inherit `componentDefaults`. |

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
resources, also set `redis.enabled`, `postgres.enabled`, and `rustfs.enabled` to
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

```gotemplate
{{- include "helper.component.deployment" (dict "root" . "name" "newComponent") }}
```

For changes to shared templates, check the default render as well as Deployment,
StatefulSet, DaemonSet, routing, and relevant optional resources. `helm lint` and
`helm template` validate local rendering; they do not replace validation against
a Kubernetes cluster with the required CRDs installed.
