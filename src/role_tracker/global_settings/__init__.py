"""Cross-tenant (admin-managed) settings.

Today there's exactly one document: the global hidden-publishers
list. Lives in its own module so adding more admin-managed knobs
later (cost caps, banned-domains, model-routing rules, etc.)
slots in next to it without polluting users/.
"""
