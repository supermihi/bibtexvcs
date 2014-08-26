#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

from __future__ import division, print_function, unicode_literals
import concurrent.futures
import sys
import traceback
from contextlib import contextmanager


# we support PyQt5, PyQt4 and PySide
nullString = None
try:
    from PyQt5 import QtWidgets, QtCore
    from PyQt5.QtCore import Qt
    QT5 = True
except ImportError:
    QT5 = False
    try:
        from PyQt4 import QtGui, QtCore
        from PyQt4.QtCore import Qt
        QtWidgets = QtGui
        nullString = QtCore.QString()
    except ImportError:
        from PySide import QtGui, QtCore
        from PySide.QtCore import Qt
        QtWidgets = QtGui

from bibtexvcs.vcs import MergeConflict, typeMap, AuthError, VCSNotFoundError, VCSInterface
from bibtexvcs.database import Database, Journal, JournalsFile, DatabaseFormatError
from bibtexvcs import config


def standardIcon(widget, standardPixmap):
    """Helper function to generate a QIcon from a standardPixmap."""
    return widget.style().standardIcon(getattr(widget.style(), standardPixmap))


class BtVCSGui(QtWidgets.QWidget):
    """Main window of the BibTeX VCS GUI application.
    """

    def __init__(self):
        super(BtVCSGui, self).__init__()
        self.setWindowTitle("BibTeX VCS")

        dbLayout = QtWidgets.QHBoxLayout()
        self.dbLabel = QtWidgets.QLabel("Please open a database")
        dbSelect = QtWidgets.QPushButton(standardIcon(self, 'SP_DialogOpenButton'), '&Open')
        dbSelect.setToolTip('Open existing local checkout of a BibTeX VCS database')
        dbSelect.clicked.connect(self.openDialog)
        dbClone = QtWidgets.QPushButton(standardIcon(self, 'SP_DriveNetIcon'), '&Clone')
        dbClone.setToolTip('Clone a BibTeX VCS database from a remote repository')
        dbClone.clicked.connect(self.cloneDialog)

        dbLayout.addWidget(self.dbLabel)
        dbLayout.addStretch()
        dbLayout.addWidget(dbSelect)
        dbLayout.addWidget(dbClone)
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(dbLayout)
        self.linkLabel = QtWidgets.QLabel('')
        self.linkLabel.setOpenExternalLinks(True)
        layout.addWidget(self.linkLabel)
        self.setLayout(layout)
        self.guiComplete = False

        # helpers for asynchronous function calls (see runAsync())
        self.executor = concurrent.futures.ThreadPoolExecutor(1)
        self.futureTimer = QtCore.QTimer(self)
        self.futureTimer.setInterval(20)
        self.futureTimer.timeout.connect(self._updateFuture)
        self.prog = QtWidgets.QProgressDialog(self)
        self.prog.setRange(0, 0)
        self.prog.setCancelButtonText(nullString)
        self.prog.setWindowModality(Qt.WindowModal)

        self.db = None
        self.show()
        self.runAsync("Opening previous database ...", self.loadDefault, config.getDefaultDatabase)

    def loadDefault(self):
        """Opens the default database as defined in :mod:`bibtexvcs`'s config file. If no default
        database is configured, nothing happens.
        """
        with self.catchExceptions():
            lastDB = self.future.result()
            if lastDB:
                self.setDB(lastDB)

    def setDB(self, db):
        """Set the current database to `db`."""
        self.db = db
        if not self.guiComplete:
            buttonLayout = QtWidgets.QHBoxLayout()
            updateButton = QtWidgets.QPushButton(standardIcon(self, 'SP_ArrowDown'), '&1: Update')
            updateButton.clicked.connect(self.updateRepository)
            jabrefButton = QtWidgets.QPushButton('&2: JabRef')
            jabrefButton.clicked.connect(self.jabref)
            commitButton = QtWidgets.QPushButton(standardIcon(self, 'SP_ArrowUp'), '&3: Commit')
            commitButton.clicked.connect(self.runChecks)
            for button in updateButton, jabrefButton, commitButton:
                buttonLayout.addWidget(button)
            self.journalsTable = JournalsWidget(self.db)
            self.layout().addWidget(self.journalsTable)
            self.layout().addLayout(buttonLayout)
            self.guiComplete = True
        self.reload()
        self.updateRepository()

    def reload(self):
        self.journalsTable.setDB(self.db)
        if self.db.publicLink:
            self.linkLabel.setText('Web: <a href="{0}">{0}</a>'.format(self.db.publicLink))
        self.linkLabel.setVisible(self.db.publicLink is not None)
        self.dbLabel.setText('Database: <i>{}</i><br />r. {}, changed {}'
                             .format(self.db.directory, *self.db.vcs.revision()))
        self.setWindowTitle("BibTeX VCS: {}".format(self.db.name))

    def runAsync(self, labelText, finishedCall, fn, *args, **kwargs):
        """Helper function for asynchronous calls during which a progress dialog is shown. The
        progress dialog will be labelled by `labelText`.

        `finishedCall` is an optional callable that will be called after `fn` has finished running.

        `fn` is the callable to be run asynchronously. Additional arguments are passed to this
        function.
        """
        self.prog.setLabelText(labelText)
        self.prog.show()
        self.finishedCall = finishedCall
        self.future = self.executor.submit(fn, *args, **kwargs)
        self.futureTimer.start()

    def _updateFuture(self):
        if self.future.done():
            self.futureTimer.stop()
            self.prog.close()
            if self.finishedCall:
                self.finishedCall()

    @contextmanager
    def catchExceptions(self, onAuthEntered=None):
        """Contextmanager catching common exceptions and displaying message boxes if they occur.

        The caught exceptions are :class:`DatabaseFormatError`, :class:`MergeConflict` and
        :class:`AuthError`.

        `onAuthEntered` is an optional callable. If it is provided and an :class:`AuthError` is
        caught, the following happens:
        - A :class:`LoginDialog` is shown to ask the user for a login,
        - if the dialog is canceled, the :class:`AuthError` is re-raised
        - otherwise, the function `onAuthEntered` is called.

        If the `store login` checkbox in the :class:`LoginDialog` was checked, the information is
        set to `self.db.vcs` and :fun:`config.setAuthInformation` is called.
        """
        M = QtWidgets.QMessageBox
        try:
            yield
        except DatabaseFormatError as e:
            M.critical(self, 'Error Opening Database', str(e))
        except MergeConflict as mc:
            M.critical(self, "Merge conflict", str(mc))
        except AuthError as a:
            if onAuthEntered is not None:
                ans = LoginDialog.getLogin(self, str(a))
                if ans:
                    self.db.vcs.username, self.db.vcs.password, store = ans
                    if store:
                        config.setAuthInformation(self.db)
                    onAuthEntered()
                    return
            M.critical(self, "Authorization Required", str(a))
        except VCSNotFoundError as e:
            M.critical(self, 'VCS program not found', str(e))
        except Exception as e:
            M.critical(self, 'Unhandled {}'.format(type(e)), traceback.format_exc())

    def openDialog(self):
        ans = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Database")
        if ans:
            with self.catchExceptions():
                db = Database(ans)
                self.setDB(db)

    def cloneDialog(self):
        self.cloneDialog = CloneDialog(self)
        if self.cloneDialog.exec_() == self.cloneDialog.Accepted:
            self.login = dict()
            self.storeLogin = False
            self.cloneDB_init()

    def cloneDB_init(self):
        self.runAsync("Cloning database ... ",
                      self.cloneDB_handle,
                      VCSInterface.getClonedDatabase,
                      self.cloneDialog.urlEdit.text(),
                      self.cloneDialog.targetEdit.text(),
                      self.cloneDialog.vcsTypeChooser.currentText(),
                      **self.login)

    def cloneDB_handle(self):
        with self.catchExceptions():
            try:
                self.setDB(self.future.result())
                if self.storeLogin:
                    config.setAuthInformation(self.db)
            except AuthError as e:
                ans = LoginDialog.getLogin(self, str(e))
                if ans:
                    self.login['username'], self.login['password'], self.storeLogin = ans
                    self.cloneDB_init()
                else:
                    raise e

    def updateRepository(self):
        self.runAsync("Updating repository ...", self.update_handle, self.db.vcs.update)

    def update_handle(self):
        with self.catchExceptions(onAuthEntered=self.updateRepository):
            changed = self.future.result()
            if changed:
                QtWidgets.QMessageBox.information(self,
                        "Update successful", "Successfully merged remote changes")
                self.reload()

    def jabref(self):
        try:
            self.db.runJabref()
        except FileNotFoundError as e:
            QtWidgets.QMessageBox.critical(self, 'Could not start JabRef', str(e))

    def runChecks(self):
        self.runAsync("Performing database checks ...", self.runChecks_handle, self.runChecks_init)

    def runChecks_init(self):
        from bibtexvcs import checks
        self.db.reload()
        return checks.performDatabaseCheck(self.db)

    def runChecks_handle(self):
        self.reload()
        errors, warnings = self.future.result()
        if len(errors) > 0:
            title = "Database Check Failed"
            text = 'One or more database checks failed. Please fix, then try again.'
            detailed = "\n\n".join(err.args[0] for err in errors)
            box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, title, text, parent=self)
            box.setDetailedText(detailed)
            box.setStandardButtons(box.Close)
            box.exec_()
        elif len(warnings) > 0:
            box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, 'Warning',
                    'All checks passed, but some warnings occured. Proceed anyway?', parent=self)
            box.setDetailedText("\n\n".join(war.args[0] for war in warnings))
            box.setStandardButtons(box.Yes | box.No)
            if box.exec_() == box.Yes:
                self.commit_init()
        else:
            self.commit_init()

    def commit_init(self):
        self.runAsync("Committing repository ...", self.commit_handle, self.db.vcs.commit)

    def commit_handle(self):
        with self.catchExceptions(onAuthEntered=self.commit_init):
            if not self.future.result():
                QtWidgets.QMessageBox.information(self, "No Local Changes", "Nothing to commit.")
            else:
                QtWidgets.QMessageBox.information(self, "Commit successful", "Commit successful.")
                self.reload()

    def closeEvent(self, event):
        if self.db and self.db.vcs.localChanges():
            ans = QtWidgets.QMessageBox.question(self, "Local changes present",
                    "Database was modified locally. Are you sure you want to quit "
                    "without committing the changes?",
                    QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Yes)
            if ans == QtWidgets.QMessageBox.Yes:
                config.setDefaultDatabase(self.db)
                event.accept()
            else:
                event.ignore()
        else:
            if self.db:
                config.setDefaultDatabase(self.db)
            event.accept()


