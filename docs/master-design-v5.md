# The Grandmother of All Demos (GOAD)

Master Design & Walkthrough Document V5

Personas: Niran Evenchen, William Arroyo, Ronak Mukhopadhyay, Chris McCain, Thomas Kraus

This document outlines the blueprint for "The Grandmother of All
Demos" (GOAD). The objective is to show the full, integrated power
of the VMware Cloud Foundation (VCF) stack across the application
lifecycle. Aimed at customers and internal field teams, the demo
illustrates where every component fits and how different enterprise
stakeholders interact with the platform.

Transcribed 2026-10-01 from the current plan. A few lines were cut
off at the edge of a page. Those spots are marked.

## 1. The Personas and Responsibilities

The demo is driven by four personas. The point is the line between
infrastructure operations and platform engineering.

| Persona | Core responsibilities | Demo interactions |
|---|---|---|
| Developer & Architect | Building the application architecture, writing code, and pushing updates. The parenthetical after this title was cut off in the source. | Deploying the Kubernetes app, integrating the AI chat agent via Tanzu, configuring granular app-level security rules. |
| Security Admin | Securing the application, ensuring compliance, and responding to threats. | Managing vDefend DFW, Antrea centralized rules, Avi WAF/LB policies, and AgentMinder configurations. |
| Cloud Admin / Ops | Managing VCF, physical and virtual infrastructure troubleshooting, and resource provisioning. | Managing VCF infrastructure up to the Supervisor cluster, creating vSphere Namespaces (the strict demarcation line), allocating GPU tenancy via VCF Automation. |
| Platform Engineer | Managing Kubernetes, Tanzu, CI/CD, patching, and platform policies. | Deploying VKS clusters, managing Istio service mesh, configuring OPA admission controllers, and using Headlamp for in-cluster ops. |

## 2. The Application Architecture: Metal Music Store AI

The core application is based on the existing music-store-ai
workload, a retail application split into small services. It uses
Kubernetes, traditional VMs, data services, and AI services.

- **Cloud-native frontend and core microservices.** Deployed as
  containers on Kubernetes (VKS). Includes the Store, Cart, Orders,
  and a simulated Traffic Generator.
- The next architecture bullets were on a page that started later.
  What is visible there is below.
- **Modern data service.** Stateful data services running natively
  on the Supervisor, for example caching for the cart or chat
  history. We will not run vSphere pods on the Supervisor.
- **Users service on a VM.** The users microservice (admin login)
  runs as a traditional VM via the VM Service on the Supervisor,
  sized with a TuneD profile.
- **Backend database via DSM.** The PostgreSQL `music_store`
  database is provisioned and managed by VMware Data Services
  Manager (DSM) on a dedicated Kubernetes cluster.
- **Agentic AI chat (the Metal Oracle).** An agentic chat interface
  on Tanzu, with Model Context Protocol (MCP) access to the music
  store inventory and order data.
- **Avi load balancer and AKO.** Layer 4-7 load balancing, WAF, and
  API gateway functions. The plan says this replaces the AgentMinder
  gateway for model routing.
- **AgentMinder.** Agent authentication, and security policy
  enforced through Avi service engines.

## 3. App Modifications and Gap Analysis

The existing music-store-ai application needs these changes before
it can carry the GOAD story.

- **Agentic chat service.** The current repo has no backend chat
  service (port 5005). Build one on Tanzu that uses local private
  models and MCP so the agent can take actions.
- **Database migration to DSM.** Move PostgreSQL out of a container
  and deploy it with DSM on a dedicated Kubernetes cluster.
- **Users service migration to a VM.** Deploy the existing users
  container as a virtual machine with the VM Service, to show
  VM-to-Kubernetes and TuneD.
- **AgentMinder.** The Metal Oracle sits behind Avi, acting as the
  AgentMinder gateway, for intent-based access control.
- **GitOps.** Wrap the Kustomize files in Terraform and Argo CD,
  integrated with VCF Automation.
- **Microsegmentation.** vDefend DFW and Antrea rules so only the
  Store service can reach the users VM, and lateral movement is
  blocked.

## 4. VCF Technology Stack and Integrations

### 4.1 Security and networking

- **vDefend DFW.** Layer 4 microsegmentation for the users VM.
- **vDefend Antrea.** Kubernetes microsegmentation with centralized
  rules and developer-driven controls.
- **vDefend SSP.** Distributed IDS/IPS for east-west traffic.

### 4.2 Platform engineering

- **VKS.** Kubernetes runtime for the microservices.
- **DSM.** Lifecycle, backup, and patching of the PostgreSQL
  database.
- **VM Service.** Lifecycle of the users VM next to the Kubernetes
  workloads.
- **Istio.** Traffic routing, observability, and mutual TLS.
- **OPA.** VCF Automation policy as an in-cluster admission
  controller.
- **Headlamp and VCF Operations.** Kubernetes monitoring and
  troubleshooting.

### 4.3 AI and data

1. **Tanzu runtime.** Hosts the Metal Oracle and its MCP connections.
2. **Private AI Services.** Retrieval-augmented generation against
   local models.
3. **Hardware acceleration.** Local GPU allocation managed as VCF
   Automation tenancy.
