import configparser
from collections import OrderedDict
from os.path import join, exists, relpath
import os

from bibtexvcs.bibfile import BibFile, MacroReference
from bibtexvcs.vcs import VCSInterface, typeMap

BTVCSCONF = 'bibtexvcs.conf' # name of the configuration file

class DatabaseFormatError(Exception):
    """Raised on any problem in the database layout (unparsable config-file, non-existeng bib file, etc.).
    """
    pass


class Database:
    """Represents a complete literature database.
    
    :param directory: Base path of the database.
    :type directory: str
    
    The database configuration is read from the file `bbibtexvcs.conf` and from the layout of the
    directory that file resides in.
    .. attribute:: directory
    
        Absolute path of the root directory of the literature database.
    .. attribute:: bibfileName
    
        Name of the main bibtex database file.
    .. attribute:: bibfile
        
        :class:`BibFile` object parsed from the bibtex file.
    .. attribute:: journalsName
    
        Name of the journals file.
    .. attribute:: journals
    
        :class:`JournalsFile` object read from the journals file.
    .. attribute:: name
    
        Name of the database.
    .. attribute:: documents
        
        Name of the documents directory (relative to :attr:`directory`).
        
    .. attribute:: vcsType
    
        Type of the used VCS system. One of: ``"git"``, ``"mercurial"``, or ``None``
    """
    
    def __init__(self, directory):
        self.directory = directory
        if exists(join(self.directory, '.git')):
            self.vcsType = 'git'
        elif exists(join(self.directory, '.hg')):
            self.vcsType = 'mercurial'
        else:
            self.vcsType = None
        self.reload()
        
    def reload(self):
        parser = configparser.ConfigParser()
        with open(self.configPath) as f:
            confFile = f.read()
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
        if not exists(self.documentsPath):
            os.mkdir(self.documentsPath)
        
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
    
    def referencedDocuments(self):
        docs = []
        for entry in self.bibfile.values():
            fname = entry.filename()
            if fname:
                docs.append(fname)
        return docs

    def existingDocuments(self):
        """Walks recursively through the `Documents` directory and return the paths of all files
        contained in there, relative to :attr:`documentsPath`.
        """
        for dirpath, dirnames, filenames in os.walk(self.documentsPath):
            for file in filenames:
                yield relpath(join(dirpath, file), self.documentsPath)
    
    def strval(self, value):
        if isinstance(value, MacroReference):
            if value.name in self.bibfile.macroDefinitions:
                return self.bibfile.macroDefinitions[value.macro]
            if value.name in self.journals:
                return self.journals[value.name].full
        return str(value)
      
    @property
    def vcs(self):
        """The :class:`VCSInterface` object associated to this db.
        
        Will be created on first access.
        """
        if not hasattr(self, '_vcs'):
            self._vcs = VCSInterface.get(self)
        return self._vcs

    @classmethod
    def cloneDatabase(cls, vcsType, url, target):
        vcsCls = typeMap[vcsType]
        vcsCls.clone(url, target)
        if not exists(join(target, BTVCSCONF)):
            raise FileNotFoundError('Configuration file "{}" not found in cloned repository '
                                    'under "{}"'.format(BTVCSCONF, target))
        return cls(target)


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
        super().__init__(self)
        
        if filename:
            journals = []
            parser = configparser.ConfigParser()
            try:
                parser.read(filename)
            except configparser.Error as e:
                raise DatabaseFormatError('Malformed journals file:\n\n{}'.format(e))
            for section in parser.sections():
                journals.append(Journal(macro=section,
                                        abbr=parser.get(section, "abbr"),
                                        full=parser.get(section, "full")))
        for journal in sorted(journals, key=lambda j: j.full):
            self[journal.macro] = journal
            
    def write(self, filename):
        config = configparser.ConfigParser()
        for journal in self.values():
            config.add_section(journal.macro)
            config[journal.macro]['abbr'] = journal.abbr
            config[journal.macro]['full'] = journal.full
        with open(filename, 'wt') as journalfile:
            config.write(journalfile)
