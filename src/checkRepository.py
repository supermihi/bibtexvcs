#!/usr/bin/python3

import sys
import literature.database, literature.journals, literature.checks

if __name__ == "__main__":
    assert len(sys.argv) == 4
    
    db = literature.database.LiteratureDatabase(sys.argv[1])
    journals = literature.journals.readJournalFile(sys.argv[2])
    files = []
    with open(sys.argv[3], "rt") as f:
        for line in f:
            files.append(line.strip())
    for elem in dir(literature.checks):
        if elem.startswith("check"):
            function = getattr(literature.checks, elem)
            if hasattr(function, "__call__"):
                function(database=db, journals=journals, fileNames=files)
    