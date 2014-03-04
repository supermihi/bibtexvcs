
class LiteratureDatabase:
    """Represents a complete literature database including journals file."""
    
    def __init__(self, bibfile, journals=None, abbreviate=True):
        self.bibfle = bibfile
        if isinstance(journals, str):
            journals = readJournalFile(journals)
        elif journals is None:
            journals = OrderedDict()
        self.journals = journals
        self.abbreviate = abbreviate
        
    
    def _textify(self, value, abbr=None):
        if abbr is None:
            abbr = self.abbreviate
        if isinstance(value, MacroReference):
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
        for entry in self.bibfile.values():
            fname = entry.filename()
            if fname:
                linkedFiles.append(fname)
        return linkedFiles
