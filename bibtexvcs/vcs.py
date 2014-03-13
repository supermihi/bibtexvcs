#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

import os, subprocess
from bibtexvcs import config

class MergeConflict(Exception):
    """Raised when merge conflicts occur on a VCS update operation."""
    pass

class AuthError(Exception):
    """Raised on authentication errors when accessing remote repositories."""
    pass

typeMap = {}

class VCSMeta(type):
    def __init__(cls, name, base, namespace):
        super().__init__(name, base, namespace)
        if hasattr(cls, 'vcsType'):
            typeMap[cls.vcsType] = cls


class VCSInterface(metaclass=VCSMeta):
    """Interface to the version control system (VCS) of a :mod:`bibtexvcs` database.

    .. attribute:: username

        Optional username for authentication.
    .. attribute:: password

        Optional password for authentication.
    .. attribute:: authCallback

        Optional authentication callback function. If set, :attr:`authCallback` must be a function
        returning either ``None`` (corresponding to user abort) or a tuple reflecting the entered
        `username` and `password` information.
    """
    def __init__(self, db):
        self.db = db
        ans = config.getAuthInformation(db)
        if ans:
            self.username, self.password = ans
        else:
            self.username = self.password = None
        self.authCallback = None

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
        :type msg:  str"""
        raise NotImplementedError()

    @staticmethod
    def get(db):
        try:
            return typeMap[db.vcsType](db)
        except KeyError:
            raise KeyError("No VCS type '{}' is known".format(db.vcsType))

    @classmethod
    def clone(cls, url, target, authCallback=None):
        """Clones a remote repository.

        :param url: The remote repository URL.
        :type url: str
        :param target: The target directory.
        :type target: str
        :param authCallback: Optional function that obtains login information from the
          user, returning a triple ``(username, password, storeLogin)``.
        :type authCallback: callable
        :returns: Either ``None`` or the triple ``(username, password, storeLogin)`` where
          ``username`` is the user name, ``password`` is the password and ``storeLogin`` is a
          boolean indicating whether the given login should be stored.
        """
        raise NotImplementedError()

    @staticmethod
    def getClonedDatabase(url, target, vcsType, authCallback=None):
        vcsCls = typeMap[vcsType]
        login = vcsCls.clone(url, target, authCallback)
        from bibtexvcs.database import Database
        db = Database(target)
        if login is not None:
            db.vcs.username, db.vcs.password, store = login
            if store:
                config.setAuthInformation(db)
        return db


class MercurialInterface(VCSInterface):
    """Interface to the `Mercurial <http://mercurial.selenic.com>`_ version control system.
    """
    vcsType = 'mercurial'
    cmdline = ['hg', '--noninteractive', '--config', 'auth.x.prefix=*']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hasRemote = len(self.callHg("showconfig", "paths.default")) > 0

    def callHg(self, *args):
        """Calls the ``hg`` script in the database directory with the given arguments.
        """
        kwargs = dict(cwd=self.root)
        if self.username:
            kwargs['username'] = self.username
        if self.password:
            kwargs['password'] = self.password
        if self.authCallback is None:
            return MercurialInterface._callHg(*args, **kwargs)
        while True:
            try:
                return self._callHg(*args, **kwargs)
            except AuthError as e:
                ans = self.authCallback(message=str(e))
                if ans is None:
                    raise e
                self.username, self.password, store = ans
                kwargs['username'] = self.username
                kwargs['password'] = self.password
                if store:
                    config.setAuthInformation(self.db)

    @classmethod
    def _callHg(cls, *args, username=None, password=None, **kwargs):
        cmdline = cls.cmdline[:]
        if username:
            cmdline += ['--config', 'auth.x.username={}'.format(username)]
        if password:
            cmdline += ['--config', 'auth.x.password={}'.format(password)]
        env = os.environ.copy()
        env['LANG'] = 'C'
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

    def add(self, path):
        self.callHg('add', path)

    def localChanges(self):
        if len(self.callHg('status', '--modified', '--added')) > 0:
            return True
        # by this we ignore unversioned files in the base folder
        return len(self.callHg('status', '--deleted', '--unknown', self.db.documents)) > 0

    def update(self):
        if self.hasRemote:
            cmd = ['pull', '--update']
        else:
            cmd = ['update']
        ans = self.callHg(*cmd).decode()
        if 'no changes found' in ans:
            return False
        self.db.reload()
        return True

    def commit(self, msg=None):
        if not self.localChanges():
            return False
        self.update()  # merge potential remote changes before commiting
        hgOutput = self.callHg('status', '--deleted', '--no-status', self.db.documents)
        deletedDocs = hgOutput.decode().splitlines()
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
        return True

    @classmethod
    def clone(cls, url, target, authCallback=None):
        if authCallback is None:
            cls._callHg('clone', url, target)
            return None
        ans = None
        kwargs = dict()
        while True:
            try:
                print(kwargs)
                cls._callHg('clone', url, target, **kwargs)
                return ans
            except AuthError as e:
                ans = authCallback(message=str(e))
                if ans is None:
                    raise e
                kwargs['username'] = ans[0]
                kwargs['password'] = ans[1]


class NoVCSInterface(VCSInterface):
    """Dummy VCS interface for the case of a database that is not under version control."""

    vcsType = None

    def __getattribute__(self, name):
        if name in ("add", "localChanges", "update", "commit"):
            return lambda *args, **kwargs: False
        return super().__getattribute__(name)
