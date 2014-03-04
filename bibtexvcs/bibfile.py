#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation


from collections import OrderedDict, namedtuple

"""This module contains classes for an object-oriented representation of the .bib file.

Most of it is generic for BibTeX, i.e. not special to the literature package.
"""


class DatabaseElement:
    """Base class for database elements (Entries, Comments, Macros)."""
    
    @classmethod
    def fromParseResult(cls, toks):
        """Creates the database element from the result of the parser.
        
        This method is meant to be used in L{parser} as parseAction on the corresponding element.
        
        @param toks: the token list 
        """
        raise NotImplementedError()


class MacroDefinition(DatabaseElement):
    """Represents a macro definition (@STRING{bla={blub}}).
    
    The members C{key} and C{value} hold the corresponding elements of the definition.
    """
    
    def __init__(self, macro, definition):
        self.key = macro
        self.value = definition
    
    def __str__(self):
        return "MacroDefinition({}={})".format(self.key, self.value)

    @classmethod
    def fromParseResult(cls, toks):
        macro = toks["macro"]
        definition = toks["definition"]
        return cls(macro, definition)
    

class MacroReference(DatabaseElement):
    """ Class to encapsulate undefined macro references."""
    def __init__(self, name):
        self.name = name
    
    def __repr__(self):
        return 'MacroReference("{}")'.format(self.name)
    
    __str__ = __repr__
    
    def __eq__(self, other):
        return self.name == other.name
    
    def __ne__(self, other):
        return self.name != other.name
    
    @classmethod
    def fromParseResult(cls, toks):
        return cls(toks[0])
    

class Entry(DatabaseElement, dict):
    """Creates a new BibTeX entry.
    """
    
    def __init__(self, entrytype, citekey, fields, src):
        super(dict).__init__()
        self.bibsrc = src
        for key, val in fields.items():
            self[key] = val
        self.citekey = citekey
        self.entrytype = entrytype
    
    @classmethod
    def fromParseResult(cls, toks):
        bibsrc = toks[-1]
        fields = {}
        for key, val in toks.items():
            if key == "entry type":
                entrytype = val
            elif key == "cite key":
                citekey = val
            else:
                fields[key] = val
        return Entry(entrytype=entrytype, citekey=citekey, fields=fields, src=bibsrc)
    
    def filename(self):
        """Returns the filename referenced in the C{file} field in JabRef format.
        
        The format of the I{file} field is
        :filename:
        If a I{file} field is present but does not match this format, 
        a L{DatabaseFormatError} will be raised.
        
        @returns : The filename or C{None} if there is no I{file} field in the entry.
        """ 
        if "file" in self:
            fname = self["file"]
            try:
                return fname[1:].rsplit(":", 1)[0].replace("\;", ";")
            except IndexError:
                raise DatabaseFormatError('Wrong file URL format in entry "{}": '
                                          '{1}'.format(self.citekey, fname))
    
    def doiURL(self):
        """Returns the DOI URL if a "doi" field is present or None otherwise."""
        if "doi" in self:
            return "http://dx.doi.org/" + self["doi"]
    
    def datestr(self):
        if "date" in self:
            return self["date"]
        ret = ""
        if "month" in self:
            ret += self.database._textify(self["month"]) + " "
        if "year" in self:
            ret += self["year"]
        return ret

    def __str__(self):
        return "{}({}) by {}".format(self.entrytype, self.citekey, self.get("author"))


class Comment(DatabaseElement):
    
    def __init__(self, comment):
        self.comment = comment
    
    @classmethod
    def fromParseResult(cls, toks):
        return cls(toks["comment"])

    def __str__(self):
        return "Comment({})".format(self.comment)

Name = namedtuple('Name', 'first middle nobility last suffix')        


class DatabaseFormatError(Exception):
    """Raised if the BibTeX database file is malformed."""
    pass


class BibFile(OrderedDict):
    
    def __init__(self, filename):
        super(OrderedDict).__init__()
        self.filename = filename
        from . import parser
        with open(filename, "rt") as bibFile:
            bibText = bibFile.read()
        bibParsed = parser.bibfile.parseString(bibText)
        self.comments = []
        self.macroDefinitions = {}
        for item in bibParsed:
            if isinstance(item, Entry):
                self[item.citekey] = item
            elif isinstance(item, Comment):
                self.comments.append(item)
            elif isinstance(item, MacroDefinition):
                self.macroDefinitions[item.key] = item
            else:
                raise ValueError('Unknown item parsed: {}'.format(item))