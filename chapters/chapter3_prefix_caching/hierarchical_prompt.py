"""
Hierarchical prompt builder for Chapter 3 — Prefix Caching demo.

build_agent_prompt(user_query) returns OpenAI-format messages where
the system content (GLOBAL_SYSTEM + TENANT_POLICY + TOOL_DESCRIPTIONS)
is IDENTICAL across all calls — ~3,600 tokens of shared prefix.

Only the user_query varies across requests, allowing prefix caching to
reuse the KV state for the shared prefix.
"""
from __future__ import annotations

from pathlib import Path

_PREFIX_FILE = Path(__file__).parent / "shared_prefix_3600.txt"
_CACHED_PREFIX: str | None = None


def _load_prefix() -> str:
    global _CACHED_PREFIX
    if _CACHED_PREFIX is None:
        _CACHED_PREFIX = _PREFIX_FILE.read_text(encoding="utf-8")
    return _CACHED_PREFIX


# The conversation history is fixed across requests too (~400 tokens)
CONVERSATION_HISTORY = """User: Can you help me find the onboarding checklist for new engineering hires?
Assistant: I found it. The onboarding checklist is stored in the Engineering Wiki under "People Ops > Onboarding > Engineering Track." It includes environment setup, access provisioning, and a 30/60/90 day plan. Would you like me to fetch the full document?
User: Yes, please fetch it.
Assistant: I've retrieved the document. It has 12 items in the first week, covering account setup, codebase walkthrough, and introductory pairing sessions. The document was last updated 3 weeks ago by the Engineering Manager. Do you want me to summarize the first-week items or the full 90-day plan?
User: Just the first week.
Assistant: First week (7 items): (1) Provision all accounts — GitHub, Jira, Slack, AWS. (2) Complete security training module. (3) Set up local development environment using the eng-bootstrap script. (4) Read the system architecture doc (link in wiki). (5) Shadow an on-call rotation for one day. (6) Complete two pairing sessions with a senior engineer. (7) Attend the weekly all-hands meeting."""

USER_QUERIES = [
    "What tools should I request access to on my first day?",
    "How do I escalate a P0 incident during the on-call rotation?",
    "Where is the architecture decision record for the data pipeline?",
    "What is the process for getting a new API key for the internal ML platform?",
    "How do I request a code review from the platform team?",
    "What is the SLA for the internal Slack bot responding to IT tickets?",
    "Where are the runbooks for the inference infrastructure stored?",
    "How do I add a new tenant to the NimbusAI platform?",
    "What monitoring alerts are set up for the recommendation service?",
    "How do I access the A/B testing dashboard for model evaluations?",
    "Where can I find the data retention policy for model outputs?",
    "What is the approval process for deploying to production on Fridays?",
    "How do I set up alert routing in PagerDuty for my team?",
    "What is the process for requesting a GPU quota increase on RunPod?",
    "Where are the integration test results stored for the last sprint?",
]


def build_agent_prompt(user_query: str) -> list[dict]:
    """
    Returns OpenAI-compatible messages with:
      - system: shared prefix (~3,600 tokens, identical across all calls)
      - assistant: conversation history (~400 tokens, identical)
      - user: user_query (~30 tokens, varies per call)

    The system + assistant content forms the cacheable prefix.
    """
    system_content = _load_prefix()
    return [
        {"role": "system", "content": system_content},
        {"role": "assistant", "content": CONVERSATION_HISTORY},
        {"role": "user", "content": user_query},
    ]


def get_user_query(i: int) -> str:
    return USER_QUERIES[i % len(USER_QUERIES)]
