"""Correction-only commands. No command can write timing or source evidence."""
import copy
import time
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QUndoCommand, QKeySequence
from PySide6.QtWidgets import QTextEdit, QMenu

FIELDS = ('corrected_text', 'review_status', 'word_alignment_status')


def effective_text(phrase):
    text = phrase.get('corrected_text')
    return phrase['original_text'] if text is None else text


def correction_state(phrase):
    return {key: phrase[key] for key in FIELDS}


def edited_state(phrase, text):
    return dict(corrected_text=text, review_status='unreviewed',
                word_alignment_status='original_estimates' if text is None else 'phrase_only')


class EditCommand(QUndoCommand):
    def __init__(self, apply, target, before, after, label, group=None):
        super().__init__(label)
        self.apply, self.target = apply, target
        self.before, self.after = copy.deepcopy(before), copy.deepcopy(after)
        self.group, self.time = group, time.monotonic()

    def id(self):
        return 1 if self.group is not None else -1

    def mergeWith(self, other):
        if (not isinstance(other, EditCommand) or self.target != other.target or
                self.group != other.group or other.time-self.time > .8):
            return False
        self.after, self.time = other.after, other.time
        return True

    def redo(self):
        self.apply(self.target, copy.deepcopy(self.after))

    def undo(self):
        self.apply(self.target, copy.deepcopy(self.before))


class CorrectionText(QTextEdit):
    """Plain text with the project's shared, coalesced edit history.

    A single history avoids Qt text undo and project undo applying an edit twice.
    Typing commands are pushed immediately, before any later project action.
    """
    undoRequested = Signal()
    redoRequested = Signal()
    boundary = Signal()

    def __init__(self):
        super().__init__()
        self.setAcceptRichText(False)
        self.setUndoRedoEnabled(False)
        self.can_undo = lambda: False
        self.can_redo = lambda: False

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Undo):
            self.undoRequested.emit(); return
        if event.matches(QKeySequence.Redo):
            self.redoRequested.emit(); return
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down,
                           Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, Qt.Key_PageDown):
            self.boundary.emit()
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        self.boundary.emit()
        super().mousePressEvent(event)

    def focusOutEvent(self, event):
        self.boundary.emit()
        super().focusOutEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        action = menu.addAction('Undo', self.undoRequested.emit); action.setEnabled(self.can_undo())
        action = menu.addAction('Redo', self.redoRequested.emit); action.setEnabled(self.can_redo())
        menu.addSeparator()
        action = menu.addAction('Cut', self.cut); action.setEnabled(self.textCursor().hasSelection())
        action = menu.addAction('Copy', self.copy); action.setEnabled(self.textCursor().hasSelection())
        menu.addAction('Paste', self.paste)
        menu.addAction('Select all', self.selectAll)
        menu.exec(event.globalPos())
