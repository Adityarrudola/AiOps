{{- define "aiops.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "aiops.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
