"""The five Campus Customs agents. Any agent can delegate to any other."""

from backend.agents import accounting, boss, customer_service, facilities, inventory

AGENT_MODULES = {
    "boss": boss,
    "inventory": inventory,
    "accounting": accounting,
    "facilities": facilities,
    "customer_service": customer_service,
}
