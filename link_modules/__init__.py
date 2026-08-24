"""Link Modules package for all link generation commands:
- single_link: Single file links (/getlink)
- channel_batch: Channel message batch links (/batch)
- custom_batch: Custom multi-message batch links (/custom_batch)
- special_link: Advanced special links with expiry & whitelist (/special_link)
- universal_link: Universal direct media links (/universal_link)
"""

from link_modules import single_link
from link_modules import channel_batch
from link_modules import custom_batch
from link_modules import special_link
from link_modules import universal_link


def register_all_link_modules(client, is_master=False):
    """Register all link generation handlers for a Pyrogram client (Master or Clone)."""
    # Register handlers with prioritized group offsets
    custom_batch.register(client, base_group=-101 if is_master else -4)
    channel_batch.register(client, base_group=-102 if is_master else -3)
    special_link.register(client, base_group=-103 if is_master else -5)
    universal_link.register(client, base_group=-104 if is_master else -6)
    single_link.register(client, base_group=-100 if is_master else -2)
    return client


__all__ = [
    "single_link",
    "channel_batch",
    "custom_batch",
    "special_link",
    "universal_link",
    "register_all_link_modules",
]
