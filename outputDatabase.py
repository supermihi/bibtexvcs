#!/usr/bin/python

import sys
import hashlib

import jinja2

from literature.database import LiteratureDatabase

def md5filter(value):
    return hashlib.md5(value.encode()).hexdigest()

dtb = LiteratureDatabase(sys.argv[1], sys.argv[2])
def bibval(entry, field, abbr=None):
    return entry.strval(field, abbr)
env = jinja2.Environment(autoescape=False)
env.filters['md5'] = md5filter
env.filters['bibval'] = bibval
#template = env.get_template('example.html')
template = env.from_string(open('example.html').read())

with open('rendered.html', 'wt') as f:
    f.write(template.render(database=dtb, entries=sorted(dtb.entries.values(), key=lambda entry: entry.get("author", ""))))
