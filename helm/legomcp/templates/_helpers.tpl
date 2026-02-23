{{/*
LegoMCP Helm Chart Helper Templates
PhD-Level Manufacturing Platform
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "legomcp.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "legomcp.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "legomcp.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "legomcp.labels" -}}
helm.sh/chart: {{ include "legomcp.chart" . }}
{{ include "legomcp.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: legomcp
{{- end }}

{{/*
Selector labels
*/}}
{{- define "legomcp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "legomcp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "legomcp.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "legomcp.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Dashboard labels
*/}}
{{- define "legomcp.dashboard.labels" -}}
{{ include "legomcp.labels" . }}
app.kubernetes.io/component: dashboard
{{- end }}

{{/*
Dashboard selector labels
*/}}
{{- define "legomcp.dashboard.selectorLabels" -}}
{{ include "legomcp.selectorLabels" . }}
app.kubernetes.io/component: dashboard
{{- end }}

{{/*
Worker labels
*/}}
{{- define "legomcp.worker.labels" -}}
{{ include "legomcp.labels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
Worker selector labels
*/}}
{{- define "legomcp.worker.selectorLabels" -}}
{{ include "legomcp.selectorLabels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
ML Worker labels
*/}}
{{- define "legomcp.mlWorker.labels" -}}
{{ include "legomcp.labels" . }}
app.kubernetes.io/component: ml-worker
{{- end }}

{{/*
ML Worker selector labels
*/}}
{{- define "legomcp.mlWorker.selectorLabels" -}}
{{ include "legomcp.selectorLabels" . }}
app.kubernetes.io/component: ml-worker
{{- end }}

{{/*
Scheduler labels
*/}}
{{- define "legomcp.scheduler.labels" -}}
{{ include "legomcp.labels" . }}
app.kubernetes.io/component: scheduler
{{- end }}

{{/*
Scheduler selector labels
*/}}
{{- define "legomcp.scheduler.selectorLabels" -}}
{{ include "legomcp.selectorLabels" . }}
app.kubernetes.io/component: scheduler
{{- end }}

{{/*
Slicer labels
*/}}
{{- define "legomcp.slicer.labels" -}}
{{ include "legomcp.labels" . }}
app.kubernetes.io/component: slicer
{{- end }}

{{/*
Slicer selector labels
*/}}
{{- define "legomcp.slicer.selectorLabels" -}}
{{ include "legomcp.selectorLabels" . }}
app.kubernetes.io/component: slicer
{{- end }}

{{/*
Get PostgreSQL host
*/}}
{{- define "legomcp.postgresql.host" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "%s-postgresql" (include "legomcp.fullname" .) }}
{{- else }}
{{- .Values.externalPostgresql.host }}
{{- end }}
{{- end }}

{{/*
Get PostgreSQL port
*/}}
{{- define "legomcp.postgresql.port" -}}
{{- if .Values.postgresql.enabled }}
{{- "5432" }}
{{- else }}
{{- .Values.externalPostgresql.port | toString }}
{{- end }}
{{- end }}

{{/*
Get PostgreSQL database
*/}}
{{- define "legomcp.postgresql.database" -}}
{{- if .Values.postgresql.enabled }}
{{- .Values.postgresql.auth.database }}
{{- else }}
{{- .Values.externalPostgresql.database }}
{{- end }}
{{- end }}

{{/*
Get PostgreSQL username
*/}}
{{- define "legomcp.postgresql.username" -}}
{{- if .Values.postgresql.enabled }}
{{- .Values.postgresql.auth.username }}
{{- else }}
{{- .Values.externalPostgresql.username }}
{{- end }}
{{- end }}

{{/*
Get Redis host
*/}}
{{- define "legomcp.redis.host" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis-master" (include "legomcp.fullname" .) }}
{{- else }}
{{- .Values.externalRedis.host }}
{{- end }}
{{- end }}

{{/*
Get Redis port
*/}}
{{- define "legomcp.redis.port" -}}
{{- if .Values.redis.enabled }}
{{- "6379" }}
{{- else }}
{{- .Values.externalRedis.port | toString }}
{{- end }}
{{- end }}

{{/*
Database URL
*/}}
{{- define "legomcp.databaseUrl" -}}
{{- printf "postgresql://%s:$(DATABASE_PASSWORD)@%s:%s/%s" (include "legomcp.postgresql.username" .) (include "legomcp.postgresql.host" .) (include "legomcp.postgresql.port" .) (include "legomcp.postgresql.database" .) }}
{{- end }}

{{/*
Redis URL
*/}}
{{- define "legomcp.redisUrl" -}}
{{- if .Values.redis.auth.enabled }}
{{- printf "redis://:$(REDIS_PASSWORD)@%s:%s/0" (include "legomcp.redis.host" .) (include "legomcp.redis.port" .) }}
{{- else }}
{{- printf "redis://%s:%s/0" (include "legomcp.redis.host" .) (include "legomcp.redis.port" .) }}
{{- end }}
{{- end }}

{{/*
Celery broker URL
*/}}
{{- define "legomcp.celeryBrokerUrl" -}}
{{- if .Values.redis.auth.enabled }}
{{- printf "redis://:$(REDIS_PASSWORD)@%s:%s/1" (include "legomcp.redis.host" .) (include "legomcp.redis.port" .) }}
{{- else }}
{{- printf "redis://%s:%s/1" (include "legomcp.redis.host" .) (include "legomcp.redis.port" .) }}
{{- end }}
{{- end }}

{{/*
Image pull secrets
*/}}
{{- define "legomcp.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Full image reference
*/}}
{{- define "legomcp.image" -}}
{{- $registry := .Values.global.imageRegistry | default "" }}
{{- $repository := .image.repository }}
{{- $tag := .image.tag | default .Chart.AppVersion }}
{{- if $registry }}
{{- printf "%s/%s:%s" $registry $repository $tag }}
{{- else }}
{{- printf "%s:%s" $repository $tag }}
{{- end }}
{{- end }}

{{/*
Common environment variables
*/}}
{{- define "legomcp.commonEnv" -}}
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "legomcp.fullname" . }}-secrets
      key: postgresql-password
{{- if .Values.redis.auth.enabled }}
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "legomcp.fullname" . }}-secrets
      key: redis-password
{{- end }}
- name: FLASK_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "legomcp.fullname" . }}-secrets
      key: flask-secret-key
- name: JWT_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "legomcp.fullname" . }}-secrets
      key: jwt-secret-key
- name: DATABASE_URL
  value: {{ include "legomcp.databaseUrl" . | quote }}
- name: REDIS_URL
  value: {{ include "legomcp.redisUrl" . | quote }}
- name: CELERY_BROKER_URL
  value: {{ include "legomcp.celeryBrokerUrl" . | quote }}
{{- end }}

{{/*
Pod security context
*/}}
{{- define "legomcp.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 1000
runAsGroup: 1000
fsGroup: 1000
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Container security context
*/}}
{{- define "legomcp.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop:
    - ALL
{{- end }}

{{/*
Liveness probe
*/}}
{{- define "legomcp.livenessProbe" -}}
livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
{{- end }}

{{/*
Readiness probe
*/}}
{{- define "legomcp.readinessProbe" -}}
readinessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
{{- end }}

{{/*
Startup probe
*/}}
{{- define "legomcp.startupProbe" -}}
startupProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 30
{{- end }}
