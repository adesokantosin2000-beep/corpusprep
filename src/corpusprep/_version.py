"""
corpusprep._version
===================

The single source of truth for the version, in a module of its own so that
nothing has to import the package to read it.

It lives here because the alternative created a circular import: `report.py`
needs the version, `__init__.py` imports `report`, and the version was defined
below that import.

Before this existed, three copies disagreed. The preprocessing log said 0.1.0
while the web application said 0.2.0, so two runs of the same tool produced
logs claiming different provenance. In software whose entire proposition is
that its output can be audited, that is a defect rather than an untidiness.

`build/build.py` reads this file textually and injects the value into the web
application, so the package and the page cannot drift apart.
"""

__version__ = "0.6.0"
