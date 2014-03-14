#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

import functools, concurrent.futures
import os.path
from contextlib import contextmanager

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt

from bibtexvcs.vcs import MergeConflict, typeMap, AuthError, VCSInterface
from bibtexvcs.database import Database, Journal, JournalsFile, DatabaseFormatError, BTVCSCONF
from bibtexvcs import config


def standardIcon(widget, standardPixmap):
    """Helper function to generate a QIcon from a standardPixmap."""
    return widget.style().standardIcon(getattr(widget.style(), standardPixmap))


class BtVCSGui(QtWidgets.QWidget):
    """Main window of the BibTeX VCS GUI application.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BibTeX VCS")

        layout = QtWidgets.QVBoxLayout()

        dbLayout = QtWidgets.QHBoxLayout()
        self.dbLabel = QtWidgets.QLabel(self.tr("Please open a database"))
        dbSelect = QtWidgets.QPushButton(standardIcon(self, "SP_DialogOpenButton"),
                                         self.tr("Open"))
        dbSelect.setToolTip(self.tr("Open existing local checkout of a BibTeX VCS database"))
        dbSelect.clicked.connect(self.openDialog)
        dbClone = QtWidgets.QPushButton(standardIcon(self, "SP_DriveNetIcon"),
                                        self.tr("Clone"))
        dbClone.setToolTip(self.tr("Clone a BibTeX VCS database from a remote repository"))
        dbClone.clicked.connect(self.cloneDialog)

        dbLayout.addWidget(self.dbLabel)
        dbLayout.addStretch()
        dbLayout.addWidget(dbSelect)
        dbLayout.addWidget(dbClone)
        layout.addLayout(dbLayout)
        self.setLayout(layout)
        self.guiComplete = False

        # helpers for asynchronous function calls
        self.executor = concurrent.futures.ThreadPoolExecutor(1)
        self.futureTimer = QtCore.QTimer(self)
        self.futureTimer.setInterval(10)
        self.futureTimer.timeout.connect(self._updateFuture)
        self.prog = QtWidgets.QProgressDialog(self)
        self.prog.setRange(0, 0)
        self.prog.setCancelButtonText(None)
        self.prog.setWindowModality(Qt.WindowModal)

        self.db = None
        self.show()

        self.runAsync(self.tr("Opening previous database ..."),
                      self.loadDefault, config.getDefaultDatabase)

    def loadDefault(self):
        """Opens the default database as defined in :mod:`bibtexvcs`'s config file. If no default
        database is configured, nothing happens.
        """
        lastDB = self.future.result()
        if lastDB:
            self.setDB(lastDB)

    def setDB(self, db):
        """Set the current database to `db`."""
        self.db = db
        if not self.guiComplete:
            buttonLayout = QtWidgets.QHBoxLayout()
            updateButton = QtWidgets.QPushButton(standardIcon(self, "SP_ArrowDown"),
                                                 self.tr("Update"))
            updateButton.clicked.connect(self.updateRepository)
            jabrefButton = QtWidgets.QPushButton(self.tr("JabRef"))
            jabrefButton.clicked.connect(self.jabref)
            exportButton = QtWidgets.QPushButton(self.tr("Create HTML"))
            exportButton.setToolTip(self.tr('Create and open a HTML page for the database'))
            exportButton.clicked.connect(self.makeHTML)
            self.linkButton = QtWidgets.QPushButton(self.tr("Public HTML"))
            self.linkButton.clicked.connect(self.publicHTML)
            commitButton = QtWidgets.QPushButton(standardIcon(self, "SP_ArrowUp"),
                                                 self.tr("Commit"))
            commitButton.clicked.connect(self.runChecks)
            for button in updateButton, jabrefButton, exportButton, self.linkButton, commitButton:
                buttonLayout.addWidget(button)
            self.journalsTable = JournalsWidget(self.db)
            self.layout().addWidget(self.journalsTable)
            self.layout().addLayout(buttonLayout)
            self.guiComplete = True
        self.reload()
        self.updateRepository()

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
            M.critical(self, self.tr('Error Opening Database'), str(e))
        except MergeConflict as mc:
            M.critical(self, self.tr("Merge conflict"), str(mc))
        except AuthError as a:
            if onAuthEntered is not None:
                ans = LoginDialog.getLogin(self, str(a))
                if ans:
                    self.db.vcs.username, self.db.vcs.password, store = ans
                    if store:
                        config.setAuthInformation(self.db)
                    onAuthEntered()
                    return
            M.critical(self, self.tr("Authorization Required"), str(a))

    def reload(self):
        self.journalsTable.setDB(self.db)
        self.linkButton.setVisible(self.db.publicLink is not None)
        if self.db.publicLink:
            self.linkButton.setToolTip(self.db.publicLink)
        self.dbLabel.setText(self.tr("Database: <i>{}</i>").format(self.db.directory))
        self.setWindowTitle(self.tr("BibTeX VCS – {}").format(self.db.name))

    def openDialog(self):
        ans = QtWidgets.QFileDialog.getOpenFileName(self, self.tr("Select Database"), "",
                                              self.tr("BibTeX VCS configuration files ({})".format(BTVCSCONF)))
        if len(ans[0]) > 0:
            directory = os.path.dirname(ans[0])
            with self.catchExceptions():
                db = Database(directory)
                self.setDB(db)

    def cloneDialog(self):
        self.cloneDialog = CloneDialog(self)
        if self.cloneDialog.exec_() == self.cloneDialog.Accepted:
            self.login = dict()
            self.storeLogin = False
            self.cloneDB_init()

    def cloneDB_init(self):
        self.runAsync(self.tr("Cloning database ... "),
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
        self.runAsync(self.tr("Updating repository ..."),
                      self.update_handle,
                      self.db.vcs.update)

    def update_handle(self):
        with self.catchExceptions(onAuthEntered=self.updateRepository):
            changed = self.future.result()
            if changed:
                self.db.makeJournalBibfiles()
                QtWidgets.QMessageBox.information(self,
                    self.tr("Update successful"),
                    self.tr("Successfully merged remote changes"))
                self.reload()

    def jabref(self):
        try:
            self.db.runJabref()
        except FileNotFoundError as e:
            QtWidgets.QMessageBox.critical(self, self.tr('Could not start JabRef'), str(e))

    def makeHTML(self):
        html = self.db.export()
        import tempfile
        with tempfile.NamedTemporaryFile('wt', suffix='.html', delete=False, encoding='UTF-8') as f:
            f.write(html)
        import subprocess
        subprocess.Popen(['firefox', f.name])

    def publicHTML(self):
        import webbrowser
        webbrowser.open(self.db.publicLink)

    def runChecks(self):
        self.runAsync(self.tr("Performing database checks ..."),
                      self.runChecks_handle,
                      self.runChecks_init)

    def runChecks_init(self):
        from bibtexvcs import checks
        self.db.reload()
        return checks.performDatabaseCheck(self.db)

    def runChecks_handle(self):
        self.reload()
        ans = self.future.result()
        if len(ans) > 0:
            title = self.tr("Database Check Failed")
            text = self.tr('One or more database consistency checks failed. Please fix and try '
                           'again.')
            detailed = "\n\n".join(str(a) for a in ans)
            box = QtWidgets.QMessageBox(self)
            box.setWindowTitle(title)
            box.setText(text)
            box.setDetailedText(detailed)
            box.setStandardButtons(box.Close)
            box.exec_()
        else:
            self.commit_init()

    def commit_init(self):
        self.runAsync(self.tr("Committing to remote repository ..."),
                      self.commit_handle, self.db.vcs.commit)

    def commit_handle(self):
        with self.catchExceptions(onAuthEntered=self.commit_init):
            if not self.future.result():
                QtWidgets.QMessageBox.information(self,
                    self.tr("Nothing to commit"),
                    self.tr("There are no local changes."))
            else:
                QtWidgets.QMessageBox.information(self,
                    self.tr("Commit successful"),
                    self.tr("Successfully updated remote repository."))
                self.reload()
                self.db.makeJournalBibfiles()

    def closeEvent(self, event):
        if self.db and self.db.vcs.localChanges():
            ans = QtWidgets.QMessageBox.question(self,
                self.tr("Local changes present"),
                self.tr("Database was modified locally. Are you sure you want to quit "
                        "without committing the changes?"))
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

    def __init__(self, db):
        super().__init__()
        self.table = QtWidgets.QTableWidget(len(db.journals), 3)
        self.table.setHorizontalHeaderLabels([self.tr("Full"), self.tr("Abbreviated"), self.tr("Macro")])
        self.setDB(db)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

        layout = QtWidgets.QVBoxLayout()
        journalsLabel = QtWidgets.QLabel(self.tr("<h3>Journals Management</h3>"))
        newJournalButton = QtWidgets.QPushButton(self.tr("Add Journal"))
        delJournalButton = QtWidgets.QPushButton(standardIcon(self, "SP_TrashIcon"),
                                                 self.tr("Delete"))
        delJournalButton.clicked.connect(self.deleteCurrent)
        newJournalButton.clicked.connect(self.addJournal)

        buttonLayout = QtWidgets.QHBoxLayout()
        buttonLayout.addWidget(journalsLabel)
        buttonLayout.addStretch()
        buttonLayout.addWidget(newJournalButton)
        buttonLayout.addWidget(delJournalButton)
        layout.addLayout(buttonLayout)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.table.cellChanged.connect(self.updateJournalsFile)
        self.dontUpdate = False
        self.setContentsMargins(0, 0, 0, 0)
        layout.setContentsMargins(0, 0, 0, 0)

    def makeItem(self, text, editable=True):
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
            self.table.setItem(i, 0, self.makeItem(journal.full))
            self.table.setItem(i, 1, self.makeItem(journal.abbr))
            self.table.setItem(i, 2, self.makeItem(journal.macro, False))
        self.dontUpdate = False

    def deleteCurrent(self):
        currentRow = self.table.currentRow()
        self.table.removeRow(currentRow)
        self.updateJournalsFile()

    def addJournal(self):
        macro, ok = QtWidgets.QInputDialog.getText(self.parent(),
            self.tr("New Journal's Macro"),
            self.tr("Please enter the <i>Macro</i> of the new journal"))
        if not ok:
            return
        for i in range(self.table.rowCount()):
            if self.table.item(i, 2).text() == macro:
                QtWidgets.QMessageBox.critcical(self.parent(), self.tr("Macro exists"),
                    self.tr("The macro '{}' is already chosen by another journal.").format(macro))
                return
        index = self.table.rowCount()
        self.dontUpdate = True
        self.table.insertRow(index)
        self.table.setItem(index, 2, self.makeItem(macro, False))
        # initialize abbr and full with the macro
        self.table.setItem(index, 0, self.makeItem(macro))
        self.dontUpdate = False
        self.table.setItem(index, 1, self.makeItem(macro))

    def updateJournalsFile(self):
        if self.dontUpdate:
            return
        journals = []
        for i in range(self.table.rowCount()):
            journals.append(Journal(full=self.table.item(i, 0).text(),
                                    abbr=self.table.item(i, 1).text(),
                                    macro=self.table.item(i, 2).text()))
        jFile = JournalsFile(journals=journals)
        jFile.write(self.db.journalsPath)


class CloneDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QGridLayout()
        self.urlEdit = QtWidgets.QLineEdit()
        self.urlEdit.setPlaceholderText(self.tr("remote repository URL"))
        layout.addWidget(QtWidgets.QLabel(self.tr("URL:")), 0, 0)
        layout.addWidget(self.urlEdit, 0, 1)
        self.vcsTypeChooser = QtWidgets.QComboBox()
        self.vcsTypeChooser.addItems([t for t in typeMap if t is not None])
        layout.addWidget(self.vcsTypeChooser, 0, 2)
        layout.addWidget(QtWidgets.QLabel(self.tr("Target:")), 1, 0)
        self.targetEdit = QtWidgets.QLineEdit()
        self.targetEdit.setPlaceholderText(self.tr("local checkout directory"))
        layout.addWidget(self.targetEdit, 1, 1)
        chooseTargetButton = QtWidgets.QPushButton(self.tr("Choose..."))
        chooseTargetButton.clicked.connect(self.chooseTarget)
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
        self.setLayout(layout)

    def checkOk(self):
        ok = all((edit.text().strip() != '' for edit in (self.targetEdit, self.urlEdit)))
        self.btbx.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(ok)

    def chooseTarget(self):
        target = QtWidgets.QFileDialog.getExistingDirectory(self, self.tr("Choose Target"))
        if target:
            self.targetEdit.setText(target)


class LoginDialog(QtWidgets.QDialog):

    def __init__(self, message=None, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QGridLayout()
        if message:
            layout.addWidget(QtWidgets.QLabel(message), 0, 0, 1, 2)
        layout.addWidget(QtWidgets.QLabel(self.tr('User:')), 1, 0)
        layout.addWidget(QtWidgets.QLabel(self.tr('Password:')), 2, 0)
        self.userEdit = QtWidgets.QLineEdit()
        self.userEdit.setPlaceholderText(self.tr('enter username'))
        layout.addWidget(self.userEdit, 1, 1)
        self.passEdit = QtWidgets.QLineEdit()
        self.passEdit.setPlaceholderText(self.tr('enter password'))
        self.passEdit.setEchoMode(QtWidgets.QLineEdit.Password)
        layout.addWidget(self.passEdit, 2, 1)
        self.storeBox = QtWidgets.QCheckBox(self.tr("Remember login"))
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
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = BtVCSGui()
    app.exec_()

if __name__ == '__main__':
    run()
