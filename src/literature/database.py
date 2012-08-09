from __future__ import absolute_import, print_function

from . import btpyparse

class DatabaseFormatError(Exception):
    pass

class LiteratureDatabase(object):
    
    def __init__(self, filename):
        self.filename = filename
        with open(filename, "rt") as bibFile:
            bibText = bibFile.read()
        bibParsed = btpyparse.parse_str(bibText)
        self.comments = []
        self.entries = {}
        for item in bibParsed:
            if "cite key" in item:
                self.entries[item["cite key"]] = item
            elif item[0] == "comment":
                self.comments.append(item)
                
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