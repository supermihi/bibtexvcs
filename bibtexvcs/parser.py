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

import re

from pyparsing import (Regex, Suppress, ZeroOrMore, OneOrMore, Group, Optional, Forward,
                       SkipTo, CaselessLiteral, Dict, originalTextFor, delimitedList)


from literature.bibfile import Entry, Comment, MacroReference, MacroDefinition, Name

# Character literals
LCURLY = Suppress('{')
RCURLY = Suppress('}')
LPAREN = Suppress('(')
RPAREN = Suppress(')')
QUOTE = Suppress('"')
COMMA = Suppress(',')
AT = Suppress('@')
EQUALS = Suppress('=')
HASH = Suppress('#')


def bracketed(expr):
    """ Return matcher for `expr` between curly brackets or parentheses """
    return (LPAREN + expr + RPAREN) | (LCURLY + expr + RCURLY)


# Define parser components for strings (the hard bit)
charsNoCurly = Regex(r"[^{}]+")
charsNoCurly.leaveWhitespace()
charsNoQuotecurly = Regex(r'[^"{}]+')
charsNoQuotecurly.leaveWhitespace()
# Curly string is some stuff without curlies, or nested curly sequences
curlyString = Forward().leaveWhitespace()
curlyItem = Group(curlyString) | charsNoCurly
curlyString << LCURLY + ZeroOrMore(curlyItem) + RCURLY
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

comment = AT + CaselessLiteral('comment') + bracketed(charsNoCurly).setResultsName("comment")
comment.setParseAction(Comment.fromParseResult)

# The name types with their digiteyness
notDigLower = notDigname.copy().setParseAction(lambda t: t[0].lower())
    
macroDef = notDigLower.copy()

macroRef = notDigLower.copy().setParseAction(MacroReference.fromParseResult)
fieldName = notDigLower.copy()
# Spaces in names mean they cannot clash with field names
entryType = notDigLower.setResultsName('entry type')
citeKey = anyName.setResultsName('cite key')
# Number has to be before macro name
string = (number | macroRef | quotedString |
          curlyString)

# There can be hash concatenation
fieldValue = string + ZeroOrMore(HASH + string)

namePart = Regex(r'(?!\band\b)\w+\.?') | curlyString
nobility = Regex(r'[a-z]\w+\.?').setResultsName("nobility") # "van" etc.
firstName = namePart.copy().setResultsName("firstname")
lastName = namePart.copy().setResultsName("lastname")
nameSuffix = namePart.copy().setResultsName("suffix")

NAME_SEP = Regex(r'and[^}]', flags=re.IGNORECASE).suppress()

csName = ( Optional(nobility) + lastName + COMMA + 
           Optional(nameSuffix + COMMA) + 
           firstName + ZeroOrMore(namePart).setParseAction(lambda t: t.asList()).setResultsName("middlenames") )

def labelLiteralName(toks):
    toks["lastname"] = toks[-1]
    if len(toks) > 1:
        toks["firstname"] = toks[0]
    if len(toks) >2:
        toks["middlenames"] = toks[1:-1]
    return toks

literalName = OneOrMore(namePart).setParseAction(labelLiteralName)
def makeName(toks):
    return Name(first=toks.get("firstname"),
                middle=toks.get("middlenames"),
                nobility=toks.get("nobility"),
                last=toks.get("lastname"),
                suffix=toks.get("suffix"))
name = (csName | literalName).setParseAction(makeName)
namesList = LCURLY + delimitedList(name, NAME_SEP) + RCURLY

author = CaselessLiteral("author")

fieldDef = Group((author + EQUALS + namesList)) | Group((fieldName + EQUALS + fieldValue))
entryContents = Dict(ZeroOrMore(fieldDef + COMMA) + Optional(fieldDef))


entry = originalTextFor(AT + entryType + bracketed(citeKey + COMMA + entryContents), asString=False)
entry.addParseAction(Entry.fromParseResult)

# Preamble is a macro-like thing with no name
preamble = AT + CaselessLiteral('preamble') + bracketed(fieldValue)

# Macros (aka strings)
macroContents = macroDef.setResultsName("macro") + EQUALS + fieldValue.setResultsName("definition")


macro = (AT + CaselessLiteral('string') + bracketed(macroContents)).setParseAction(MacroDefinition.fromParseResult)

icomment = SkipTo('@').setResultsName("comment") #.setParseAction(Comment.fromParseResult)

# entries are last in the list (other than the fallback) because they have
# arbitrary start patterns that would match comments, preamble or macro
definitions = comment | preamble | macro | entry
bibfile = Optional(icomment) + ZeroOrMore(definitions)

def parse_str(string):
    return bibfile.parseString(string)

example = """
Some introductory text
(implicit comment)

@ARTICLE{Authors2011,
  author = {Stefan Maria van Ruzika and von Helmling, Michael and Forney, Jr., David G. M.},
  title = {An article about {S}omething},
  journal = "Journal of Articles",
  journaltitle = IEEE_J_IT,
  year = {2011},
  volume = {16},
  pages = {1140--1141},
  number = {2}
}
@STRING{spast = {lol lol lol}}

@INCOLLECTION{DeineMutter,
    title = {Artikel von deiner Mutter}
}
"""

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rt") as f:
            text = f.read()
    else:
        text = example
    parsed = bibfile.parseString(text, parseAll=False)
    for entry in parsed:
        print(type(entry))
        print(entry)
