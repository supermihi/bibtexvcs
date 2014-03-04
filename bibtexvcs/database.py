from configparser import ConfigParser
from collections import OrderedDict ,namedtuple
from os.path import abspath, dirname, join, basename, exists

from bibtexvcs.bibfile import BibFile

class Database:
    """Represents a complete literature database.
    
    :param btvcsconf: Path of the database's main configuration file.
    :type btvcsconf: str
    
    The database configuration is read from `btvcsconf` and from the layout of the
    directory that file resides in.
    
    .. attribute:: confFile
        
        Name of the configuration file.
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
    
    def __init__(self, btvcsconf):
        parser = ConfigParser()
        
        with open(btvcsconf) as f:
            confFile = f.read()
        # workaround because ConfigParser does not support sectionless entries
        parser.read_string("[root]\n" + confFile)
        config = parser['root']
        
        self.confFile = basename(btvcsconf)
        self.directory = abspath(dirname(btvcsconf)) 
        self.bibfileName = config.get('bibfile', 'references.bib')
        self.bibfile = BibFile(join(self.directory, self.bibfileName))
        
        self.journalsName = config.get('journals', 'journals.txt')
        self.journals = JournalsFile(join(self.directory, self.journalsName))
        
        self.name = config.get('name', "Untitled Bibtex Database")
        self.documents = config.get('documents', 'Documents')
        
        if exists(join(self.directory, '.git')):
            self.vcsType = 'git'
        elif exists(join(self.directory, '.hg')):
            self.vcsType = 'mercurial'
        else:
            self.vcsType = None
    
    def referencedFiles(self):
        linkedFiles = []
        for entry in self.bibfile.values():
            fname = entry.filename()
            if fname:
                linkedFiles.append(fname)
        return linkedFiles


Journal = namedtuple("Journal", "macro, abbr, full")

class JournalsFile(OrderedDict):
    """Represents the file in a bibtexvcs database containing journal abbreviations.
    
    In the journal file, each journal is represented by a configuration section of the
    following form::
    
        [JOURNAL_MACRO]
        full = A Journal of Nice and Interesting Topics
        abbr = J. Nice Int. Top.
    
    :param filename: The path of the journals file.
    :type  filename: str.
    """
    
    def __init__(self, filename):
        super().__init__(self)
        parser = ConfigParser()
        parser.read(filename)
        for section in parser.sections():
            self[section] = Journal(macro=section,
                                    abbr=parser.get(section, "abbr"),
                                    full=parser.get(section, "full"))