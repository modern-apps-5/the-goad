"""The three specialists. Each returns the prompt the orchestrator sends to Qwen."""


def orchestrator_prompt(packet: str) -> str:
    return (
        "You are the Incident response agent. Turn this evidence into a short brief: "
        "what failed, since when, and which services are involved. Do not choose a fix.\n\n"
        + packet
    )


def logs_prompt(brief: str, packet: str) -> str:
    return (
        "You are the K8s diagnostic agent. From this brief and evidence, say what the logs show. "
        "Three short sentences.\n\n"
        + brief
        + "\n"
        + packet[:2500]
    )


def platform_prompt(brief: str, pods: str, events: str) -> str:
    return (
        "You are the K8s diagnostic agent. From this evidence, say what changed in the cluster. "
        "Three short sentences.\n\n"
        + brief
        + "\n"
        + pods[:1500]
        + "\n"
        + events[:1500]
    )


def writer_prompt(choice: str, route: str, brief: str, logs_note: str, platform_note: str) -> str:
    return (
        "You are the writer. Produce the ticket enrichment. Include a summary, the likely cause, "
        "the evidence, and the suggested fix. "
        f"Jev chose {choice}. Route text: {route}\n\n"
        f"Brief:\n{brief}\n\nLogs:\n{logs_note}\n\nPlatform:\n{platform_note}"
    )
