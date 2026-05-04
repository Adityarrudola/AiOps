{{- define "load-generator.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "load-generator.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
