{{/*
Shared component resource templates: a LiSA extension to the this-is-tobi/helm-charts scaffold,
not an upstream chart dependency. Per-component files include these macros by name. See the
chart README for the inheritance rules and the steps required to add a component.
*/}}


{{/*
Canonical list of this chart's components. Single source of truth for validation.yaml; keep in
sync with the per-component template folders under templates/ and with values.yaml.
*/}}
{{- define "helper.componentNames" -}}
{{- list "backend" "frontend" "anonymize" "safety" "ner" "relation" "classification" "imageClassification" "parser" | toYaml -}}
{{- end -}}


{{/*
Resolve a component's effective values by deep-merging its values.yaml block on top of
`componentDefaults` (the shared "mold" every component is stamped from). `deepCopy` is required
before `mergeOverwrite` because the latter mutates its first argument in place and
`componentDefaults` is one dict shared by reference across every component - without copying it
first, merging the first component rendered would permanently pollute `componentDefaults` for
every component rendered afterwards in the same `helm template` run. Nested maps are merged key by
key (a component overriding `resources.limits.cpu` keeps every other default untouched); lists
(e.g. `ingress.hosts`) are replaced wholesale by the component's own list when it sets one.

`probes` is replaced wholesale instead, same as a list: a probe's handler (`exec`/`httpGet`/
`tcpSocket`) is a set of mutually exclusive alternatives, so merging a component's own `httpGet`
probe key by key into `componentDefaults`' `exec` probe would produce a probe with both handlers
set - which Kubernetes rejects. A component with an HTTP(S) health endpoint (unlike the `exec`
probes most worker components share) is expected to restate the whole `probes` block.
Parameters:
- root: The root context.
- name: The component name (e.g. "servicename"), used to find its override block in Values.
*/}}
{{- define "helper.component.values" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $defaults := deepCopy ($root.Values.componentDefaults | default dict) -}}
{{- $overrides := deepCopy (index $root.Values $name | default dict) -}}
{{- if hasKey $overrides "probes" -}}
{{- $_ := unset $defaults "probes" -}}
{{- $_ := set $defaults "probes" (index $overrides "probes") -}}
{{- $_ := unset $overrides "probes" -}}
{{- end -}}
{{- mergeOverwrite $defaults $overrides | toYaml -}}
{{- end -}}


