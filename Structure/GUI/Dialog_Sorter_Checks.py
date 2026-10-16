"""
Sicherheits- und Vorprüfungsdialoge vor dem Start des LoadOrder Sorters.
"""

import sys
import ctypes
from PySide6.QtWidgets import QMessageBox, QWidget
from PySide6.QtGui import QIcon

from Structure.Database import check_sorter_prerequisites, apply_all_classifier_categories
from Structure.GUI.UI_Theme import set_dark_title_bar


def _show_custom_message_box(
    parent: QWidget | None,
    title: str,
    text: str,
    icon: QMessageBox.Icon,
    buttons: list[tuple[str, QMessageBox.ButtonRole]]
) -> str | None:
    """
    Zeigt eine angepasste QMessageBox mit dunkler Titelleiste und deutschen Schaltflächen an.
    Gibt die Beschriftung der geklickten Schaltfläche zurück.
    """
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(icon)

    if parent and parent.windowIcon():
        msg_box.setWindowIcon(parent.windowIcon())

    set_dark_title_bar(msg_box)

    btn_map = {}
    default_btn = None
    for label, role in buttons:
        btn = msg_box.addButton(label, role)
        btn_map[btn] = label
        if role in (QMessageBox.ButtonRole.RejectRole, QMessageBox.ButtonRole.NoRole):
            default_btn = btn

    if default_btn:
        msg_box.setDefaultButton(default_btn)

    msg_box.exec()
    clicked = msg_box.clickedButton()
    return btn_map.get(clicked)


