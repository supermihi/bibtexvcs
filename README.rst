The BibTeX VCS Package
======================

`BibTeX VCS` is a python package that helps sharing a BibTeX_ database with a  control system (VCS).
It is optimized for usage together with the JabRef_ BibTeX manager.


Introduction
------------
Collecting and managing bibliography information can be cumbersone. Therefore it makes sense to maintain
a single BibTeX database within a research group that focusses on the same topic and thus has a lot of
common bibliography. Furthermore, tools like JabRef_ allow to link PDF documents to BibTeX entries, turning
the ``bib`` file into a valuable literature database.

Since the ``bib`` file is text-based, it can be efficiently put under revision control. However, such a database
used by several people over a long period of time tends to become messy. Furthermore, most people are not
trained, and even less interested in, the usage of VCS systems.

`BibTeX VCS` resolves these issues by automating the most common VCS operations and providing a minimalist,
platform-independent GUI. It allows to defined a number of `database checks` that are run prior to each
commit operation, in order to enforce consistency and a defined referencing style within the database.
For example, there is a check that ensures that the documents linked to BibTeX entries actually exist, and
each PDF document is linked to by at least one BibTeX entry.

Installation
------------
`BibTeX VCS` needs a `Python <Python>`_ interpreter. Python version 3.x is recommended, but the package will also
run with Python 2.7. The easiest way to install it is using pip_::

   pip3 install bibtexvcs

If you want to use the GUI_, you need to install either PyQt4_, PyQt5_, or PySide_. For exporting
the database using a template, Jinja2_ is an additional requirement.

Repository (Database) Layout
----------------------------
A `BibTeX VCS` database consists of a repository of supported type (currently, this is only Mercurial_, but
other VCS systems are easy to implement). The toplevel directory of the repository, henceforth called the
`database directory`, must contain a file named ``bibtexvcs.conf`` which consists of "``key = value``"-type
configuration options. The possible configuration options are:

``bibfile``
   name of the BibTeX database file. Defaults to ``references.bib``.

``documents``
   directory in which PDF (and other) documents that are referenced from BibTeX entries are
   placed. Default: ``Documents``.

``name`` (optional)
   A title for the database (e.g., `Literature of the Optimization Research Group`).

.. _journalstxt:

``journals`` 
   Name of the journals file. See `Journal Abbreviations`_. Default: ``journals.txt``.
   
``publicLink`` (optional)
   URL of a web page containing an exported version of the database (see Exporting_). 

GUI
---

`BibTeX VCS` includes a graphical user interface (GUI), based on Qt_, that allows to perform the most
commont tasks without having to use the command line:

- clone a database from a remote repository,
- update the local checkout of a repository
- viewing and editing journal abbreviations,
- commiting changes into the remote repository, thereby running database checks,
- open the BibTeX_ database with JabRef_,
- :ref:`export <Exporting>` the database to HTML using the default template,
- open the public HTML export (if it exists). 

The GUI is run by the ``btvcs`` command that is installed automatically with the package. Alternatively,
you can directly run the gui module by invoking::

   python3 -m bibtexvcs.gui
   
The GUI needs either PyQt5_, PyQt4_ or PySide_ for Python 3 to be installed.

Journal Abbreviations
---------------------
Depending on the publisher's demands, journal names in the references list should either be abbreviated
(like in `J. Comput. Syst. Sci.`) or not (`Journal of Computer and Journal Sciences`). Since BibTeX does
not support specifying both versions in the same entry, a common workaround is the use of `macros`. In the
BibTeX file, the ``journal`` entry is defined as a macro reference (say, `J_COM_SS`). Then, there are two
additional BibTeX files, one containing macro (string) definitions for the full, one for the abbreviated
journal names. In your paper, you then include the main bibfile and the corresponding macro definition
file. That way, the version of journal names does not have to be specified in the shared database.

In order to ease handling of journal abbreviations, `BibTeX VCS` uses a simple :ref:`configuration file <journalstxt>`
that contains, for each journal, an entry of the form::
   
   [MACRO_NAME]
   full = Full Journal Name
   abbr = Abbrev. J. Name

The GUI_ allows to conveniently edit journal macros in a table structure.

`BibTeX VCS` then automatically generates the BibTeX files containing macro definitions for full and
abbreviated journal names, respectively. They will be named like the main bibfile but augmented by ``_full``
and ``_abbr``, respectively. 

.. _Exporting:

Exporting
---------
A `BibTeX VCS` database can be exported to HTML and other formats using the Jinja2_ templating engine.
A default template creates a searchable HTML table containing, for each entry, the most common fields, 
places a link to the PDF document if that exists, and allows to view the raw BibTeX source for each entry.
If you upload the result to a public web space, the database can be used in read-only mode without having
access to the version control system, and without having to install the `BibTeX VCS` package.



.. _BibTeX : http://www.bibtex.org
.. _JabRef: http://jabref.sourceforge.net
.. _Mercurial: http://mercurial.selenic.com
.. _Jinja2: http://jinja.pocoo.org
.. _Qt: http://qt-project.org
.. _PyQt5: http://riverbankcomputing.com/software/pyqt/download5
.. _PyQt4: http://riverbankcomputing.com/software/pyqt/download
.. _PySide: http://qt-project.org/wiki/PySide 
.. _Python: http://www.python.org
.. _pip: http://www.pip-installer.org