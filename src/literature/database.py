from __future__ import absolute_import, print_function

from collections import OrderedDict
from . import btpyparse
from .journals import readJournalFile


class DatabaseFormatError(Exception):
    """Raised if the BibTeX database file is malformed."""
    pass

class Entry(dict):
    
    def __init__(self, ppEntry, database):
        super().__init__()
        self.database = database
        for key, val in ppEntry.items():
            if key == "entry type":
                self.entrytype = val
            elif key == "cite key":
                self.key = val
            else:
                self[key] = val
    
    def authorLastNames(self, maxNames=None):
        try:
            authors = self["author"].split(" and ")
            string = ", ".join(name.split(",")[0] for name in authors[:maxNames])
            if len(authors) > maxNames:
                string += ", et al."
            return string
        except KeyError:
            return ""
    
    def filename(self):
        if "file" in self:
            try:
                return self["file"][1:].rsplit(":", 1)[0].replace("\;", ";")
            except IndexError:
                raise DatabaseFormatError('Wrong URL format in "{0}" : {1}'.format(self.key, self["file"]))
    
    def doiURL(self):
        if "doi" in self:
            return "http://dx.doi.org/" + self["doi"]

    def textify(self, value, abbr=False):
        if isinstance(value, btpyparse.Macro):
            if value.name in self.database.journals:
                jrnl = self.database.journals[value.name]
                return jrnl.strval(abbr)
            else:
                return value.name
        if isinstance(value, str):
            return value
        return "".join(self.textify(token, abbr) for token in value)
    
    def strval(self, key, abbrJournals=False):
        if key not in self:
            return ""
        return self.textify(self[key])
    
    def datestr(self):
        if "date" in self:
            return self["date"]
        ret = ""
        if "month" in self:
            ret += self.textify(self["month"]) + " "
        if "year" in self:
            ret += self["year"]
        return ret

class LiteratureDatabase:
    
    def __init__(self, filename, journals=None):
        self.filename = filename
        if isinstance(journals, str):
            journals = readJournalFile(journals)
        elif journals is None:
            journals = OrderedDict()
        self.journals = journals
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
                
    def referencedFiles(self):
        linkedFiles = []
        for entry in self.entries.values():
            fname = entry.filename()
            if fname:
                linkedFiles.append(fname)
        return linkedFiles