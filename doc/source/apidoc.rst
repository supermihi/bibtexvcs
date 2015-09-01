****************************
BibTeX VCS API Documentation
****************************

The :mod:`bibtexvcs` package is split into several modules, each of which is responsible for a
specific task or level of abstraction:

- :mod:`bibtexvcs.parser` contains low-methods for parsing a ``.bib`` file.
- :mod:`bibtexvcs.bibfile` uses the parsed results for an object-oriented representation of its
  contents. These two modules are generic in such that they could be used without the rest of
  bibtexvcs.
- :mod:`bibtexvcs.database` contains the higher-level definitions related to the concept of a
  *BibTeX VCS database*, consisting of a bib file and several supplementary configuration files
  located in a version controlled directory.
- :mod:`bibtexvcs.vcs` implements VCS access for different VCS systems.
- :mod:`bibtexvcs.checks` contains the logic for running automated database checks.
- :mod:`bibtexvcs.config` considers database-independent configuration,
  like a list of recent databases or VCS auth information.

Main Package Module
===================

.. automodule:: bibtexvcs
   :members:

The ``bibfile`` Module
======================

.. automodule:: bibtexvcs.bibfile
   :members:

The ``database`` Module
=======================

.. automodule:: bibtexvcs.database
   :members:

The ``vcs`` Module
==================

.. automodule:: bibtexvcs.vcs
   :members:

.. _checksModule:

Consistency Checks
==================

The module :mod:`bibtexvcs.checks` supports definition of automated database consistency checks that
are performed prior to a VCS commit.

.. automodule:: bibtexvcs.checks
   :members:

Configuration Module
====================

.. automodule:: bibtexvcs.config
   :members:

BibTeX Parser Module
====================

.. automodule:: bibtexvcs.parser
   :members:
