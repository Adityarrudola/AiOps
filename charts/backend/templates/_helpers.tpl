{{- define "backend.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "backend.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
