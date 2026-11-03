"""Mission: segment powers and the two-phase flight time.

The models are imported lazily so that the project schema can import this package
without a circular import.
"""


def __getattr__(name: str):
    if name in ("SegmentPower", "SpeedSweep"):
        from predimrc_wrapper.mission import powers  # noqa: PLC0415

        return getattr(powers, name)
    raise AttributeError(name)
