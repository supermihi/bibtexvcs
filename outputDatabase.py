#!/usr/bin/python

import sys
import hashlib

import jinja2

from bibtexvcs.database import Database

def md5filter(value):
    return hashlib.md5(value.encode()).hexdigest()

dtb = Database(sys.argv[1])
env = jinja2.Environment(autoescape=False)
env.filters['md5'] = md5filter
#template = env.get_template('example.html')
template = env.from_string(open('example.html').read())

with open('rendered.html', 'wt') as f:
    f.write(template.render(database=dtb, entries=dtb.bibfile.values()))
