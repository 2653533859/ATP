{{/* 通用命名 helper */}}
{{- define "atp.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "atp.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "atp.componentLabels" -}}
{{ include "atp.labels" . }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Allow production to bind an ExternalSecret/SOPS-managed Secret. */}}
{{- define "atp.secretName" -}}
{{- if .Values.secret.existingName -}}
{{ .Values.secret.existingName }}
{{- else -}}
{{ include "atp.fullname" . }}-secret
{{- end -}}
{{- end -}}
