class ServiceUnavailable(Exception):
    """A missing artifact, provider outage or invalid provider output; no raw body exposure."""


class StaleDocument(Exception):
    """The document was replaced/deleted during indexing."""
