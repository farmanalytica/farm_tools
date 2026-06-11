from qgis.PyQt.QtCore import Qt, QCoreApplication, pyqtSignal
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QWidget,
    QCheckBox,
    QPushButton,
    QLabel,
    QFrame,
    QDialogButtonBox,
)
import pandas as pd

from .styles import STYLE_BTN_PRIMARY, STYLE_BTN_SECONDARY, STYLE_CHECKBOX


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_DIALOG_STYLE = (
    "QDialog { background-color: #ffffff; color: #212121; }"
    "QLabel { background: transparent; border: none; }"
    + STYLE_CHECKBOX
)


class SARDateFilterDialog(QDialog):
    filter_changed = pyqtSignal(list)

    def __init__(self, dates, active_dates=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_tr("Filter Dates"))
        self.setGeometry(100, 100, 500, 620)
        self.setMinimumWidth(480)
        self.setMinimumHeight(450)
        self.setStyleSheet(_DIALOG_STYLE)

        self._dates = dates
        self._active_dates = active_dates
        self._initial_active_dates = active_dates
        self._date_checkboxes = []
        self._month_checkboxes = {}
        self._year_checkboxes = {}
        self._month_widgets = {}
        self._month_headers = {}
        self._updating = False

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #e0e0e0; border-radius: 4px; }"
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)

        df = pd.DataFrame({"dates": pd.to_datetime(self._dates)})
        grouped_by_year = df.groupby(df["dates"].dt.year)

        for year in sorted(grouped_by_year.groups.keys()):
            year_months = df[df["dates"].dt.year == year].groupby(
                df["dates"].dt.month
            )

            year_header = QLabel(str(year))
            year_font = QFont()
            year_font.setPointSize(11)
            year_font.setBold(True)
            year_header.setFont(year_font)
            year_header.setStyleSheet("color: #1b6b39; margin-top: 8px;")
            scroll_layout.addWidget(year_header)

            year_checkbox = QCheckBox(_tr("Select all in this year"))
            year_checkbox.setFont(QFont())
            year_checkbox.setStyleSheet(
                "QCheckBox { color: #616161; font-size: 11px; margin-left: 8px; }"
            )
            year_checkbox.stateChanged.connect(
                lambda state, yr=year: self._toggle_year(yr, state)
            )
            year_checkbox.setChecked(
                True
                if self._active_dates is None
                else all(
                    str(d.date()) in self._active_dates
                    for d in df[df["dates"].dt.year == year]["dates"]
                )
            )
            self._year_checkboxes[year] = year_checkbox
            scroll_layout.addWidget(year_checkbox)

            months_container = QWidget()
            months_container.setStyleSheet("background: transparent;")
            months_layout = QVBoxLayout(months_container)
            months_layout.setContentsMargins(12, 4, 0, 0)
            months_layout.setSpacing(8)

            for month in sorted(year_months.groups.keys()):
                month_key = f"{year:04d}-{month:02d}"
                month_dates = df[
                    (df["dates"].dt.year == year) & (df["dates"].dt.month == month)
                ]["dates"]
                month_count = len(month_dates)

                month_card = self._create_month_card(
                    month_key, month_dates, month_count
                )
                months_layout.addWidget(month_card)

            scroll_layout.addWidget(months_container)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, 1)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        select_all_btn = QPushButton(_tr("Select All"))
        select_all_btn.setMaximumWidth(120)
        select_all_btn.setFixedHeight(30)
        select_all_btn.setStyleSheet(STYLE_BTN_SECONDARY)
        select_all_btn.clicked.connect(self._select_all)
        deselect_all_btn = QPushButton(_tr("Deselect All"))
        deselect_all_btn.setMaximumWidth(120)
        deselect_all_btn.setFixedHeight(30)
        deselect_all_btn.setStyleSheet(STYLE_BTN_SECONDARY)
        deselect_all_btn.clicked.connect(self._deselect_all)
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setStyleSheet(STYLE_BTN_PRIMARY)
        ok_btn.setFixedHeight(32)
        ok_btn.setMinimumWidth(96)
        cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setStyleSheet(STYLE_BTN_SECONDARY)
        cancel_btn.setFixedHeight(32)
        cancel_btn.setMinimumWidth(96)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self._on_cancel)
        main_layout.addWidget(button_box)

    def _create_month_card(self, month_key, month_dates, month_count):
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(
            "QFrame { border: 1px solid #e8e8e8; border-radius: 4px; "
            "background: #fafafa; padding: 8px; }"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        month_header_layout = QHBoxLayout()
        month_header_layout.setContentsMargins(0, 0, 0, 0)
        month_header_layout.setSpacing(8)

        month_checkbox = QCheckBox(month_key)
        month_checkbox.setStyleSheet(
            "QCheckBox { color: #333333; font-weight: 500; font-size: 11px; }"
        )
        month_checkbox.stateChanged.connect(
            lambda state, mk=month_key: self._toggle_month(mk, state)
        )
        month_checkbox.setChecked(
            True
            if self._active_dates is None
            else all(str(d.date()) in self._active_dates for d in month_dates)
        )
        self._month_checkboxes[month_key] = month_checkbox
        month_header_layout.addWidget(month_checkbox)

        count_label = QLabel(f"({sum(1 for d in month_dates if str(d.date()) in (self._active_dates or [str(x.date()) for x in month_dates]))}/{month_count})")
        count_label.setStyleSheet("color: #999999; font-size: 10px;")
        month_header_layout.addWidget(count_label)
        self._month_headers[month_key] = count_label

        month_header_layout.addStretch()
        layout.addLayout(month_header_layout)

        dates_layout = QHBoxLayout()
        dates_layout.setContentsMargins(0, 0, 0, 0)
        dates_layout.setSpacing(6)

        dates_container = QWidget()
        dates_grid = QVBoxLayout(dates_container)
        dates_grid.setContentsMargins(0, 0, 0, 0)
        dates_grid.setSpacing(3)

        dates_list = sorted(month_dates)
        for date in dates_list:
            date_str = str(date.date())
            date_checkbox = QCheckBox(date_str)
            date_checkbox.setStyleSheet(
                "QCheckBox { color: #555555; font-size: 10px; padding: 2px; }"
            )
            date_checkbox.setChecked(
                True
                if self._active_dates is None
                else date_str in self._active_dates
            )
            date_checkbox.stateChanged.connect(
                lambda checked, mk=month_key: self._on_date_changed(mk)
            )
            dates_grid.addWidget(date_checkbox)
            self._date_checkboxes.append((date_checkbox, month_key))

        dates_layout.addWidget(dates_container)
        dates_layout.addStretch()
        layout.addLayout(dates_layout)

        self._month_widgets[month_key] = card
        return card

    def _toggle_year(self, year, state):
        is_checked = state == Qt.CheckState.Checked
        for month_key in list(self._month_checkboxes.keys()):
            if int(month_key.split("-")[0]) == year:
                self._month_checkboxes[month_key].blockSignals(True)
                self._month_checkboxes[month_key].setChecked(is_checked)
                self._month_checkboxes[month_key].blockSignals(False)

                for cb, mk in self._date_checkboxes:
                    if mk == month_key:
                        cb.blockSignals(True)
                        cb.setChecked(is_checked)
                        cb.blockSignals(False)

        self._update_all_counts()
        self._on_checkbox_changed()

    def _toggle_month(self, month_key, state):
        is_checked = state == Qt.CheckState.Checked
        for cb, mk in self._date_checkboxes:
            if mk == month_key:
                cb.blockSignals(True)
                cb.setChecked(is_checked)
                cb.blockSignals(False)

        self._update_count(month_key)
        self._on_checkbox_changed()

    def _on_date_changed(self, month_key):
        self._update_count(month_key)
        self._on_checkbox_changed()

    def _update_count(self, month_key):
        selected = sum(1 for cb, mk in self._date_checkboxes if mk == month_key and cb.isChecked())
        total = sum(1 for cb, mk in self._date_checkboxes if mk == month_key)
        if month_key in self._month_headers:
            self._month_headers[month_key].setText(f"({selected}/{total})")

    def _update_all_counts(self):
        for month_key in self._month_headers.keys():
            self._update_count(month_key)

    def _select_all(self):
        self._updating = True
        for cb, _ in self._date_checkboxes:
            cb.setChecked(True)
        for month_cb in self._month_checkboxes.values():
            month_cb.blockSignals(True)
            month_cb.setChecked(True)
            month_cb.blockSignals(False)
        for year_cb in self._year_checkboxes.values():
            year_cb.blockSignals(True)
            year_cb.setChecked(True)
            year_cb.blockSignals(False)
        self._updating = False
        self._update_all_counts()
        self._on_checkbox_changed()

    def _deselect_all(self):
        self._updating = True
        for cb, _ in self._date_checkboxes:
            cb.setChecked(False)
        for month_cb in self._month_checkboxes.values():
            month_cb.blockSignals(True)
            month_cb.setChecked(False)
            month_cb.blockSignals(False)
        for year_cb in self._year_checkboxes.values():
            year_cb.blockSignals(True)
            year_cb.setChecked(False)
            year_cb.blockSignals(False)
        self._updating = False
        self._update_all_counts()
        self._on_checkbox_changed()

    def _on_checkbox_changed(self):
        if self._updating:
            return
        selected = [cb.text() for cb, _ in self._date_checkboxes if cb.isChecked()]
        self.filter_changed.emit(selected)

    def _on_cancel(self):
        if self._initial_active_dates is not None:
            self.filter_changed.emit(self._initial_active_dates)
        else:
            all_dates = [cb.text() for cb, _ in self._date_checkboxes]
            self.filter_changed.emit(all_dates)
        self.reject()
