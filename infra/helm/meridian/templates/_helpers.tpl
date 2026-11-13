{{/* Tarayıcının gördüğü host (appUrl'dan). */}}
{{- define "meridian.host" -}}
{{- (urlParse .Values.appUrl).host -}}
{{- end -}}

{{- define "meridian.issuer" -}}
{{- printf "%s/auth/realms/meridian" (trimSuffix "/" .Values.appUrl) -}}
{{- end -}}

{{- define "meridian.image" -}}
{{- printf "%s%s:%s" .root.Values.image.registry .repository .root.Values.image.tag -}}
{{- end -}}

{{- define "meridian.labels" -}}
app.kubernetes.io/name: meridian
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
app.kubernetes.io/part-of: meridian
{{- end -}}

{{- define "meridian.selector" -}}
app.kubernetes.io/name: meridian
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Pod güvenlik bağlamı: root olmayan kullanıcı. */}}
{{- define "meridian.podSecurity" -}}
securityContext:
  runAsNonRoot: true
  runAsUser: {{ .uid }}
  runAsGroup: {{ .uid }}
  fsGroup: {{ .uid }}
  seccompProfile: {type: RuntimeDefault}
{{- end -}}

{{- define "meridian.containerSecurity" -}}
securityContext:
  allowPrivilegeEscalation: false
  capabilities: {drop: [ALL]}
{{- end -}}

{{- define "meridian.secretEnv" -}}
- name: {{ .name }}
  valueFrom:
    secretKeyRef: {name: {{ .root.Values.secretName }}, key: {{ .name }}}
{{- end -}}

{{/* İzleme ortam değişkenleri (ADR-0017); toplayıcı yalnızca observability.enabled ile vardır. */}}
{{- define "meridian.otelEnv" -}}
- name: OTEL_EXPORT
  value: {{ .Values.observability.enabled | quote }}
- name: OTEL_ENDPOINT
  value: http://otel-collector:4318
- name: OTEL_SAMPLING
  value: {{ .Values.observability.sampling | quote }}
- name: DEPLOYMENT_ENVIRONMENT
  value: {{ include "meridian.host" . | quote }}
{{- end -}}
