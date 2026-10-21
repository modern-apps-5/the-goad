1. - Platform team applies a VKS Cluster to vSphere namespace via Gitops creating the cluster
2. - Platform team layers on secops ACNP in the securityops tier priority 50 [secops-policy-1.yaml](/app/music-store/anp/secops-policy-1.yaml) applied to all Namespaces allowing Ingress port and kube-dns traffic.  It also PASSES rule evaluation down to the Application Tier (I thought) with an Action of PASS
3. - Platform team layers on [baseline-deny-policy-3.yaml](/app/music-store/anp/baseline-deny-policy-3.yaml) in baseline tier with priority 50 dropping Ingress traffic. This should break the application or if we deploy the application not allow it to work.
4. - Application Team applies their application manifests and [application-policy-2.yaml](/app/music-store/anp/application-policy-2.yaml) in the application tier with priority 100-106 for various microservice components.  I would expect this to allow the traffic I told it in the ruleset but the baseline would catch anything I did not specifically allow in Step 3.

NOTE: Right now applying the baseline-deny-policy-3.yaml breaks all application traffic.

NOTE: This is what I see from policy perspective.
```bash

> k get acnp
NAME                    TIER          PRIORITY   DESIRED NODES   CURRENT NODES   AGE
baseline-default-drop   baseline      250        3               3               7s
secops-pass-prod        securityops   50         4               4               52m


> k get anp
NAME                       TIER          PRIORITY   DESIRED NODES   CURRENT NODES   AGE
allow-client-to-service    application   100        3               3               51m
cart-service-policy        Application   106        1               1               51m
chat-service-policy        Application   100        1               1               51m
music-store-1-policy       Application   104        1               1               51m
order-service-policy       Application   103        1               1               51m
postgres-policy            Application   105        1               1               51m
traffic-generator-policy   Application   102        1               1               51m
users-service-policy       Application   101        1               1               51m

```
