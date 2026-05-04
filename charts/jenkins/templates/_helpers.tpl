{{- define "jenkins.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "jenkins.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
