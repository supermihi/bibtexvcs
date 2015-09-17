#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014-2015 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

"""The :mod:`database <bibtexvcs.database>` module contains classes for managing a BibTeX VCS
database, which consists of a config file, a bib file, a documents directory, and a journals file.
"""
from __future__ import division, print_function, unicode_literals
import configparser, io, os, subprocess
from collections import OrderedDict
from os.path import join, exists, relpath

from pkg_resources import resource_string, resource_filename, get_distribution

from bibtexvcs.bibfile import BibFile, MacroReference
from bibtexvcs.vcs import VCSInterface

BTVCSCONF = 'bibtexvcs.conf'  # name of the configuration file


class DatabaseFormatError(Exception):
    """Raised on any problem in the database layout (unparsable config-file, non-existing
    bib file, etc.).
    """
    pass


class Database:
    """Represents a complete literature database.

    The database configuration is read from the file `bbibtexvcs.conf` and from the layout of the
    directory that file resides in.

    Parameters
    ----------
    directory : str
        Base path of the database.

    Attributes
    ----------
    directory : str
        Absolute path of the root directory of the literature database.
    bibfileName : str
        Name of the main bibtex database file.
    bibfile : :class:`BibFile`
        :class:`BibFile` object parsed from the bibtex file.
    journalsName : str
        Name of the journals file.
    journals : :class:`JournalsFile`
        :class:`JournalsFile` object read from the journals file.
    name : str
        Name of the database.
    documents : str
        Name of the documents directory (relative to :attr:`directory`).
    vcsType : ("git", "mercurial", "local")
        Type of the used VCS system.
    """

    def __init__(self, directory, vcs=None):
        self.directory = directory
        if exists(join(self.directory, '.git')):
            self.vcsType = 'git'
        elif exists(join(self.directory, '.hg')):
            self.vcsType = 'mercurial'
        else:
            self.vcsType = 'local'
        self._vcs = vcs
        self.reload()

    def reload(self):
        """(Re-)loads the database from filesystem."""
        parser = configparser.ConfigParser()
        try:
            with io.open(self.configPath, encoding='UTF-8') as f:
                confFile = f.read()
        except IOError:
            raise DatabaseFormatError('Invalid BibTeX VCS directory "{}": '
                                      'Configuration file bibtexvcs.conf not found.'
                                      .format(self.directory))
        # workaround because ConfigParser does not support sectionless entries
        try:
            parser.read_string("[root]\n" + confFile)
        except configparser.Error as e:
            raise DatabaseFormatError("Could not parse configuration file '{}':\n\n{}"
                                      .format(BTVCSCONF, e))
        config = parser['root']

        self.bibfileName = config.get('bibfile', 'references.bib')
        self.journalsName = config.get('journals', 'journals.txt')

        for path in self.bibfilePath, self.journalsPath:
            if not exists(path):
                open(path, 'a').close()
                self.vcs.add(relpath(path, self.directory))

        self.bibfile = BibFile(join(self.directory, self.bibfileName))
        self.journals = JournalsFile(join(self.directory, self.journalsName))

        self.name = config.get('name', "Untitled Bibtex Database")
        self.documents = config.get('documents', 'Documents')

        self.makeJournalBibfiles()  # ensure these are up-to-date

        self.publicLink = config.get('publicLink', None)
        if not exists(self.documentsPath):
            os.mkdir(self.documentsPath)

    def setDefault(self):
        """Set this database as default in config."""
        from bibtexvcs import config
        config.setDefaultDatabase(self)

    @classmethod
    def getDefault(cls):
        from bibtexvcs import config
        directory = config.getDefaultDirectory()
        if directory is None:
            raise RuntimeError('No default database configured')
        return cls(directory)

    @property
    def journalsPath(self):
        """The absolute path of the `journals` file."""
        return join(self.directory, self.journalsName)

    @property
    def documentsPath(self):
        """Absolute path of the `documents` directory."""
        return join(self.directory, self.documents)

    @property
    def bibfilePath(self):
        """Absolute path of the bib file."""
        return join(self.directory, self.bibfileName)

    @property
    def configPath(self):
        """Absolute path of the conf file."""
        return join(self.directory, BTVCSCONF)

    @property
    def checksPath(self):
        """Absolute path of the (optional) checks file."""
        return join(self.directory, 'checks.py')

    def referencedDocuments(self):
        """Returns a list of all filenames of documents referenced to in the bib file."""
        docs = []
        for entry in self.bibfile.values():
            fname = entry.filename()
            if fname:
                docs.append(fname)
        return docs

    def existingDocuments(self):
        """Walks recursively through the :attr:`documents` directory and return the paths of all
        files contained in there, relative to :attr:`documentsPath`.
        """
        for dirpath, _, filenames in os.walk(self.documentsPath):
            for file in filenames:
                if file != '.DS_Store':
                    yield relpath(join(dirpath, file), self.documentsPath)

    def strval(self, value):
        """Returns a string value for *value*. If *value* is a :class:`MacroReference`, substitutes
        the value (if known).
        """
        if isinstance(value, MacroReference):
            if value.name in self.bibfile.macroDefinitions:
                return self.bibfile.macroDefinitions[value.name]
            if value.name in self.journals:
                return self.journals[value.name].full
        return str(value)

    @property
    def abbrJournalsName(self):
        """Name of the abbreviated journals string file."""
        return self.bibfileName[:-4] + '_abbr.bib'

    @property
    def fullJournalsName(self):
        """Name of the full journals string file."""
        return self.bibfileName[:-4] + '_full.bib'

    def makeJournalBibfiles(self):
        """Creates or updates the files containing journal macro definitions in full and
        abbreviated form, respectively.
        """
        abbr, full = [join(self.directory, name) for name in
                      (self.abbrJournalsName, self.fullJournalsName)]
        if not exists(full) or not exists(abbr) or \
                        os.path.getmtime(self.journalsPath) > os.path.getmtime(abbr):
            self.journals.writeBibfiles(self.bibfileName[:-4])

    def runJabref(self):
        """Tries to open this database's ``.bib`` file with `JabRef`_. Will do the following:

        - If there is a file named ``jabref.jar`` in :attr:`directory`, it is run with the
          java interpreter through ``java -jar jabref.jar``. If additionally there is a file
          ``jabref.prefs``, JabRef`s options are imported from that file.
        - Otherwise, the command ``jabref`` is executed. To that end, the ``jabref`` binary must
          be in the system's ``PATH``.

        :returns: The :class:`subprocess.Popen` object corresponding to JabRef process.
        """
        shell = False
        if exists(join(self.directory, 'jabref.jar')):
            if os.name == 'nt':
                cmdline = ['start', 'jabref.jar']
                shell = True
            else:
                cmdline = ['java', '-jar', 'jabref.jar']
        else:
            cmdline = ['jabref']
        if exists(join(self.directory, 'jabref.prefs')):
            cmdline += ['--primp', join('jabref.prefs')]
        else:
            cmdline += ['--primp', resource_filename(__name__, 'defaultJabref.prefs')]
        cmdline.append(os.curdir + os.sep + self.bibfileName)
        try:
            return subprocess.Popen(cmdline, shell=shell, cwd=self.directory)
        except FileNotFoundError as fnf:
            if cmdline[0] in ('java', 'start'):
                fnf.strerror = 'Please install Java from http://java.com.'
            elif cmdline[0] == 'jabref':
                fnf.strerror = 'Please install JabRef from http://jabref.sf.net.'
            raise fnf

    @property
    def vcs(self):
        """The :class:`VCSInterface` object associated to this db.

        Will be created on first access.
        """
        if self._vcs is None:
            self._vcs = VCSInterface.get(self)
        return self._vcs

    def export(self, templateString=None, docDir=None):
        """Exports the BibTeX database to a string by using the jinja template engine."""
        import datetime, hashlib
        try:
            import jinja2
        except ImportError:
            raise ImportError('You need to install the jinja2 package in order to export.')
        if docDir is None:
            docDir = self.documentsPath
        def md5filter(value):
            return hashlib.md5(value.encode()).hexdigest()
        env = jinja2.Environment(autoescape=False)
        env.filters['md5'] = md5filter
        if templateString is None:
            templateString = resource_string(__name__, 'defaultTemplate.html').decode('UTF-8')
        template = env.from_string(templateString)
        revision = self.vcs.revision()
        import locale
        locale.setlocale(locale.LC_ALL, '')
        now = datetime.datetime.now().strftime('%c')
        version = get_distribution('bibtexvcs').version
        return template.render(database=self, docDir=docDir, version=version, revision=revision, now=now)