class JournalsWidget(QtWidgets.QWidget):
    """Widget for displaying the journal abbreviations, including buttons to add/remove entries."""
    def __init__(self, db):
        super(JournalsWidget, self).__init__()
        self.table = QtWidgets.QTableWidget(len(db.journals), 3)
        self.table.setHorizontalHeaderLabels(['Macro', 'Abbreviated', 'Full'])
        self.setDB(db)
        fName = 'setSectionResizeMode' if QT5 else 'setResizeMode'
        getattr(self.table.horizontalHeader(), fName)(2, QtWidgets.QHeaderView.ResizeToContents)
        for i in range(1,3):
            getattr(self.table.horizontalHeader(), fName)(i, QtWidgets.QHeaderView.Interactive)

        getattr(self.table.verticalHeader(), fName)(QtWidgets.QHeaderView.ResizeToContents)
        layout = QtWidgets.QVBoxLayout()
        journalsLabel = QtWidgets.QLabel('<h3>Journals Management</h3>')
        self.searchEdit = QtWidgets.QLineEdit()
        self.searchEdit.textChanged.connect(self.search)
        newJournalButton = QtWidgets.QPushButton('&Add Journal')
        delJournalButton = QtWidgets.QPushButton(standardIcon(self, 'SP_TrashIcon'), '&Delete')
        delJournalButton.clicked.connect(self.deleteCurrent)
        newJournalButton.clicked.connect(self.addJournal)

        buttonLayout = QtWidgets.QHBoxLayout()
        buttonLayout.addWidget(journalsLabel)
        buttonLayout.addWidget(self.searchEdit)
        buttonLayout.addStretch()
        buttonLayout.addWidget(newJournalButton)
        buttonLayout.addWidget(delJournalButton)
        layout.addLayout(buttonLayout)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.table.cellChanged.connect(self.updateJournalsFile)
        self.dontUpdate = False
        layout.setContentsMargins(0, 0, 0, 0)

    def search(self, text):
        for row in range(self.table.rowCount()):
            hide = True
            for col in range(self.table.columnCount()):
                if text in self.table.item(row, col).text():
                    hide = False
                    break
            self.table.setRowHidden(row, hide)

    @staticmethod
    def makeItem(text, editable=True):
        item = QtWidgets.QTableWidgetItem(text)
        if not editable:
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        return item

    def setDB(self, db):
        self.db = db
        self.dontUpdate = True
        self.table.clearContents()
        self.table.setRowCount(len(self.db.journals))
        for i, journal in enumerate(self.db.journals.values()):
            self.table.setItem(i, 0, self.makeItem(journal.macro, False))
            self.table.setItem(i, 1, self.makeItem(journal.abbr))
            self.table.setItem(i, 2, self.makeItem(journal.full))
        self.dontUpdate = False
        self.table.horizontalHeader().resizeSections(QtWidgets.QHeaderView.ResizeToContents)

    def deleteCurrent(self):
        currentRow = self.table.currentRow()
        self.table.removeRow(currentRow)
        self.updateJournalsFile()

    def addJournal(self):
        macro, ok = QtWidgets.QInputDialog.getText(self.parent(), "New Journal's Macro",
                'Please enter the <i>Macro</i> of the new journal')
        if not ok:
            return
        for i in range(self.table.rowCount()):
            if self.table.item(i, 2).text() == macro:
                QtWidgets.QMessageBox.critcical(self.parent(), 'Macro exists',
                        "The macro '{}' is already in use by another journal".format(macro))
                return
        index = self.table.rowCount()
        self.dontUpdate = True
        self.table.insertRow(index)
        self.table.setItem(index, 2, self.makeItem(macro))
        # initialize abbr and full with the macro
        self.table.setItem(index, 0, self.makeItem(macro, False))
        self.dontUpdate = False
        self.table.setItem(index, 1, self.makeItem(macro))
        self.table.selectRow(index)

    def updateJournalsFile(self):
        if self.dontUpdate:
            return
        journals = []
        for i in range(self.table.rowCount()):
            macro, abbr, full = [self.table.item(i, j).text() for j in (0, 1, 2)]
            if sys.version_info.major == 2 and not isinstance(full, unicode):
                full, abbr, macro = [unicode(s) for s in (full, abbr, macro)]
            journals.append(Journal(full=full, abbr=abbr, macro=macro))
        self.db.journals = JournalsFile(journals=journals)
        self.db.journals.write(self.db.journalsPath)
        self.db.makeJournalBibfiles()


class CloneDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(CloneDialog, self).__init__(parent)
        layout = QtWidgets.QGridLayout()
        self.urlEdit = QtWidgets.QLineEdit()
        self.urlEdit.setPlaceholderText("remote repository URL")
        layout.addWidget(QtWidgets.QLabel("URL:"), 0, 0)
        layout.addWidget(self.urlEdit, 0, 1)
        self.vcsTypeChooser = QtWidgets.QComboBox()
        self.vcsTypeChooser.addItems([t for t in typeMap if t is not None])
        layout.addWidget(self.vcsTypeChooser, 0, 2)
        layout.addWidget(QtWidgets.QLabel('Target:'), 1, 0)
        self.targetEdit = QtWidgets.QLineEdit()
        self.targetEdit.setPlaceholderText('local checkout directory')
        layout.addWidget(self.targetEdit, 1, 1)
        chooseTargetButton = QtWidgets.QPushButton('Choose...')
        chooseTargetButton.clicked.connect(lambda: self.targetEdit.setText(
                QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose Target')))
        layout.addWidget(chooseTargetButton, 1, 2)
        Ok = QtWidgets.QDialogButtonBox.Ok
        Cancel = QtWidgets.QDialogButtonBox.Cancel
        self.btbx = QtWidgets.QDialogButtonBox(Cancel | Ok)
        self.btbx.button(Ok).setEnabled(False)
        layout.addWidget(self.btbx, 2, 0, 1, 3)
        layout.setColumnMinimumWidth(1, 250)
        self.btbx.rejected.connect(self.reject)
        self.btbx.accepted.connect(self.accept)
        self.targetEdit.textChanged.connect(self.checkOk)
        self.urlEdit.textChanged.connect(self.checkOk)
        self.setLayout(layout)

    def checkOk(self):
        ok = all((edit.text().strip() != '' for edit in (self.targetEdit, self.urlEdit)))
        self.btbx.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(ok)


class LoginDialog(QtWidgets.QDialog):

    def __init__(self, message=None, parent=None):
        super(LoginDialog, self).__init__(parent)

        layout = QtWidgets.QGridLayout()
        if message:
            layout.addWidget(QtWidgets.QLabel(message), 0, 0, 1, 2)
        layout.addWidget(QtWidgets.QLabel('User:'), 1, 0)
        layout.addWidget(QtWidgets.QLabel('Password:'), 2, 0)
        self.userEdit = QtWidgets.QLineEdit()
        self.userEdit.setPlaceholderText('enter username')
        layout.addWidget(self.userEdit, 1, 1)
        self.passEdit = QtWidgets.QLineEdit()
        self.passEdit.setPlaceholderText('enter password')
        self.passEdit.setEchoMode(QtWidgets.QLineEdit.Password)
        layout.addWidget(self.passEdit, 2, 1)
        self.storeBox = QtWidgets.QCheckBox('Remember login')
        layout.addWidget(self.storeBox, 3, 1)
        btbx = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel |
                                          QtWidgets.QDialogButtonBox.Ok)
        btbx.accepted.connect(self.accept)
        btbx.rejected.connect(self.reject)
        layout.addWidget(btbx, 4, 0, 1, 2)
        self.setLayout(layout)

    @staticmethod
    def getLogin(parent=None, message=None):
        dialog = LoginDialog(parent=parent, message=message)
        if dialog.exec_() == dialog.Accepted:
            return dialog.userEdit.text(), dialog.passEdit.text(), dialog.storeBox.isChecked()
        return None


def run():
    if len (sys.argv) > 1 and sys.argv[1] == '-j':
        config.getDefaultDatabase().runJabref()
        sys.exit(0)
    import bibtexvcs, pkg_resources
    from distutils.version import StrictVersion
    app = QtWidgets.QApplication(sys.argv)
    window = None
    newVersion = bibtexvcs.pypiVersion()
    if newVersion:
        newVersion = StrictVersion(newVersion)
        myVersion = StrictVersion(pkg_resources.get_distribution('bibtexvcs').version)
        if newVersion > myVersion:
            window = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical,
                                           "New version available",
                                           "A new version of BibTeX VCS ({}) is available. "
                                           "Please update (pip install -U --user bibtexvcs), "
                                           "then start again.".format(newVersion),
                                           QtWidgets.QMessageBox.Ok)
            window.show()
            window.accepted.connect(app.exit)
    if window is None:
        window = BtVCSGui()
    app.exec_()

if __name__ == '__main__':
    run()
