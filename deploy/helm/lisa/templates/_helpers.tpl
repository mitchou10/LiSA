{{/* Expand the chart name. */}}
{{- define "lisa.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Fully qualified app name. */}}
{{- define "lisa.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{/* Common labels. */}}
{{- define "lisa.labels" -}}
app.kubernetes.io/name: {{ include "lisa.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{/* Per-component selector labels. Call with (dict "ctx" . "component" "backend"). */}}
{{- define "lisa.selectorLabels" -}}
app.kubernetes.io/name: {{ include "lisa.name" .ctx }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Secret name to use (existing or generated). */}}
{{- define "lisa.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- printf "%s-secrets" (include "lisa.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/* Resolve an image string for a component sub-map (repository/tag/pullPolicy). */}}
{{- define "lisa.image" -}}
{{- $tag := .image.tag | default .global.imageTag -}}
{{- printf "%s:%s" .image.repository $tag -}}
{{- end -}}

{{/* DATABASE_URL: external override or the bundled postgres service. */}}
{{- define "lisa.databaseUrl" -}}
{{- if .Values.postgres.externalUrl -}}
{{- .Values.postgres.externalUrl -}}
{{- else -}}
{{- $a := .Values.postgres.auth -}}
{{- printf "postgresql+asyncpg://%s:%s@%s-postgres:%v/%s" $a.username $a.password (include "lisa.fullname" .) (.Values.postgres.service.port | int) $a.database -}}
{{- end -}}
{{- end -}}

{{/* REDIS_URL: external override or the bundled redis service. */}}
{{- define "lisa.redisUrl" -}}
{{- if .Values.redis.externalUrl -}}
{{- .Values.redis.externalUrl -}}
{{- else -}}
{{- printf "redis://%s-redis:%v/0" (include "lisa.fullname" .) (.Values.redis.service.port | int) -}}
{{- end -}}
{{- end -}}
