## 🔴 IaC Security Review: `bad.yaml`

**File Summary**: Kubernetes Deployment with multiple critical security misconfigurations.

---

### **CRITICAL Issues** (Real Risk)

1. **Privileged Container Execution**  
   *Risk*: Container runs with full kernel capabilities, allowing escape and host compromise.  
   *Fix*: Remove `privileged: true` from securityContext.

2. **Running as Root User**  
   *Risk*: Container process has unlimited root privileges; any vulnerability becomes complete system compromise.  
   *Fix*: Set `runAsNonRoot: true` and specify `runAsUser: 1000` (non-root UID).

3. **Mutable Image Tag (`latest`)**  
   *Risk*: Deployment will pull arbitrary image versions at runtime—unpredictable behavior and potential injection of malicious code.  
   *Fix*: Replace `nginx:latest` with a specific pinned version: `nginx:1.25.3@sha256:...` (include digest for immutability).

---

### **HIGH Issues**

4. **Missing Resource Limits**  
   *Risk*: Container can consume all cluster CPU/memory, causing DoS and evicting other pods.  
   *Fix*: Add to container spec:
   ```yaml
   resources:
     requests:
       cpu: 100m
       memory: 128Mi
     limits:
       cpu: 500m
       memory: 512Mi
   ```

5. **No Health Checks (Readiness/Liveness Probes)**  
   *Risk*: Failed containers remain in `Running` state; traffic routes to dead endpoints causing cascading failures.  
   *Fix*: Add:
   ```yaml
   livenessProbe:
     httpGet:
       path: /
       port: 80
     initialDelaySeconds: 10
     periodSeconds: 10
   readinessProbe:
     httpGet:
       path: /
       port: 80
     initialDelaySeconds: 5
     periodSeconds: 5
   ```

---

### **MEDIUM Issues**