# Demos

Each folder here is one demo you can run on the built lab, with
everything it needs: a README that takes you from nothing to the end of
the demo, and the scripts and manifests it runs.

| Demo | What it shows |
|---|---|
| [pen-test-dashboard](pen-test-dashboard) | The music store's security layers on the Grafana board "Pen test": take the Antrea default deny and the Avi WAF out, the attacks get through, put them back |
| [pen-test-manual](pen-test-manual) | The same layers by hand: an attacker pod next to the store, its five attacks blocked by the default deny and the Avi WAF, with the results in the terminal |

## What a demo folder holds

- `README.md`, in this order:
  1. What the demo shows and which layers it touches. No persona
     roles: anyone with the access in step 2 runs it.
  2. **Before the demo**: the tools, the access, and the vcf contexts
     the presenter needs, made with their own login. Say which
     Supervisor Namespace each context must point at, and how to find
     its generated suffix.
  3. **Run the demo**: numbered steps, each with the command, what it
     prints, and what the audience sees.
  4. **After the demo**: how to put the lab back, and how to check it.
  5. **Troubleshooting**: the errors a presenter is likely to meet.
- The scripts the presenter runs, and any manifests only the demo uses.

Scripts take the context they need as an argument. They never default
to one person's context, and they print no secret.

What runs all the time is not here: it is synced by Argo CD from
`gitops/`, like the pen test's probes in
`gitops/music-store-platform/pen-test.yaml`. A demo folder holds only
what a person starts.
