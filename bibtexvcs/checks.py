#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

from literature.parser import MacroReference

class ConsistencyError(Exception):
    pass

def _checkJournalMacro(entry, field, journals):
    if field in entry and isinstance(entry[field], MacroReference):
        if entry[field].name not in journals:
            raise ConsistencyError("{} macro '{}' in '{}' does not exist in journal file".
                                   format(field, entry[field].name, entry["cite key"]))


def checkJournalMacros(database):
    """Check if all journal macros defined in *database* exist in *journals*.
    """
    
    for entry in database.bibfile.values():
        _checkJournalMacro(entry, "journal", database.journals)
        _checkJournalMacro(entry, "booktitle", database.journals)
        

def checkFileLinks(database, fileNames, **kwargs):
    """Check that the files linked to in *database* and those existing in *listOfFilenames* match.
    
    If either an entry of *database* links to a file that does not exist, or a filename in
    *listOfFilenames* is not linked to by any database entry, an exception is thrown.
    """
    
    dbFilesSet = set(database.referencedFiles())
    fsFilesSet = set(fileNames)
    
    if len(dbFilesSet - fsFilesSet) > 0:
        raise ConsistencyError("Some files in the bib file don't exist in document folder:\n"
                               "{}".format("\n".join(dbFilesSet - fsFilesSet)))
    if len(fsFilesSet - dbFilesSet) > 0:
        raise ConsistencyError("Some files in the document folder are not linked in any entry:\n"
                               "{}".format("\n".join(fsFilesSet - dbFilesSet)))


def checkMonthMacros(database, **kwargs):
    """Checks that the "month" field only contains (proper) macros."""
    MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul",
              "aug", "sep", "oct", "nov", "dec"]
    for key, entry in database.entries.items():
        try:
            month = entry["month"]
        except KeyError:
            continue
        if isinstance(month, str):
            raise ValueError("Non-macro '{}' in month field of '{}' detected".
                             format(month, key))
        elif isinstance(month, MacroReference):
            if month.name not in MONTHS:
                raise ValueError("Month macro '{}' used in '{}' is not valid".
                                format(month.name, key))
        else:
            #  must be a list of macros
            if len(month) % 2 != 1:
                raise ValueError("Invalid month definition '{}' in '{}': even number of fields".
                                 format(month, key))
            separators = [ month[i] for i in range(1, len(month), 2) ]
            macros = [ month[i] for i in range(0, len(month), 2) ]
            if any(separator.strip() != "/" for separator in separators):
                raise ValueError("Invalid month definition '{}' in '{}'".
                                 format(month, key))
            if any(macro.name not in MONTHS for macro in macros):
                raise ValueError("Invalid month definition '{}' in '{}'".
                                 format(month, key)) 