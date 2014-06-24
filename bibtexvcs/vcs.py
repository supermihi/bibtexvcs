#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

from __future__ import division, print_function, unicode_literals
import io
import os
import subprocess
import sys

from bibtexvcs import config


class MergeConflict(Exception):
    """Raised when merge conflicts occur on a VCS update operation."""
    pass


class AuthError(Exception):
    """Raised on authentication errors when accessing remote repositories."""
    pass


class VCSNotFoundError(Exception):
    """Raised when the necessary VCS binary (e.g. "hg") is not installed."""

typeMap = {} # maps name of a VCS (e.g. 'mercurial') to class instance


class VCSMeta(type):
    def __init__(cls, name, base, namespace):
        super(VCSMeta, cls).__init__(name, base, namespace)
        if hasattr(cls, 'vcsType'):
            typeMap[cls.vcsType] = cls

VCSBase = VCSMeta('VCSBase' if sys.version_info.major >= 3 else b'VCSBase', (object,), {})


class VCSInterface(VCSBase):
    """Interface to the version control system (VCS) of a :mod:`bibtexvcs` database.

    .. attribute:: username

        Optional username for authentication.
    .. attribute:: password

        Optional password for authentication.
    """

    def __init__(self, db):
        self.db = db
        ans = config.getAuthInformation(db)
        if ans:
            self.username, self.password = ans
        else:
            self.username = self.password = None

    @property
    def root(self):
        return self.db.directory

    def add(self, path):
        """Adds a file or directory to the repository.

        :param path: The path (relative to the vcs root).
        :type path: str
        """

    def localChanges(self):
        """Determines whether any local changes have been made to the repository.

        Returns ``True`` if one of the following requirements are met:

        - any versioned file has been modified,
        - any versioned file in the documents folder has been deleted, or
        - any unversioned file has been placed in the documents folder.
        """
        raise NotImplementedError()

    def update(self):
        """Checks if there are updates in the remote repository. If so, tries to merge
        them and reloads the database.

        :return: ``True`` if something was update, ``False`` otherwise.
        :raises: :class:`MergeConflict` if a conflict is introduced by merging."""
        raise NotImplementedError()

    def commit(self, msg=None):
        """Commit local changes and push to remote, if exists.

        :param msg: Commit message.
        :type msg:  str
        :rtype: bool
        :return: Indicate whether there were any actual changes.
        """
        raise NotImplementedError()

    def revision(self):
        """Returns a tuple containing the current revision and its date."""
        raise NotImplementedError()

    @staticmethod
    def get(db):
        try:
            return typeMap[db.vcsType](db)
        except KeyError:
            raise KeyError("No VCS type '{}' is known".format(db.vcsType))

    @classmethod
    def clone(cls, url, target):
        """Clones a remote repository.

        :param url: The remote repository URL.
        :type url: str
        :param target: The target directory.
        :type target: str
        """
        raise NotImplementedError()

    @staticmethod
    def getClonedDatabase(url, target, vcsType, username=None, password=None):
        vcsCls = typeMap[vcsType]
        vcsCls.clone(url, target, username=username, password=password)
        from bibtexvcs.database import Database
        return Database(target)


