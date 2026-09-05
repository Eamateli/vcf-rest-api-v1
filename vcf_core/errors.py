"""Exceptions raised by the VCF domain layer."""


class VcfError(Exception):
    """Base for every error this package raises."""


class MalformedVcfError(VcfError):
    """A line or header does not match the VCF structure."""