def check_and_confirm_sorter_start(parent: QWidget | None = None) -> bool:
    """
    Führt die vollständige Prüf- und Dialogkette für den LoadOrder Sorter aus:
    - Prüfung 0: Gibt es überhaupt installierte Mods (State = 1)?
    - Prüfung 1: Sind alle Kategorien (Category_LOH) zugeordnet?
    - Prüfung 2: Gibt es neuere Mods als den letzten Kategorisierer- oder Konflikt-Lauf?
    - Prüfung 3: Gibt es Abweichungen zwischen Category_LOH und Category_LOH_Classifier?

    Gibt True zurück, wenn der Sorter gestartet werden darf, andernfalls False.
    """
    # 1. Daten ermitteln
    prereqs = check_sorter_prerequisites()

    installed_count = prereqs.get("installed_mods_count", 0)
    unassigned_loh = prereqs.get("unassigned_loh_count", 0)
    unassigned_classifier = prereqs.get("unassigned_classifier_count", 0)
    has_newer_mods = prereqs.get("has_newer_mods", False)
    diff_count = prereqs.get("diff_categories_count", 0)

    # ---------------------------------------------------------
    # Prüfung 0: Keine aktiven Mods vorhanden
    # ---------------------------------------------------------
    if installed_count == 0:
        _show_custom_message_box(
            parent,
            "Keine aktiven Mods",
            "Es sind keine aktiven Mods installiert. Eine Sortierung kann nicht durchgeführt werden.",
            QMessageBox.Icon.Information,
            [("OK", QMessageBox.ButtonRole.AcceptRole)]
        )
        return False

    # ---------------------------------------------------------
    # Prüfung 1: Sind nicht alle Kategorien belegt?
    # ---------------------------------------------------------
    if unassigned_loh > 0:
        # Fall 1a: Kategorisierer ist vollständig und aktuell
        if unassigned_classifier == 0 and not has_newer_mods:
            text = (
                "Es müssen alle Kategorien zugeordnet sein. Sollen die ermittelten "
                "Kategorien aus dem Kategorisierer übernommen werden?\n\n"
                "Bereits manuell zugewiesene Kategorien werden dabei überschrieben."
            )
            choice = _show_custom_message_box(
                parent,
                "Kategorien unvollständig",
                text,
                QMessageBox.Icon.Question,
                [
                    ("Übernehmen", QMessageBox.ButtonRole.YesRole),
                    ("Abbrechen", QMessageBox.ButtonRole.RejectRole)
                ]
            )
            if choice == "Übernehmen":
                updated = apply_all_classifier_categories()
                if updated >= 0:
                    # Nach Übernahme ist alles synchronisiert -> Sorter darf starten
                    return True
                else:
                    _show_custom_message_box(
                        parent,
                        "Datenbankfehler",
                        "Beim Übernehmen der Kategorisierer-Kategorien ist ein Fehler aufgetreten.",
                        QMessageBox.Icon.Critical,
                        [("OK", QMessageBox.ButtonRole.AcceptRole)]
                    )
                    return False
            else:
                return False

        # Fall 1b: Kategorisierer ist belegt, aber nicht aktuell
        elif unassigned_classifier == 0 and has_newer_mods:
            text = "Es gibt neu installierte Mods. Sie sollten den Kategorisierer und die Konfliktanalyse ausführen."
            _show_custom_message_box(
                parent,
                "Neu installierte Mods",
                text,
                QMessageBox.Icon.Warning,
                [("Abbrechen", QMessageBox.ButtonRole.RejectRole)]
            )
            return False

        # Fall 1c: Kategorisierer ist ebenfalls unvollständig
        else:
            text = (
                "Es sind nicht allen Mods Kategorien zugewiesen und auch das Ergebnis "
                "des Kategorisierers ist unvollständig. Bitte führen Sie zuerst den Kategorisierer aus."
            )
            _show_custom_message_box(
                parent,
                "Kategorien unvollständig",
                text,
                QMessageBox.Icon.Warning,
                [("Abbrechen", QMessageBox.ButtonRole.RejectRole)]
            )
            return False

    # ---------------------------------------------------------
    # Prüfung 2: Alle Kategorien belegt, aber neuere Mods vorhanden
    # ---------------------------------------------------------
    if has_newer_mods:
        text = (
            "Sie haben neue Mods installiert, welche noch nicht durch den Kategorisierer "
            "und / oder der Konflikanalyse überprüft wurden. Es wird empfohlen diese zuvor auszuführen.\n\n"
            "Möchten Sie die Sortierung dennoch fortsetzen?"
        )
        choice = _show_custom_message_box(
            parent,
            "Neu installierte Mods",
            text,
            QMessageBox.Icon.Warning,
            [
                ("Trotzdem fortfahren", QMessageBox.ButtonRole.AcceptRole),
                ("Abbrechen", QMessageBox.ButtonRole.RejectRole)
            ]
        )
        if choice != "Trotzdem fortfahren":
            return False

    # ---------------------------------------------------------
    # Prüfung 3: Abweichungen zwischen Category_LOH und Kategorisierer
    # ---------------------------------------------------------
    if diff_count > 0:
        text = (
            "Es gibt Abweichungen zwischen den zugewiesenen Kategorien und den Ergebnissen "
            "des Kategorisierers. Möchten Sie die Ergebnisse des Kategorisierers übernehmen?\n\n"
            "Bereits manuell zugewiesene Kategorien werden dabei überschrieben."
        )
        choice = _show_custom_message_box(
            parent,
            "Abweichende Kategorien",
            text,
            QMessageBox.Icon.Question,
            [
                ("Kategorisierer übernehmen", QMessageBox.ButtonRole.YesRole),
                ("Bestehende beibehalten", QMessageBox.ButtonRole.NoRole),
                ("Abbrechen", QMessageBox.ButtonRole.RejectRole)
            ]
        )
        if choice == "Kategorisierer übernehmen":
            updated = apply_all_classifier_categories()
            if updated >= 0:
                return True
            else:
                _show_custom_message_box(
                    parent,
                    "Datenbankfehler",
                    "Beim Übernehmen der Kategorisierer-Kategorien ist ein Fehler aufgetreten.",
                    QMessageBox.Icon.Critical,
                    [("OK", QMessageBox.ButtonRole.AcceptRole)]
                )
                return False
        elif choice == "Bestehende beibehalten":
            return True
        else:
            return False

    # ---------------------------------------------------------
    # Prüfung 4: Alles vollständig, konsistent und freigegeben
    # ---------------------------------------------------------
    return True