class MercurialInterface(VCSInterface):
    """Interface to the `Mercurial <http://mercurial.selenic.com>`_ version control system.
    """
    vcsType = 'mercurial'
    cmdline = ['hg', '--noninteractive', '--config', 'auth.x.prefix=*']

    def __init__(self, *args, **kwargs):
        super(MercurialInterface, self).__init__(*args, **kwargs)
        self.hasRemote = len(self.callHg("showconfig", "paths.default")) > 0
        self.hgid = self.callHg('id', '-i')

    def callHg(self, *args):
        """Calls the ``hg`` script in the database directory with the given arguments.
        """
        return MercurialInterface._callHg(*args, username=self.username, password=self.password,
                                          cwd=self.root)

    @classmethod
    def _callHg(cls, *args, **kwargs):
        cmdline = cls.cmdline[:]
        kwargs = kwargs.copy()
        if kwargs.get('username'):
            cmdline += ['--config', 'auth.x.username={}'.format(kwargs['username'])]
        if kwargs.get('password'):
            cmdline += ['--config', 'auth.x.password={}'.format(kwargs['password'])]
        if 'username' in kwargs:
            del kwargs['username']
        if 'password' in kwargs:
            del kwargs['password']
        env = os.environ.copy()
        env['LANG'] = 'C'
        env['LANGUAGE'] = 'C'  # on Ubuntu 12.04, LANG=C does not convince hg to use english output
        try:
            return subprocess.check_output(cmdline + list(args), env=env,
                                           stderr=subprocess.STDOUT, **kwargs)
        except subprocess.CalledProcessError as e:
            output = e.output.decode(errors='replace')
            if "authorization required" in output:
                raise AuthError('Authorization required for the mercurial repository.')
            if "authorization failed" in output:
                raise AuthError('Authorization for the mercurial repository failed.')
            if 'conflicts during merge' in output:
                raise MergeConflict('Conflict arised when merging remote and local changes!\n'
                                    'You need to fix this issue by hand. Error message:\n{}'
                                    .format(e.output))
            if 'unresolved merge conflicts' in output:
                raise MergeConflict('There are unresolved merge conflicts in your repository.\n'
                                    'You have to fix them manually before proceeding to use this '
                                    'tool.')
            raise e
        except OSError as e:
            raise VCSNotFoundError('Could not run "hg". Please install mercurial')

    def add(self, path):
        self.callHg('add', path)

    def localChanges(self):
        if len(self.callHg('status', '--modified', '--added')) > 0:
            return True
        # by this we ignore unversioned files in the base folder
        return len(self.callHg('status', '--deleted', '--unknown', self.db.documents)) > 0

    def update(self):
        if self.hasRemote:
            self.callHg('pull')
        self.callHg('update')
        newId = self.callHg('id', '-i')
        if newId != self.hgid:
            self.hgid = newId
            self.db.reload()
            return True
        return False

    def commit(self, msg=None):
        if not self.localChanges():
            return False
        if os.name != 'nt':
            with io.open(self.db.bibfilePath, 'rt', encoding='UTF-8') as bibfile:
                bib = bibfile.read()
            with io.open(self.db.bibfilePath, 'wt', encoding='UTF-8', newline='\r\n') as bibfile:
                bibfile.write(bib)
        hgOutput = self.callHg('status', '--deleted', '--no-status', self.db.documents)
        deletedDocs = hgOutput.decode(sys.getfilesystemencoding()).splitlines()
        if len(deletedDocs) > 0:
            self.callHg('remove', *deletedDocs)
        hgOutput = self.callHg('status', '--unknown', '--no-status', self.db.documents)
        newDocs = hgOutput.decode().splitlines()
        if len(newDocs) > 0:
            self.callHg('add', *newDocs)
        # TODO: sophisticated analysis of diff to current head
        self.callHg('commit', '--message', msg or 'Auto-Commit by BibTeX VCS')
        if self.hasRemote:
            self.callHg('push')
        self.db.reload()
        self.hgid = self.callHg('id', '-i')
        return True

    def revision(self):
        return self.callHg('log', '-l', '1', '--template', '{rev}\n{date|isodate}'
                           ).decode().splitlines()

    @classmethod
    def clone(cls, url, target, username=None, password=None):
        cls._callHg('clone', url, target, username=username, password=password)


class NoVCSInterface(VCSInterface):
    """Dummy VCS interface for the case of a database that is not under version control."""

    vcsType = None

    def __getattribute__(self, name):
        if name in ("add", "localChanges", "update", "commit"):
            return lambda *args, **kwargs: False
        return VCSInterface.__getattribute__(self, name)

    def revision(self):
        return None, None
