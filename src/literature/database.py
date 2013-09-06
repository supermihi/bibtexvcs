from __future__ import absolute_import, print_function

from collections import OrderedDict
from . import btpyparse
from .journals import readJournalFile


class DatabaseFormatError(Exception):
    """Raised if the BibTeX database file is malformed."""
    pass

class Entry(dict):
    """A single BibTeX entry. Values can be accessed through the dict interface.
    
    Additionally the attributes "key" (BibTeX key) and "entrytype" (article, book, etc.)
    are available.
    """
    
    def __init__(self, ppEntry, database):
        super().__init__()
        self.database = database
        self.bibsrc = ppEntry[-1]
        print(self.bibsrc)
        for key, val in ppEntry.items():
            if key == "entry type":
                self.entrytype = val
            elif key == "cite key":
                self.key = val
            else:
                self[key] = val
    
    def authorLastNames(self, maxNames=None):
        """Formatted output of the author file in form ofcomma-joined last names.
        
        If *maxNames* is given, the abbreviation "et al." is used after *maxNames*
        author names.
        """
        try:
            authors = self["author"].split(" and ")
            string = ", ".join(name.split(",")[0] for name in authors[:maxNames])
            if len(authors) > maxNames:
                string += ", et al."
            return string
        except KeyError:
            return ""
    
    def filename(self):
        """Returns the filename referenced in the "file" field in JabRef format.
        
        Returns None if there is no "file" field. The format of the file field is
        :filename:
        If it does not match this format, a DatabaseFormatError will be raised.
        """ 
        if "file" in self:
            try:
                return self["file"][1:].rsplit(":", 1)[0].replace("\;", ";")
            except IndexError:
                raise DatabaseFormatError('Wrong URL format in "{0}" : {1}'.format(self.key, self["file"]))
    
    def doiURL(self):
        """Returns the DOI URL if a "doi" field is present or None otherwise."""
        if "doi" in self:
            return "http://dx.doi.org/" + self["doi"]
    
    def strval(self, key, abbr=None):
        """Returns a string value of the given field.
        
        In contrast to simple dict field access, macros and journal names are expanded in
        the output of strval.
        """
        if key not in self:
            return ""
        return self.database._textify(self[key], abbr)
    
    def datestr(self):
        if "date" in self:
            return self["date"]
        ret = ""
        if "month" in self:
            ret += self.database._textify(self["month"]) + " "
        if "year" in self:
            ret += self["year"]
        return ret


class LiteratureDatabase:
    """Represents a complete literature database including journals file."""
    
    def __init__(self, filename, journals=None, abbreviate=True):
        self.filename = filename
        if isinstance(journals, str):
            journals = readJournalFile(journals)
        elif journals is None:
            journals = OrderedDict()
        self.journals = journals
        self.abbreviate=abbreviate
        with open(filename, "rt") as bibFile:
            bibText = bibFile.read()
        bibParsed = btpyparse.parse_str(bibText)
        self.comments = []
        self.entries = OrderedDict()
        for item in bibParsed:
            if "cite key" in item:
                self.entries[item["cite key"]] = Entry(item, self)
            elif item[0] in ("comment", "icomment"):
                self.comments.append(item)
            else:
                print('unknown item: {}'.format(item))
    
    def _textify(self, value, abbr=None):
        if abbr is None:
            abbr = self.abbreviate
        if isinstance(value, btpyparse.Macro):
            if value.name in self.journals:
                jrnl = self.journals[value.name]
                return jrnl.strval(abbr)
            else:
                return value.name
        if isinstance(value, str):
            return value
        return "".join(self._textify(token) for token in value)
    
    def referencedFiles(self):
        linkedFiles = []
        for entry in self.entries.values():
            fname = entry.filename()
            if fname:
                linkedFiles.append(fname)
        return linkedFiles