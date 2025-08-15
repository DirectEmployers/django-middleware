# django-middleware
Python package of reusable middleware for Django apps.

## Package Installation
The `django-middleware` package is hosted as a public repository on GitHub. Pinning this requirement from a release archive is recommended.

### django_middleware.healthchecks.HealthCheckMiddleware
Allow [Kubernetes liveness, readiness, and startup probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/) to make test your Django server container with `healthz/` and `readiness/` endpoints.

#### Installation
Add `HealthCheckMiddleware` to the Django settings module as early as is feasible, and especially before middleware that would access the databases (and cause an unpleasant server error). 

```python
MIDDLEWARE = (
    "django_middleware.healthchecks.HealthCheckMiddleware",
    # ...other middleware go after HealthCheckMiddleware...
)
```

For more details on the available properties and proper use of status probes, see:
- [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Probe API Reference](https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/pod-v1/#Probe)

Example usage:
```yaml
startupProbe:
  # Protect pods from restarts until they can initialize.
  # This should use the same command as livenessProbe.
  httpGet:
    path: /healthz
    port: 8000
  failureThreshold: 30
  periodSeconds: 10
livenessProbe:
  # Detect broken pods and restart them.
  httpGet:
    path: /healthz
    port: 8000
  initialDelaySeconds: 10
  failureThreshold: 2
  periodSeconds: 15
readinessProbe:
  # Detect when pods are able to receive requests/connections. 
  httpGet:
    path: /readiness
    port: 8000
  initialDelaySeconds: 10
  failureThreshold: 2
  periodSeconds: 10
```