class Journal:
    """A single journal entry in the journals file.

    .. attribute:: macro

        The macro defining the journal.
    .. attribute:: abbr

        The abbreviated journal name.
    .. attribute:: full

        The full (unabbreviated) journal name.
    """
    def __init__(self, macro, abbr, full):
        self.macro = macro
        self.abbr = abbr
        self.full = full

    def __iter__(self):
        yield self.full
        yield self.abbr
        yield self.macro


class JournalsFile(OrderedDict):
    """Represents the file in a bibtexvcs database containing journal abbreviations.

    In the journal file, each journal is represented by a configuration section of the
    following form::

        [JOURNAL_MACRO]
        full = A Journal of Nice and Interesting Topics
        abbr = J. Nice Int. Top.

    :param filename: The path of the journals file.
    :type  filename: str
    :param journals: As an alternative of giving a ``filename``, you can also provide a list
                     of journals entries to create the :class:`JournalsFile` object.
    :type journals: iterable
    """

    def __init__(self, filename=None, journals=None):
        super(JournalsFile, self).__init__()

        if filename:
            journals = []
            parser = configparser.ConfigParser()
            try:
                parser.read(filename, encoding='UTF-8')
            except configparser.Error as error:
                raise DatabaseFormatError('Malformed journals file:\n\n{}'.format(error))
            for section in parser.sections():
                journals.append(Journal(macro=section,
                                        abbr=parser.get(section, "abbr"),
                                        full=parser.get(section, "full")))
        for journal in sorted(journals, key=lambda j: j.full):
            self[journal.macro] = journal

    def write(self, filename):
        """Write the journals file to the given filename."""
        config = configparser.ConfigParser()
        for journal in self.values():
            config.add_section(journal.macro)
            config[journal.macro]['abbr'] = journal.abbr
            config[journal.macro]['full'] = journal.full
        with io.open(filename, 'w', encoding='UTF-8', newline='\n') as journalfile:
            config.write(journalfile)

    def writeBibfiles(self, basename):
        """Creates two ``.bib`` files that contain macro definitions for all journals defined in
        this file, resolving to the full and abbreviated journal names, respectively.

        `basename` is the base path of the output files, which will have the file names
        ``<basename>_full.bib`` and ``<basename>_abbr.bib``, respectively.
        """
        for jrnlType in 'full', 'abbr':
            outFile = '{}_{}.bib'.format(basename, jrnlType)
            with io.open(outFile, 'w', encoding='UTF-8') as bibfile:
                for journal in self.values():
                    bibfile.write('@STRING{' + journal.macro + ' = {' + getattr(journal, jrnlType)
                                  + '}}\n')
