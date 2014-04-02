#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

# The parser definitions are partially based on "btpyparse" by Matthew Brett
# 2010 Simplified BSD license.
# https://github.com/matthew-brett/btpyparse

from __future__ import division, print_function, unicode_literals
import re

from pyparsing import (Regex, Suppress, ZeroOrMore, OneOrMore, Group, Optional, Forward,
                       SkipTo, CaselessLiteral, Dict, originalTextFor, delimitedList)

from bibtexvcs.bibfile import (Entry, Comment, ImplicitComment, MacroReference,
                                MacroDefinition, Name, Preamble)

LCURLY = Suppress('{')
RCURLY = Suppress('}')
QUOTE = Suppress('"')
COMMA = Suppress(',')
AT = Suppress('@')
EQUALS = Suppress('=')
HASH = Suppress('#')

bracketed = lambda expr: LCURLY + expr + RCURLY

# Define parser components for strings (the hard bit)
charsNoCurly = Regex(r"[^{}]+")
charsNoCurly.leaveWhitespace()
charsNoQuotecurly = Regex(r'[^"{}]+')
charsNoQuotecurly.leaveWhitespace()

# Curly string is some stuff without curlies, or nested curly sequences
curlyString = Forward().leaveWhitespace()
curlyItem = Group(curlyString) | charsNoCurly
curlyString <<= LCURLY + ZeroOrMore(curlyItem) + RCURLY

# quoted string is either just stuff within quotes, or stuff within quotes, within
# which there is nested curliness
quotedItem = Group(curlyString) | charsNoQuotecurly
quotedString = QUOTE + ZeroOrMore(quotedItem) + QUOTE

number = Regex('[0-9]+')
# Basis characters (by exclusion) for variable / field names.  The following
# list of characters is from the btparse documentation
anyName = Regex('[^\s"#%\'(),={}]+')

# btparse says, and the test bibs show by experiment, that macro and field names
# cannot start with a digit.  In fact entry type names cannot start with a digit
# either (see tests/bibs). Cite keys can start with a digit
notDigname = Regex('[^\d\s"#%\'(),={}][^\s"#%\'(),={}]*')

comment = AT + CaselessLiteral('comment') + LCURLY + charsNoCurly.setResultsName("comment") + RCURLY
comment.setParseAction(Comment.fromParseResult)

# The name types with their digiteyness
notDigLower = notDigname.copy().setParseAction(lambda t: t[0].lower())

macroDef = notDigLower.copy()

macroRef = notDigLower.copy().setParseAction(MacroReference.fromParseResult)
fieldName = notDigLower.copy()
entryType = notDigLower.setResultsName('entry type')
citeKey = anyName.setResultsName('cite key')
string = (number | macroRef | quotedString | curlyString)

# There can be hash concatenation
fieldValue = string + ZeroOrMore(HASH + string)

namePart = Regex(r'(?!\band\b)[^\s\.,{}]+\.?') | curlyString
nobility = Regex(r'[a-z]\w+\.?(\s[a-z]\w+\.?)*').setResultsName("nobility")  # "van" etc.
spacedNames = originalTextFor(OneOrMore(namePart))
firstNames = spacedNames.copy().setResultsName("firstname")
lastNames = spacedNames.copy().setResultsName("lastname")
nameSuffix = namePart.copy().setResultsName("suffix")

# a name in "comma separated" style, like "Helmling, Michael"
csName = (Optional(nobility) + lastNames + COMMA + Optional(nameSuffix + COMMA) + firstNames)


def labelLiteralName(toks):
    """In case of a literal name, we cannot distinguish between first and middle names, or
    recognize multi-part last names. Hence it is assumed that the last part is the last name,
    anything else is stored as first names.
    """
    toks["lastname"] = toks[-1]
    if len(toks) > 1:
        toks["firstname"] = " ".join(toks[:-1])
    return toks

# a name in "literal" style, like "Michael Helmling
literalName = OneOrMore(namePart).setParseAction(labelLiteralName)

def makeName(toks):
    """Create a :class:`Name` object from the parse result of either a csName or a literalName."""
    return Name(first=toks.get("firstname"),
                nobility=toks.get("nobility"),
                last=toks.get("lastname"),
                suffix=toks.get("suffix"))

name = (csName | literalName).setParseAction(makeName)
NAME_SEP = Regex(r'and[^}]', flags=re.IGNORECASE).suppress()
namesList = LCURLY + delimitedList(name, NAME_SEP) + RCURLY

namesField = (CaselessLiteral("author") | CaselessLiteral('editor')).setParseAction(lambda t: t[0].lower())
# we treat the author field special because we parse names
fieldDef = Group(namesField + EQUALS + namesList) | Group(fieldName + EQUALS + fieldValue)
entryContents = Dict(ZeroOrMore(fieldDef + COMMA) + Optional(fieldDef))


entry = originalTextFor(AT + entryType + bracketed(citeKey + COMMA + entryContents), asString=False)
entry.addParseAction(Entry.fromParseResult)

# Preamble is a macro-like thing with no name
preamble = AT + CaselessLiteral('preamble') + bracketed(fieldValue).setResultsName("preamble")
preamble.setParseAction(Preamble.fromParseResult)

# Macros (aka strings)
macroContents = macroDef.setResultsName("macro") + EQUALS + fieldValue.setResultsName("definition")


macro = (AT + CaselessLiteral('string') + bracketed(macroContents)).setParseAction(MacroDefinition.fromParseResult)

icomment = SkipTo('@').setResultsName("comment").setParseAction(ImplicitComment.fromParseResult)

definitions = comment | preamble | macro | entry
bibfile = Optional(icomment) + ZeroOrMore(definitions)