{{- define "helper.component.deployment" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if eq $component.deploymentType "Deployment" }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
spec:
  {{- if not $component.autoscaling.enabled }}
  replicas: {{ $component.replicaCount }}
  {{- end }}
  revisionHistoryLimit: {{ $component.revisionHistoryLimit | default 10 }}
  selector:
    matchLabels: {{- include "helper.selectorLabels" (dict "root" $root "componentName" $name) | nindent 6 }}
  strategy:
    type: {{ $component.strategy.type }}
    {{- if eq $component.strategy.type "RollingUpdate" }}
    rollingUpdate:
      maxUnavailable: {{ $component.strategy.rollingUpdate.maxUnavailable }}
      maxSurge: {{ $component.strategy.rollingUpdate.maxSurge }}
    {{- end }}
  template:
    {{- include "helper.component.podTemplate" (dict "root" $root "name" $name "component" $component) | nindent 4 }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.statefulset" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if eq $component.deploymentType "StatefulSet" }}
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- include "helper.labels" (dict "root" $root "componentName" $name) | nindent 4 }}
spec:
  {{- if not $component.autoscaling.enabled }}
  replicas: {{ $component.replicaCount }}
  {{- end }}
  revisionHistoryLimit: {{ $component.revisionHistoryLimit | default 10 }}
  selector:
    matchLabels: {{- include "helper.selectorLabels" (dict "root" $root "componentName" $name) | nindent 6 }}
  serviceName: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  {{- with $component.updateStrategy }}
  updateStrategy: {{- toYaml . | nindent 4 }}
  {{- end }}
  template:
    {{- include "helper.component.podTemplate" (dict "root" $root "name" $name "component" $component) | nindent 4 }}
  {{- if or $component.volumeClaims $component.extraVolumeClaims }}
  volumeClaimTemplates: {{- toYaml (concat (default (list) $component.volumeClaims) (default (list) $component.extraVolumeClaims)) | nindent 2 }}
  {{- end }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.daemonset" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if eq $component.deploymentType "DaemonSet" }}
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
spec:
  revisionHistoryLimit: {{ $component.revisionHistoryLimit | default 10 }}
  selector:
    matchLabels: {{- include "helper.selectorLabels" (dict "root" $root "componentName" $name) | nindent 6 }}
  {{- with $component.updateStrategy }}
  updateStrategy: {{- toYaml . | nindent 4 }}
  {{- end }}
  template:
    {{- include "helper.component.podTemplate" (dict "root" $root "name" $name "component" $component) | nindent 4 }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.service" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- /* Not gated on `deploymentType`: every supported kind (Deployment/StatefulSet/DaemonSet) can
sit behind a Service, and `service.enabled` is the switch for components that take no traffic.
This matches metrics.yaml, which is gated the same way. */ -}}
{{- if $component.service.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
spec:
  type: {{ $component.service.type | default "ClusterIP" }}
  ports:
  - port: {{ $component.service.port | default 80 }}
    targetPort: {{ $component.containerPortName | default $component.containerPort | default 8080 }}
    protocol: {{ $component.service.protocol | default "TCP" }}
    {{- if and (eq $component.service.type "NodePort") $component.service.nodePort }}
    nodePort: {{ $component.service.nodePort }}
    {{- end }}
    name: {{ $component.service.portName | default "http" }}
  {{- if $component.service.extraPorts -}}
  {{- toYaml $component.service.extraPorts | nindent 2 -}}
  {{- end }}
  selector: {{- include "helper.selectorLabels" (dict "root" $root "componentName" $name) | nindent 4 }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.configmap" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if or $component.envCm $root.Values.global.envCm -}}
kind: ConfigMap
apiVersion: v1
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
data:
  {{- if $root.Values.global.envCm -}}
  {{- include "helper.env" (dict "root" $root "data" $root.Values.global.envCm) | indent 2 }}
  {{- end -}}
  {{- if $component.envCm -}}
  {{- include "helper.env" (dict "root" $root "data" $component.envCm) | indent 2 }}
  {{- end -}}
{{- end -}}
{{- end }}
{{- end -}}


{{- define "helper.component.secret" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if or $component.envSecret $root.Values.global.envSecret -}}
kind: Secret
apiVersion: v1
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
data:
  {{- if $root.Values.global.envSecret -}}
  {{- include "helper.secret" (dict "root" $root "data" $root.Values.global.envSecret) | indent 2 }}
  {{- end -}}
  {{- if $component.envSecret -}}
  {{- include "helper.secret" (dict "root" $root "data" $component.envSecret) | indent 2 }}
  {{- end -}}
{{- end -}}
{{- end }}
{{- end -}}


{{- define "helper.component.hpa" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- /* DaemonSet is excluded on purpose: it has no scale subresource, so an HPA targeting one is
rejected by the API server. `helper.component.validate` already fails on that combination - this
guard just keeps the template honest if the validation is ever relaxed. */ -}}
{{- if and $component.autoscaling.enabled (ne $component.deploymentType "DaemonSet") }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: {{ $component.deploymentType }}
    name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  minReplicas: {{ $component.autoscaling.minReplicas }}
  maxReplicas: {{ $component.autoscaling.maxReplicas }}
  metrics:
  {{- if $component.autoscaling.targetCPUUtilizationPercentage }}
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: {{ $component.autoscaling.targetCPUUtilizationPercentage }}
  {{- end }}
  {{- if $component.autoscaling.targetMemoryUtilizationPercentage }}
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: {{ $component.autoscaling.targetMemoryUtilizationPercentage }}
  {{- end }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.pdb" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if $component.pdb.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
  {{- if $component.pdb.labels }}
    {{- toYaml $component.pdb.labels | nindent 4 }}
  {{- end }}
  {{- if $component.pdb.annotations }}
  annotations: {{- toYaml $component.pdb.annotations | nindent 4 }}
  {{- end }}
spec:
  {{- /* Tested against the empty string rather than for truthiness: `maxUnavailable: 0` is a valid
  setting (it blocks every voluntary eviction) but is falsy, so `with`/`if` would silently fall
  through to minAvailable. `toString` maps both nil and "" to "", which are the two unset forms.
  `helper.component.validate` guarantees at least one of the two is set. */ -}}
  {{- if ne (toString $component.pdb.maxUnavailable) "" }}
  maxUnavailable: {{ $component.pdb.maxUnavailable }}
  {{- else }}
  minAvailable: {{ $component.pdb.minAvailable }}
  {{- end }}
  selector:
    matchLabels: {{- include "helper.selectorLabels" (dict "root" $root "componentName" $name) | nindent 6 }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.networkpolicy" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if $component.networkPolicy.create }}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
  {{- if $component.networkPolicy.labels }}
    {{- toYaml $component.networkPolicy.labels | nindent 4 }}
  {{- end }}
  {{- if $component.networkPolicy.annotations }}
  annotations: {{- toYaml $component.networkPolicy.annotations | nindent 4 }}
  {{- end }}
spec:
  {{- /* Required: an omitted podSelector defaults to `{}`, which would apply these rules to EVERY
  pod in the release namespace instead of just this component's pods. */}}
  podSelector:
    matchLabels: {{- include "helper.selectorLabels" (dict "root" $root "componentName" $name) | nindent 6 }}
  policyTypes: {{- toYaml $component.networkPolicy.policyTypes | nindent 2 }}
  {{- with $component.networkPolicy.ingress }}
  ingress: {{- toYaml . | nindent 2 }}
  {{- end }}
  {{- with $component.networkPolicy.egress }}
  egress: {{- toYaml . | nindent 2 }}
  {{- end }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.serviceaccount" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if and $component.serviceAccount.enabled $component.serviceAccount.create }}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ $component.serviceAccount.name | default (include "helper.componentFullname" (dict "root" $root "componentName" $name)) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
  {{- if $component.serviceAccount.annotations }}
  annotations:
    {{- tpl (toYaml $component.serviceAccount.annotations) $root | nindent 4 }}
  {{- end }}
automountServiceAccountToken: {{ $component.serviceAccount.automountServiceAccountToken }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.role" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if and $component.serviceAccount.enabled $component.serviceAccount.role.create $component.serviceAccount.role.rules }}
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
rules: {{- toYaml $component.serviceAccount.role.rules | nindent 0 }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.rolebinding" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- /* Gated on `rules` as well, exactly like role.yaml: without it, an empty `rules` list yields a
RoleBinding whose roleRef points at a Role that was never created. */ -}}
{{- if and $component.serviceAccount.enabled $component.serviceAccount.role.create $component.serviceAccount.role.rules }}
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
subjects:
- kind: ServiceAccount
  name: {{ $component.serviceAccount.name | default (include "helper.componentFullname" (dict "root" $root "componentName" $name)) }}
  namespace: {{ $root.Release.Namespace }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.clusterrole" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if and $component.serviceAccount.enabled $component.serviceAccount.clusterRole.create $component.serviceAccount.clusterRole.rules }}
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
rules: {{- toYaml $component.serviceAccount.clusterRole.rules | nindent 0 }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.clusterrolebinding" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- /* Gated on `rules` as well, exactly like clusterrole.yaml: without it, an empty `rules` list
yields a ClusterRoleBinding whose roleRef points at a ClusterRole that was never created. */ -}}
{{- if and $component.serviceAccount.enabled $component.serviceAccount.clusterRole.create $component.serviceAccount.clusterRole.rules }}
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
subjects:
- kind: ServiceAccount
  name: {{ $component.serviceAccount.name | default (include "helper.componentFullname" (dict "root" $root "componentName" $name)) }}
  namespace: {{ $root.Release.Namespace }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.pullsecret" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- range $index, $value := $component.imagePullSecrets }}
{{- if and $value.create $value.username $value.password }}
---
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "helper.imagePullSecretName" (dict "root" $root "componentName" $name "index" $index "value" $value) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: {{ template "helper.imagePullSecret" dict "username" $value.username "password" $value.password "email" $value.email "registry" $value.registry }}
{{- end }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.metrics" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if $component.metrics.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" (printf "%s-metrics" $name)) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" (printf "%s-metrics" $name))) | nindent 4 }}
  {{- if $component.metrics.service.labels }}
    {{- toYaml $component.metrics.service.labels | nindent 4 }}
  {{- end }}
  {{- if $component.metrics.service.annotations }}
  annotations: {{- toYaml $component.metrics.service.annotations | nindent 4 }}
  {{- end }}
spec:
  type: {{ $component.metrics.service.type | default "ClusterIP" }}
  ports:
  - port: {{ $component.metrics.service.port }}
    targetPort: {{ $component.metrics.service.targetPort }}
    protocol: TCP
    name: {{ $component.metrics.service.portName | default "metrics" }}
  selector: {{- include "helper.selectorLabels" (dict "root" $root "componentName" $name) | nindent 4 }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.servicemonitor" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if and $component.metrics.enabled $component.metrics.serviceMonitor.enabled }}
{{- $metricSvcPort := $component.metrics.service.portName | default $component.metrics.service.port -}}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" (printf "%s-metrics" $name)) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
  {{- if $component.metrics.serviceMonitor.labels }}
    {{- toYaml $component.metrics.serviceMonitor.labels | nindent 4 }}
  {{- end }}
  {{- if $component.metrics.serviceMonitor.annotations }}
  annotations: {{- toYaml $component.metrics.serviceMonitor.annotations | nindent 4 }}
  {{- end }}
spec:
  endpoints:
  {{- range $component.metrics.serviceMonitor.endpoints }}
  - port: {{ $metricSvcPort }}
    path: {{ .path }}
    honorLabels: {{ .honorLabels }}
    {{- if and .basicAuth .basicAuth.username .basicAuth.password }}
    basicAuth: {{- toYaml .basicAuth | nindent 6 }}
    {{- end }}
    {{- if and .bearerTokenSecret .bearerTokenSecret.name .bearerTokenSecret.key }}
    bearerTokenSecret: {{- toYaml .bearerTokenSecret | nindent 6 }}
    {{- end }}
    {{- if .interval }}
    interval: {{ .interval }}
    {{- end }}
    {{- if .scrapeTimeout }}
    scrapeTimeout: {{ .scrapeTimeout }}
    {{- end }}
    {{- if .relabelings }}
    relabelings: {{- toYaml .relabelings | nindent 6 }}
    {{- end }}
    {{- if .metricRelabelings }}
    metricRelabelings: {{- toYaml .metricRelabelings | nindent 6 }}
    {{- end }}
    {{- if .scheme }}
    scheme: {{ .scheme }}
    {{- end }}
    {{- if .tlsConfig }}
    tlsConfig: {{- toYaml .tlsConfig | nindent 6 }}
    {{- end }}
  {{- end }}
  namespaceSelector:
    matchNames:
    - {{ $root.Release.Namespace | quote }}
  selector:
    matchLabels: {{- include "helper.selectorLabels" (dict "root" $root "componentName" (printf "%s-metrics" $name)) | nindent 6 }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.ingress" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if $component.ingress.enabled -}}
{{- $fullNameApp := include "helper.componentFullname" (dict "root" $root "componentName" $name) -}}
{{- $svcPortApp := $component.service.port -}}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
  {{- if $component.ingress.labels }}
    {{- toYaml $component.ingress.labels | nindent 4 }}
  {{- end }}
  {{- if $component.ingress.annotations }}
  annotations:
    {{- tpl (toYaml $component.ingress.annotations) $root | nindent 4 }}
  {{- end }}
spec:
  {{- if $component.ingress.className }}
  ingressClassName: {{ $component.ingress.className }}
  {{- end }}
  {{- if gt (len $component.ingress.tls) 0 }}
  tls:
  {{- range $component.ingress.tls }}
  - hosts:
    {{- range .hosts }}
    - {{ . | quote }}
    {{- end }}
    secretName: {{ .secretName | default (printf "%s-%s" $fullNameApp "tls") | quote }}
  {{- end }}
  {{- end }}
  rules:
  {{- range $component.ingress.hosts }}
  - host: {{ .name | quote }}
    http:
      paths:
      {{- range .paths }}
      - path: {{ .path | default "/" }}
        pathType: {{ .pathType | default "Prefix" }}
        backend:
          service:
          {{- if .backend }}
            name: {{ .backend.serviceName | default $fullNameApp }}
            port:
              number: {{ .backend.portNumber | default $svcPortApp }}
          {{- else }}
            name: {{ $fullNameApp }}
            port:
              number: 80
          {{- end }}
      {{- end }}
  {{- end }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.httproute" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if $component.httpRoute.enabled -}}
{{- $fullNameApp := include "helper.componentFullname" (dict "root" $root "componentName" $name) -}}
{{- $svcPortApp := $component.service.port -}}
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
  {{- if $component.httpRoute.labels }}
    {{- toYaml $component.httpRoute.labels | nindent 4 }}
  {{- end }}
  {{- if $component.httpRoute.annotations }}
  annotations:
    {{- tpl (toYaml $component.httpRoute.annotations) $root | nindent 4 }}
  {{- end }}
spec:
  {{- if $component.httpRoute.parentRefs }}
  parentRefs:
  {{- range $component.httpRoute.parentRefs }}
  - name: {{ .name }}
    {{- if .namespace }}
    namespace: {{ .namespace }}
    {{- end }}
    {{- if .sectionName }}
    sectionName: {{ .sectionName }}
    {{- end }}
    {{- if .port }}
    port: {{ .port }}
    {{- end }}
    {{- if .group }}
    group: {{ .group }}
    {{- end }}
    {{- if .kind }}
    kind: {{ .kind }}
    {{- end }}
  {{- end }}
  {{- end }}
  {{- if $component.httpRoute.hostnames }}
  hostnames:
  {{- range $component.httpRoute.hostnames }}
  - {{ . | quote }}
  {{- end }}
  {{- end }}
  {{- if $component.httpRoute.rules }}
  rules:
  {{- range $component.httpRoute.rules }}
  {{- if .matches }}
  - matches:
    {{- range .matches }}
    {{- if .path }}
    - path:
        type: {{ .path.type | default "PathPrefix" }}
        value: {{ .path.value | default "/" }}
    {{- end }}
      {{- if .headers }}
      headers:
      {{- range .headers }}
      - type: {{ .type | default "Exact" }}
        name: {{ .name }}
        value: {{ .value }}
      {{- end }}
      {{- end }}
      {{- if .queryParams }}
      queryParams:
      {{- range .queryParams }}
      - type: {{ .type | default "Exact" }}
        name: {{ .name }}
        value: {{ .value }}
      {{- end }}
      {{- end }}
      {{- if .method }}
      method: {{ .method }}
      {{- end }}
    {{- end }}
    {{- end }}
    {{- if .filters }}
    filters:
    {{- toYaml .filters | nindent 4 }}
    {{- end }}
    {{- if .backendRefs }}
    backendRefs:
    {{- range .backendRefs }}
    - name: {{ .name | default $fullNameApp }}
      port: {{ .port | default $svcPortApp }}
      {{- if .weight }}
      weight: {{ .weight }}
      {{- end }}
      {{- if .group }}
      group: {{ .group }}
      {{- end }}
      {{- if .kind }}
      kind: {{ .kind }}
      {{- end }}
      {{- if .namespace }}
      namespace: {{ .namespace }}
      {{- end }}
    {{- end }}
    {{- else }}
    backendRefs:
    - name: {{ $fullNameApp }}
      port: {{ $svcPortApp }}
    {{- end }}
  {{- end }}
  {{- else }}
  {{/* Default rule when no rules specified */}}
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: "/"
    backendRefs:
    - name: {{ $fullNameApp }}
      port: {{ $svcPortApp }}
  {{- end }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "helper.component.grpcroute" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $component := include "helper.component.values" (dict "root" $root "name" $name) | fromYaml -}}
{{- if $root.Values.enabled }}
{{- if $component.grpcRoute.enabled -}}
{{- $fullNameApp := include "helper.componentFullname" (dict "root" $root "componentName" $name) -}}
{{- $svcPortApp := $component.service.port -}}
apiVersion: gateway.networking.k8s.io/v1
kind: GRPCRoute
metadata:
  name: {{ include "helper.componentFullname" (dict "root" $root "componentName" $name) }}
  labels: {{- (include "helper.labels" (dict "root" $root "componentName" $name)) | nindent 4 }}
  {{- if $component.grpcRoute.labels }}
    {{- toYaml $component.grpcRoute.labels | nindent 4 }}
  {{- end }}
  {{- if $component.grpcRoute.annotations }}
  annotations:
    {{- tpl (toYaml $component.grpcRoute.annotations) $root | nindent 4 }}
  {{- end }}
spec:
  {{- if $component.grpcRoute.parentRefs }}
  parentRefs:
  {{- range $component.grpcRoute.parentRefs }}
  - name: {{ .name }}
    {{- if .namespace }}
    namespace: {{ .namespace }}
    {{- end }}
    {{- if .sectionName }}
    sectionName: {{ .sectionName }}
    {{- end }}
    {{- if .port }}
    port: {{ .port }}
    {{- end }}
    {{- if .group }}
    group: {{ .group }}
    {{- end }}
    {{- if .kind }}
    kind: {{ .kind }}
    {{- end }}
  {{- end }}
  {{- end }}
  {{- if $component.grpcRoute.hostnames }}
  hostnames:
  {{- range $component.grpcRoute.hostnames }}
  - {{ . | quote }}
  {{- end }}
  {{- end }}
  {{- if $component.grpcRoute.rules }}
  rules:
  {{- range $component.grpcRoute.rules }}
  {{- if .matches }}
  - matches:
    {{- range .matches }}
    {{- if .method }}
    - method:
        {{- if .method.type }}
        type: {{ .method.type }}
        {{- end }}
        {{- if .method.service }}
        service: {{ .method.service }}
        {{- end }}
        {{- if .method.method }}
        method: {{ .method.method }}
        {{- end }}
    {{- end }}
      {{- if .headers }}
      headers:
      {{- range .headers }}
      - type: {{ .type | default "Exact" }}
        name: {{ .name }}
        value: {{ .value }}
      {{- end }}
      {{- end }}
    {{- end }}
    {{- end }}
    {{- if .filters }}
    filters:
    {{- toYaml .filters | nindent 4 }}
    {{- end }}
    {{- if .backendRefs }}
    backendRefs:
    {{- range .backendRefs }}
    - name: {{ .name | default $fullNameApp }}
      port: {{ .port | default $svcPortApp }}
      {{- if .weight }}
      weight: {{ .weight }}
      {{- end }}
      {{- if .group }}
      group: {{ .group }}
      {{- end }}
      {{- if .kind }}
      kind: {{ .kind }}
      {{- end }}
      {{- if .namespace }}
      namespace: {{ .namespace }}
      {{- end }}
    {{- end }}
    {{- else }}
    backendRefs:
    - name: {{ $fullNameApp }}
      port: {{ $svcPortApp }}
    {{- end }}
  {{- end }}
  {{- else }}
  {{/* Default rule when no rules specified - routes all gRPC traffic */}}
  rules:
  - backendRefs:
    - name: {{ $fullNameApp }}
      port: {{ $svcPortApp }}
  {{- end }}
{{- end }}
{{- end }}
{{- end -}}
