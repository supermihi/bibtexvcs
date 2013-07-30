from __future__ import absolute_import, print_function

from collections import OrderedDict
from . import btpyparse

class DatabaseFormatError(Exception):
    pass

class Entry(dict):
    
    def __init__(self, ppEntry):
        super().__init__()
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
        

class LiteratureDatabase:
    
    def __init__(self, filename):
        self.filename = filename
        with open(filename, "rt") as bibFile:
            bibText = bibFile.read()
        bibParsed = btpyparse.parse_str(bibText)
        self.comments = []
        self.entries = OrderedDict()
        for item in bibParsed:
            if "cite key" in item:
                self.entries[item["cite key"]] = Entry(item)
            elif item[0] in ("comment", "icomment"):
                self.comments.append(item)
            else:
                print('unknown item: {}'.format(item))
                
    def referencedFiles(self):
        linkedFiles = []
        for key, entry in self.entries.items():
            try:
                fileAttr = entry["file"]
            except KeyError:
                continue
            try:
                fileName = fileAttr[1:].rsplit(":", 1)[0].replace("\;", ";")
                linkedFiles.append(fileName)
            except IndexError:
                raise DatabaseFormatError('Wrong URL format in "{0}" : {1}'.format(key, fileAttr))
        return linkedFiles