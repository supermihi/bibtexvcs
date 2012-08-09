import collections

class JournalFormatError(Exception):
    pass


class Journal(object):

    def __init__(self, macro, abbr, full):
        self.macro = macro
        self.abbr = abbr
        self.full = full
        
    def __str__(self):
        return self.abbr
        
        
def readJournalFile(filename, separator="|", encoding="utf8"):
    """Read the journal definiton file from *filename*.
    
    The file consists of one journal definition (macro, abbreviated name, full name) per line,
    separated by *separator* (a vertical line '|' by default). The file encoding can be set with
    *encoding* and defaults to UTF-8.
    
    Returns a collections.OrderedDict mapping macros to Journal objects.
    """
    
    journals = collections.OrderedDict()
    with open(filename, 'rt', encoding=encoding) as jFile:
        for line in jFile:
            line = line.strip()
            if line == "" or line.startswith("#"):
                continue
            try:
                macro, abbr, full = line.split(separator)
                journals[macro] = Journal(macro, abbr, full)
            except ValueError:
                raise JournalFormatError("Could not parse line '{0}' in "
                                             "jorunal file {1}\n".format(line, filename))
    return journals
