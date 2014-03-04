from os.path import abspath, join, dirname

def datadir():
    return join(abspath(dirname(__file__)), 'data')