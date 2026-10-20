1. - Platform team applies a VKS Cluster to vSphere namespace via Gitops creating the cluster
2. - Platform team layers on secops ACNP in the securityops tier priority 50 [secops-policy-1.yaml](/app/music-store/anp/secops-policy-1.yaml) applied to all Namespaces allowing Ingress port and kube-dns traffic.  It also PASSES rule evaluation down to the Application Tier (I thought) with an Action of PASS
3. - Platform team layers on [baseline-deny-policy-3.yaml](/app/music-store/anp/baseline-deny-policy-3.yaml) in baseline tier with priority 50 dropping Ingress traffic. This should break the application or if we deploy the application not allow it to work.
4. - Application Team applies their application manifests and application-policy-2.yaml in the application tier with priority 100-106 for various microservice components.  I would expect this to allow the traffic I told it in the ruleset but the baseline would catch anything I did not specifically allow in Step 3.

NOTE: Trying to achieve a somewhat realistic scneario for platform admins creating security but giving devops/app teams some flexibility on a specific namespace.
