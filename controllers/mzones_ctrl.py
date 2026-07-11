# -*- coding: utf-8 -*-
"""Management Zones controller (functional fork of precision_zones).

One facade (``MZonesCtrl``) owning the shared ``PZSession`` plus the six
step controllers ported from precision_zones. Signal wiring happens in
``farm_tools.py``; widgets live on the dialog as ``mz_*`` attributes
(published by ``view/mzones.py``).

Light steps run synchronously on the UI thread wrapped in a wait cursor;
the resampling/extraction and elbow + silhouette steps run on worker
threads (``workers/mzones_worker.py``) with progress on their buttons.
"""
import os
import shutil
from contextlib import contextmanager

import numpy as np
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication, QFileDialog
from qgis.core import QgsProject, QgsRasterLayer

from .. import extlibs_manager
from ..managers.settings_manager import SettingsManager
from ..renderers.raster_renderer_utils import RasterRendererUtils
from ..services.mzones import (
    clustering_service,
    export_service,
    filter_service,
    pca_service,
    variance_service,
    zones_service,
)
from ..services.mzones.deps import (
    DependencyMissing,
    check_imports,
    import_pandas,
    try_pandas,
)
from ..services.mzones.export_service import NoPointsInZones
from ..services.mzones.i18n import tr
from ..services.mzones.notify import Notifier
from ..services.mzones.raster_io import read_ref_metadata_from_layer
from ..services.mzones.session import PZSession
from ..services.mzones.variance_service import NoZonesData
from ..workers.mzones_worker import ElbowWorker, ResampleWorker


@contextmanager
def _wait_cursor():
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


def _stem_filename(title: str) -> str:
    return title.replace("/", "-").replace(":", "-")


def _export_folder(dialog, notifier):
    """Global download folder from the Welcome page, or None (with warning)."""
    pasta = (SettingsManager.load_download_folder() or "").strip()
    if not pasta or not os.path.isdir(pasta):
        notifier.warning(dialog, tr("Error"),
                         tr("No download folder set. Choose one on the Welcome page."))
        return None
    return pasta


def _nome_base_zonas(k: int, fonte_tag: str, pcs) -> str:
    if fonte_tag == "PCA":
        pcs_txt = f", PCs={pcs}" if pcs else ""
        return tr("Zones (k={}, PCA{})").format(k, pcs_txt)
    return tr("Zones (k={}, Orig)").format(k)


def _elbow_base_name(tag, kminmax, pcs) -> str:
    kmin, kmax = kminmax if kminmax else (None, None)
    if tag == "PCA" and pcs is not None:
        return tr("Indices (Elbow+Silhouette) – PCA (PCs={}, k={}-{})").format(pcs, kmin, kmax)
    return tr("Indices (Elbow+Silhouette) – Original variables (z-score), k={}-{}").format(kmin, kmax)


class DepsController:
    """Intro-tab dependency panel: live status + install/recheck."""

    def __init__(self, dialog, notifier):
        self.dialog = dialog
        self.notifier = notifier

    def refresh(self):
        extlibs_manager.ensure_on_path()
        self.dialog.mz_set_dep_status(check_imports())

    def install(self):
        self.dialog.mz_set_deps_installing(True)
        self._dl = extlibs_manager.start_download()
        self._dl.download_done.connect(self._on_done)

    def _on_done(self, ok: bool, msg: str):
        self.dialog.mz_set_deps_installing(False)
        if ok:
            extlibs_manager.ensure_on_path()
            self.refresh()
            self.notifier.info(self.dialog, tr("Done"),
                               tr("Dependencies installed."))
        else:
            self.notifier.warning(self.dialog, tr("Missing dependency"),
                                  msg or tr("Could not install dependencies."))


class ResampleController:
    """Data tab: read inputs, run resampling_service on a worker, store state."""

    def __init__(self, iface, dialog, session, notifier):
        self.iface = iface
        self.dialog = dialog
        self.session = session
        self.notifier = notifier
        self._worker = None
        self._btn_text = None

    def run(self):
        dlg = self.dialog
        ses = self.session
        if self._worker is not None and self._worker.isRunning():
            # Second click while running = cancel request.
            self._worker.cancel()
            dlg.mz_btn_resample.setEnabled(False)
            dlg.mz_btn_resample.setText(tr("Cancelling…"))
            return

        contorno_layer = dlg.mz_vector_combo.currentLayer()
        if contorno_layer is None:
            self.notifier.warning(dlg, tr("Error"),
                                  tr("Select a boundary vector layer."))
            return
        # A geographic boundary is auto-reprojected to its UTM CRS by the
        # resampling service.

        rasters = []
        for layer_id in dlg.mz_checked_raster_ids():
            layer = QgsProject.instance().mapLayer(layer_id)
            if isinstance(layer, QgsRasterLayer) and layer.isValid():
                rasters.append(layer)
        if not rasters:
            self.notifier.warning(dlg, tr("Error"),
                                  tr("Check at least one raster."))
            return

        res_txt = dlg.mz_resolution_input.text().strip()
        try:
            resolucao = float(res_txt)
            if resolucao <= 0:
                raise ValueError
        except Exception:
            self.notifier.warning(dlg, tr("Error"),
                                  tr("Provide resolution as a number (e.g., 2 or 2.5)."))
            return
        ses.res_alvo = resolucao

        self._btn_text = dlg.mz_btn_resample.text()
        dlg.mz_btn_resample.setText(tr("Cancel"))

        self._worker = ResampleWorker(contorno_layer, rasters, resolucao)
        self._worker.status.connect(self.notifier.status)
        self._worker.finished.connect(self._on_done)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.dep_missing.connect(self._on_dep_missing)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def stop_worker(self):
        """Cancel and join a running resample worker (plugin unload)."""
        worker = self._worker
        if worker is None:
            return
        try:
            worker.status.disconnect()
            worker.finished.disconnect()
            worker.cancelled.disconnect()
            worker.dep_missing.disconnect()
            worker.failed.disconnect()
        except Exception:
            pass
        if worker.isRunning():
            worker.cancel()
            worker.wait()
        self._worker = None

    def _reset_btn(self):
        btn = self.dialog.mz_btn_resample
        if self._btn_text:
            btn.setText(self._btn_text)
        btn.setEnabled(True)

    def _on_cancelled(self):
        self._reset_btn()
        self.notifier.status(tr("Resampling"), tr("Cancelled by user."), 1)

    def _on_dep_missing(self, msg):
        self._reset_btn()
        self.notifier.warning(self.dialog, tr("Missing dependency"), msg)

    def _on_failed(self, msg):
        self._reset_btn()
        self.notifier.critical(self.dialog, tr("Error"),
                               tr("Failed to generate/extract values: {}").format(msg))

    def _on_done(self, result):
        self._reset_btn()
        dlg = self.dialog
        ses = self.session

        # status messages for cleaning
        if result.n_removed > 0:
            self.notifier.status(tr("Data cleaning"),
                                 tr("Removed {} rows with missing/NoData.").format(result.n_removed))
        if result.zero_var_cols:
            self.notifier.status(tr("Data cleaning"),
                                 tr("Removed zero-variance columns: {}.").format(', '.join(result.zero_var_cols)))

        # reference grid metadata always stored
        ses.ref_gt = result.ref_gt
        ses.ref_crs_wkt = result.ref_crs_wkt
        ses.ref_crs_authid = result.target_crs_authid
        ses.grid_shape = result.grid_shape
        ses.referencia_raster = result.referencia_raster

        if result.df is None or result.df.empty:
            self.notifier.warning(dlg, tr("No valid data"),
                                  tr("After cleaning, no valid rows remained for analysis."))
            return

        ses.dados_amostrados = result.df
        ses.matriz_variaveis_originais = result.matriz_variaveis_originais
        ses.colunas_variaveis_originais = result.colunas_variaveis_originais

        # UTM auto-reprojection (result.reprojected) is deliberately not
        # surfaced — it is seamless from the user's point of view.
        msg = tr("Data resampled, extracted and stored in memory (with cleaning) successfully!")
        self.notifier.info(dlg, tr("Step completed"), msg)


class PCAController:
    """PCA tab: run PCA, export report/folder, export PC rasters."""

    def __init__(self, iface, dialog, session, notifier):
        self.iface = iface
        self.dialog = dialog
        self.session = session
        self.notifier = notifier

    # ---------------------------------------------------------------- PCA
    def run_pca(self):
        dlg = self.dialog
        ses = self.session
        try:
            with _wait_cursor():
                result = pca_service.run_pca(ses.dados_amostrados)
        except DependencyMissing as e:
            self.notifier.warning(dlg, tr("Missing dependency"),
                                  e.user_message())
            return
        except ValueError as e:
            self.notifier.warning(dlg, tr("Error"), str(e))
            return
        except Exception as e:
            self.notifier.critical(dlg, tr("PCA error"), str(e))
            return

        ses.pca_transformada = result.scores
        ses.pca_scores = result.scores
        ses.relatorio_pca = result.relatorio_pca
        ses.variancia_explicada = result.variancia_explicada

        dlg.mz_pca_table.setRowCount(len(result.variance_pct))
        dlg.mz_pca_table.setColumnCount(4)
        dlg.mz_pca_table.setHorizontalHeaderLabels([
            tr("Component"),
            tr("Eigenvalue (λ)"),
            tr("Variance (%)"),
            tr("Cumulative (%)")
        ])
        for i, (lam, v, a) in enumerate(zip(result.eigenvalues, result.variance_pct,
                                            result.cumulative_pct)):
            dlg.mz_pca_table.setItem(i, 0, QtWidgets.QTableWidgetItem(f"PC{i+1}"))
            dlg.mz_pca_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{lam:.6f}"))
            dlg.mz_pca_table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{v:.2f}"))
            dlg.mz_pca_table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{a:.2f}"))

        try:
            from qgis.PyQt.QtWidgets import QHeaderView
            hdr = dlg.mz_pca_table.horizontalHeader()
            hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            hdr.setStretchLastSection(True)
        except Exception:
            pass

        dlg.mz_populate_pc_combos(len(result.variance_pct))

        self.notifier.info(dlg, tr("PCA finished"),
                           tr("PCA analysis finished successfully."))

    # ---------------------------------------------------------------- export
    def export_report(self):
        dlg = self.dialog
        ses = self.session
        if ses.relatorio_pca is None or ses.variancia_explicada is None:
            self.notifier.warning(dlg, tr("Error"),
                                  tr("Run PCA before exporting the report."))
            return
        pasta = _export_folder(dlg, self.notifier)
        if not pasta:
            return
        try:
            export_service.save_pca_report(ses.relatorio_pca, ses.variancia_explicada, pasta)
            self.notifier.info(dlg, tr("Exported"),
                               tr("Files saved to:\n{}").format(pasta))
        except Exception as e:
            self.notifier.critical(dlg, tr("Error"), str(e))

    # -------------------------------------------------- PC raster exports
    def _ensure_ref_metadata(self) -> bool:
        ses = self.session
        dlg = self.dialog
        if ses.has_ref_metadata():
            return True
        # infer from the first selected raster (or the filter/analysis combo)
        try:
            ref_layer = None
            checked = dlg.mz_checked_raster_ids()
            if checked:
                ref_layer = QgsProject.instance().mapLayer(checked[0])
            if ref_layer is None:
                ref_layer = (dlg.mz_filter_raster_combo.currentLayer()
                             or dlg.mz_analysis_raster_combo.currentLayer())
            if ref_layer is None or not isinstance(ref_layer, QgsRasterLayer) or not ref_layer.isValid():
                return False
            meta = read_ref_metadata_from_layer(ref_layer)
            if meta is None:
                return False
            ses.ref_gt, ses.ref_crs_wkt, ses.grid_shape = meta
            return True
        except Exception:
            return False

    def export_selected_pc(self):
        dlg = self.dialog
        ses = self.session
        try:
            if not self._ensure_ref_metadata():
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Reference raster metadata missing. "
                                         "Select a raster in the Data tab (or run that step)."))
                return

            scores, ncomp = ses.resolve_pca_scores()
            if scores is None or ncomp == 0:
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Run PCA in the plugin before exporting."))
                return
            # autofill combo if needed
            if dlg.mz_pc_export_combo.count() == 0:
                dlg.mz_populate_pc_combos(ncomp)

            pc_idx = dlg.mz_pc_export_combo.currentData()
            if pc_idx is None:
                txt = dlg.mz_pc_export_combo.currentText().strip().upper()
                if txt.startswith("PC"):
                    try:
                        pc_idx = int(txt.replace("PC", "")) - 1
                    except Exception:
                        pc_idx = None
            if pc_idx is None or pc_idx < 0:
                self.notifier.warning(dlg, tr("Warning"),
                                      tr("No PC selected."))
                return
            if pc_idx >= ncomp:
                self.notifier.warning(dlg, tr("Warning"),
                                      tr("Invalid PC index."))
                return

            df = ses.dados_amostrados
            if df is None or df.empty or not all(k in df.columns for k in ("X", "Y")):
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Points (X,Y) not found. Run resampling in the plugin."))
                return

            sugestao = f"PC{pc_idx+1}.tif"
            out_path, _ = QFileDialog.getSaveFileName(
                dlg, tr("Save PC GeoTIFF"), sugestao,
                tr("GeoTIFF (*.tif)"))
            if not out_path:
                return
            if not out_path.lower().endswith(".tif"):
                out_path += ".tif"

            export_service.export_pc_raster(scores, pc_idx, df, ses.ref_gt,
                                            ses.ref_crs_wkt, ses.grid_shape, out_path)
            self.notifier.info(dlg, tr("Done"),
                               tr("PC raster exported successfully."))
        except Exception as e:
            self.notifier.critical(dlg, tr("Export error"), str(e))

    def export_all_pcs(self):
        dlg = self.dialog
        ses = self.session
        try:
            if not self._ensure_ref_metadata():
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Reference raster metadata missing. "
                                         "Select a raster in the Data tab (or run that step)."))
                return

            scores, ncomp = ses.resolve_pca_scores()
            if scores is None or ncomp == 0:
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Run PCA in the plugin before exporting."))
                return

            df = ses.dados_amostrados
            if df is None or df.empty or not all(k in df.columns for k in ("X", "Y")):
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Points (X,Y) not found. Run resampling in the plugin."))
                return

            out_path, _ = QFileDialog.getSaveFileName(
                dlg, tr("Save PCs (multiband)"), "PCs.tif",
                tr("GeoTIFF (*.tif)"))
            if not out_path:
                return
            if not out_path.lower().endswith(".tif"):
                out_path += ".tif"

            export_service.export_all_pcs_multiband(scores, df, ses.ref_gt,
                                                    ses.ref_crs_wkt, ses.grid_shape, out_path)
            self.notifier.info(dlg, tr("Done"),
                               tr("Multiband PCs GeoTIFF exported successfully."))
        except Exception as e:
            self.notifier.critical(dlg, tr("Export error"), str(e))


class ZonesController:
    """Zones tab: elbow/silhouette analysis, PNG/CSV export, zone raster.

    The elbow run happens on an ``ElbowWorker`` thread; table/plot updates
    land back on the UI thread via signals."""

    def __init__(self, iface, dialog, session, notifier):
        self.iface = iface
        self.dialog = dialog
        self.session = session
        self.notifier = notifier
        self._worker = None
        self._fonte_str = None
        self._btn_text = None

    # ------------------------------------------------ elbow + silhouette
    def run_elbow(self):
        dlg = self.dialog
        ses = self.session
        if self._worker is not None and self._worker.isRunning():
            # Second click while running = cancel request.
            self._worker.cancel()
            dlg.mz_btn_run_elbow.setEnabled(False)
            dlg.mz_btn_run_elbow.setText(tr("Cancelling…"))
            return
        try:
            use_pca = dlg.mz_rad_pca.isChecked()

            if use_pca:
                if ses.pca_transformada is None:
                    self.notifier.warning(dlg, tr("Error"),
                                          tr("Run PCA first or select 'Original variables'."))
                    return
                pcs = int(dlg.mz_pc_selector.currentText())
                dados = ses.pca_transformada[:, :pcs]
                fonte_str = tr("PCA (PCs={})").format(pcs)
                ses._ultima_pcs = pcs
                ses._ultima_fonte_tag = "PCA"
            else:
                if ses.matriz_variaveis_originais is None:
                    self.notifier.warning(dlg, tr("Error"),
                                          tr("Run the resampling/extraction step first."))
                    return
                dados = clustering_service.standardize(ses.matriz_variaveis_originais)
                fonte_str = tr("Original variables (z-score)")
                ses._ultima_pcs = None
                ses._ultima_fonte_tag = "Orig"

            k_min = dlg.mz_kmin_spin.value()
            k_max = dlg.mz_kmax_spin.value()
            ses._ultimo_kminmax = (k_min, k_max)
        except DependencyMissing as e:
            self.notifier.warning(dlg, tr("Missing dependency"),
                                  e.user_message())
            return
        except Exception as e:
            self.notifier.critical(dlg, tr("Zones analysis error"), str(e))
            return

        self._fonte_str = fonte_str
        self._btn_text = dlg.mz_btn_run_elbow.text()
        dlg.mz_btn_run_elbow.setText(tr("Cancel"))

        self._worker = ElbowWorker(dados, k_min, k_max)
        self._worker.progress.connect(self._on_elbow_progress)
        self._worker.finished.connect(self._on_elbow_done)
        self._worker.cancelled.connect(self._on_elbow_cancelled)
        self._worker.dep_missing.connect(self._on_elbow_dep_missing)
        self._worker.failed.connect(self._on_elbow_failed)
        self._worker.start()

    def stop_worker(self):
        """Interrupt and join a running elbow worker (plugin unload)."""
        worker = self._worker
        if worker is None:
            return
        try:
            worker.progress.disconnect()
            worker.finished.disconnect()
            worker.cancelled.disconnect()
            worker.dep_missing.disconnect()
            worker.failed.disconnect()
        except Exception:
            pass
        if worker.isRunning():
            worker.cancel()
            worker.wait()
        self._worker = None

    def _on_elbow_progress(self, done, total):
        if self._worker is not None and self._worker.isInterruptionRequested():
            return  # keep the "Cancelling…" label
        self.dialog.mz_btn_run_elbow.setText(
            tr("Cancel ({}/{})").format(done, total))

    def _reset_elbow_btn(self):
        btn = self.dialog.mz_btn_run_elbow
        if self._btn_text:
            btn.setText(self._btn_text)
        btn.setEnabled(True)

    def _on_elbow_cancelled(self):
        self._reset_elbow_btn()
        self.notifier.status(tr("Zones analysis"), tr("Cancelled by user."), 1)

    def _on_elbow_dep_missing(self, msg):
        self._reset_elbow_btn()
        self.notifier.warning(self.dialog, tr("Missing dependency"), msg)

    def _on_elbow_failed(self, msg):
        self._reset_elbow_btn()
        self.notifier.critical(self.dialog, tr("Zones analysis error"), msg)

    def _on_elbow_done(self, elbow):
        self._reset_elbow_btn()
        dlg = self.dialog
        ses = self.session
        fonte_str = self._fonte_str or ""
        try:
            pd = import_pandas()

            ks, inercia, silhuetas = elbow.ks, elbow.inertia, elbow.silhouettes

            dlg.mz_indices_table.setRowCount(len(ks))
            dlg.mz_indices_table.setColumnCount(3)
            dlg.mz_indices_table.setHorizontalHeaderLabels([
                tr("k"), tr("Inertia"), tr("Silhouette")])
            for i, (k, iner, sil) in enumerate(zip(ks, inercia, silhuetas)):
                dlg.mz_indices_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(k)))
                dlg.mz_indices_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{iner:.2f}"))
                dlg.mz_indices_table.setItem(i, 2, QtWidgets.QTableWidgetItem(
                    "" if np.isnan(sil) else f"{sil:.4f}"))

            try:
                from qgis.PyQt.QtWidgets import QHeaderView
                hdr = dlg.mz_indices_table.horizontalHeader()
                hdr.setStretchLastSection(True)
                hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
                hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            except Exception:
                pass

            ses.tabela_elbow = pd.DataFrame({
                "Clusters": ks,
                "Inércia": inercia,
                tr("Silhouette"): silhuetas
            })

            ax = dlg.mz_elbow_axes
            ax.clear()
            old_twin = getattr(dlg, "_mz_elbow_twin_ax", None)
            if old_twin is not None:
                try:
                    old_twin.remove()
                except Exception:
                    pass
                dlg._mz_elbow_twin_ax = None

            l1, = ax.plot(ks, inercia, marker='o', label=tr("Inertia"))
            ax.set_xlabel(tr("Number of clusters (k)"))
            ax.set_ylabel(tr("Inertia"))
            ax.set_title(tr("Elbow + Silhouette – {}").format(fonte_str))

            twin = ax.twinx()
            dlg._mz_elbow_twin_ax = twin
            twin.grid(False)
            l2, = twin.plot(ks, silhuetas, marker='s', linestyle='--', color='red',
                            label=tr("Silhouette"))
            twin.set_ylabel(tr("Silhouette (−1 to 1)"))
            ax.legend([l1, l2], [l1.get_label(), l2.get_label()], loc='best')
            dlg.mz_elbow_canvas.draw()

            self.notifier.info(dlg, tr("Analysis completed"),
                               tr("Elbow + Silhouette analysis finished successfully."))
        except DependencyMissing as e:
            self.notifier.warning(dlg, tr("Missing dependency"),
                                  e.user_message())
        except Exception as e:
            self.notifier.critical(dlg, tr("Zones analysis error"), str(e))

    # --------------------------------------------------------- exports
    def export_elbow_png(self):
        dlg = self.dialog
        ses = self.session
        if ses.tabela_elbow is None:
            self.notifier.warning(dlg, tr("Error"),
                                  tr("Run zones analysis before exporting."))
            return
        base = _elbow_base_name(ses._ultima_fonte_tag or "Orig", ses._ultimo_kminmax, ses._ultima_pcs)
        sugestao = _stem_filename(base + ".png")
        caminho, _ = QFileDialog.getSaveFileName(
            dlg, tr("Save plot (PNG)"), sugestao,
            tr("PNG (*.png)"))
        if not caminho:
            return
        if not caminho.lower().endswith(".png"):
            caminho += ".png"
        try:
            dlg.mz_elbow_canvas.figure.savefig(caminho, dpi=300, bbox_inches="tight")
            self.notifier.info(dlg, tr("Export completed"),
                               tr("Plot saved to:\n{}").format(caminho))
        except Exception as e:
            self.notifier.critical(dlg, tr("Export error"), str(e))

    def export_elbow_csv(self):
        dlg = self.dialog
        ses = self.session
        if try_pandas() is None:
            self.notifier.warning(dlg, tr("Missing dependency"),
                                  tr("This feature requires 'pandas'."))
            return
        if ses.tabela_elbow is None:
            self.notifier.warning(dlg, tr("Error"),
                                  tr("Run zones analysis before exporting."))
            return
        base = _elbow_base_name(ses._ultima_fonte_tag or "Orig", ses._ultimo_kminmax, ses._ultima_pcs)
        sugestao = _stem_filename(base + ".csv")
        caminho, _ = QFileDialog.getSaveFileName(
            dlg, tr("Save results (CSV)"), sugestao,
            tr("CSV (*.csv)"))
        if not caminho:
            return
        if not caminho.lower().endswith(".csv"):
            caminho += ".csv"
        try:
            ses.tabela_elbow.to_csv(caminho, index=False, encoding="utf-8-sig")
            self.notifier.info(dlg, tr("Export completed"),
                               tr("Results saved to:\n{}").format(caminho))
        except Exception as e:
            self.notifier.critical(dlg, tr("Export error"), str(e))

    # ----------------------------------------------- generate zone raster
    def generate_zones(self):
        dlg = self.dialog
        ses = self.session
        try:
            use_pca = dlg.mz_rad_pca.isChecked()

            if use_pca and ses.pca_transformada is None:
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Run PCA before generating zones (or select 'Original variables')."))
                return
            if (not use_pca) and ses.matriz_variaveis_originais is None:
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Run the resampling/extraction step first."))
                return

            n_zonas = dlg.mz_final_k_spin.value()

            if use_pca:
                pcs = dlg.mz_pc_selector.currentIndex() + 1
                dados = ses.pca_transformada[:, :pcs]
                modo_tag = "PCA"
            else:
                dados = clustering_service.standardize(ses.matriz_variaveis_originais)
                modo_tag = "Orig"
                pcs = None

            contorno_layer = dlg.mz_vector_combo.currentLayer()
            if contorno_layer is None:
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Select a valid boundary layer."))
                return
            # Points (X,Y) live on the resampling grid, which may be an
            # auto-estimated UTM CRS — use that, not the raw boundary CRS.
            crs_authid = ses.ref_crs_authid or contorno_layer.crs().authid()

            if ses.ref_gt is None or ses.grid_shape is None:
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Reference grid not available. Run the resampling step."))
                return

            pasta_exportacao = _export_folder(dlg, self.notifier)
            if not pasta_exportacao:
                return

            apply_filter = dlg.mz_zones_filter_check.isChecked()
            raio = int(dlg.mz_zones_filter_radius.value())

            with _wait_cursor():
                zonas = clustering_service.final_kmeans(dados, n_zonas)

                df = ses.dados_amostrados.copy()
                df["Zona"] = zonas + 1

                layer_title = _nome_base_zonas(n_zonas, modo_tag, pcs if use_pca else None)
                suffix = "_filtered" if apply_filter else ""
                out_basename = f"zonas_manejo_k{n_zonas}_{modo_tag}{suffix}.tif"
                out_path = os.path.join(pasta_exportacao, out_basename)

                zones_service.rasterize_zones(df, crs_authid, ses.ref_gt, ses.grid_shape, out_path)

                if apply_filter:
                    # Same smoothing as the Filter tab, baked into the saved file.
                    result = filter_service.apply_majority_filter(
                        out_path, crs_authid, raio)
                    shutil.copyfile(result.out_path, out_path)
                    layer_title = tr("{} – majority (r={})").format(layer_title, raio)

            layer_raster = RasterRendererUtils.load_pseudocolor_raster(
                out_path, layer_title, 1, dlg.mz_zones_ramp_combo.currentText())
            if layer_raster is None:
                raise Exception(tr("Failed to load generated raster."))
            dlg.mz_refresh_rasters()

            self.notifier.info(dlg, tr("Zones generated"),
                               tr("Zones were generated and saved to:\n{}").format(out_path))
        except DependencyMissing as e:
            self.notifier.warning(dlg, tr("Missing dependency"),
                                  e.user_message())
        except Exception as e:
            self.notifier.critical(dlg, tr("Error generating zones"), str(e))


class FilterController:
    """Filter tab: majority filter on a zones raster."""

    def __init__(self, iface, dialog, session, notifier):
        self.iface = iface
        self.dialog = dialog
        self.session = session
        self.notifier = notifier

    def apply(self):
        dlg = self.dialog
        try:
            raster = dlg.mz_filter_raster_combo.currentLayer()
            if not raster or not raster.isValid():
                raise Exception(tr("Raster not found."))
            src_path = raster.dataProvider().dataSourceUri().split("|")[0]

            raio = int(dlg.mz_window_spin.value())
            threshold = 0.0

            with _wait_cursor():
                result = filter_service.apply_majority_filter(
                    src_path, raster.crs().authid(), raio, threshold)

            layer_name = tr("{} – majority (r={})").format(raster.name(), result.raio)
            out_layer = RasterRendererUtils.load_pseudocolor_raster(
                result.out_path, layer_name, 1,
                dlg.mz_filter_ramp_combo.currentText())
            if out_layer is None:
                raise Exception(tr("Invalid/unreadable output."))

            try:
                if result.nodata is not None:
                    out_layer.dataProvider().setNoDataValue(1, float(result.nodata))
                out_layer.triggerRepaint()
            except Exception:
                pass

            dlg.mz_refresh_rasters()

            self.notifier.info(
                dlg, tr("Majority filter"),
                tr("Filter applied.\nLayer created: {}").format(layer_name))
        except Exception as e:
            self.notifier.critical(
                dlg, tr("Error applying majority filter"),
                str(e))


class AnalysisController:
    """Analysis tab: load CSV, variance reduction, boxplots."""

    def __init__(self, iface, dialog, session, notifier):
        self.iface = iface
        self.dialog = dialog
        self.session = session
        self.notifier = notifier

    # ------------------------------------------------------------ CSV
    def load_csv(self):
        dlg = self.dialog
        pd = try_pandas()
        if pd is None:
            self.notifier.warning(
                dlg, tr("Missing dependency"),
                tr("Reading CSV requires 'pandas'."))
            return
        try:
            caminho, _ = QFileDialog.getOpenFileName(
                dlg, tr("Select CSV"), "",
                tr("CSV files (*.csv)"))
            if not caminho:
                return

            df = pd.read_csv(caminho, sep=None, engine='python', decimal=',')
            colunas = df.columns.tolist()

            dlg.mz_col_x_combo.clear()
            dlg.mz_col_y_combo.clear()
            dlg.mz_col_attr_combo.clear()
            dlg.mz_col_x_combo.addItems(colunas)
            dlg.mz_col_y_combo.addItems(colunas)
            dlg.mz_col_attr_combo.addItems(colunas)

            self.session.dados_amostrados = df
            self.notifier.info(dlg, tr("Success"),
                               tr("CSV loaded successfully."))
        except Exception as e:
            self.notifier.critical(dlg, tr("Error"),
                                   tr("Failed to read CSV:\n{}").format(e))

    # ------------------------------------------------ variance reduction
    def _zones_raster_path(self):
        layer = self.dialog.mz_analysis_raster_combo.currentLayer()
        if layer is None:
            return None
        return layer.dataProvider().dataSourceUri().split("|")[0]

    def variance_reduction(self):
        dlg = self.dialog
        ses = self.session
        try:
            raster_path = self._zones_raster_path()
            if raster_path is None:
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Zones raster not found."))
                return

            if ses.dados_amostrados is None:
                self.notifier.warning(dlg, tr("Error"),
                                      tr("No points CSV loaded."))
                return

            col_x = dlg.mz_col_x_combo.currentText()
            col_y = dlg.mz_col_y_combo.currentText()
            col_attr = dlg.mz_col_attr_combo.currentText()
            if not col_x or not col_y or not col_attr:
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Select X, Y and attribute columns."))
                return

            with _wait_cursor():
                result = variance_service.variance_reduction(
                    ses.dados_amostrados, col_x, col_y, col_attr, raster_path)
        except NoZonesData as e:
            self.notifier.warning(dlg, tr("Error"), str(e))
            return
        except DependencyMissing as e:
            self.notifier.warning(dlg, tr("Missing dependency"),
                                  e.user_message())
            return
        except ValueError as e:
            self.notifier.warning(dlg, tr("Error"), str(e))
            return
        except Exception as e:
            self.notifier.critical(dlg, tr("Error"),
                                   tr("Variance Reduction failed:\n{}").format(e))
            return

        if result.dropped:
            self.notifier.status(tr("Analysis"),
                                 tr("Ignored {} points outside the zones raster.").format(result.dropped))

        colZona = tr("Zone")
        colMedia = tr("Mean")
        colVar = tr("Variance")
        colArea = tr("Area (ha)")

        dlg.mz_result_table.setRowCount(len(result.ui_rows))
        dlg.mz_result_table.setColumnCount(5)
        dlg.mz_result_table.setHorizontalHeaderLabels([colZona, colMedia, colVar, "n", colArea])
        for i, (z, media, var, n, area_ha) in enumerate(result.ui_rows):
            dlg.mz_result_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(int(z))))
            dlg.mz_result_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{media:.2f}"))
            dlg.mz_result_table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{var:.2f}"))
            dlg.mz_result_table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(int(n))))
            dlg.mz_result_table.setItem(i, 4, QtWidgets.QTableWidgetItem(f"{area_ha:.2f}"))

        vr = result.vr_percent
        dlg.mz_vr_lbl.setText(tr("VR: {}%").format(vr))

        salvar, _ = QFileDialog.getSaveFileName(
            dlg, tr("Save CSV (per-zone statistics)"), "",
            tr("CSV Files (*.csv)"))
        if salvar:
            try:
                pd = import_pandas()
                export_df = result.export_df
                extra = {c: "" for c in export_df.columns}
                extra[colZona] = tr("Total VR%")
                extra[colMedia] = f"{vr:.2f}"
                df_out = pd.concat([export_df, pd.DataFrame([extra])], ignore_index=True)
                df_out.to_csv(salvar, index=False)
                self.notifier.info(
                    dlg, tr("Success"),
                    tr("File saved successfully to:\n{}\n\n(Total VR = {}%)").format(salvar, vr))
            except Exception as e:
                self.notifier.critical(dlg, tr("Error"),
                                       tr("Variance Reduction failed:\n{}").format(e))

    # ------------------------------------------------------- boxplots
    def export_boxplots(self):
        dlg = self.dialog
        ses = self.session
        try:
            if ses.dados_amostrados is None:
                self.notifier.warning(dlg, tr("Error"),
                                      tr("No points CSV loaded."))
                return

            col_x = dlg.mz_col_x_combo.currentText()
            col_y = dlg.mz_col_y_combo.currentText()
            col_attr = dlg.mz_col_attr_combo.currentText()
            if not col_x or not col_y or not col_attr:
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Select X, Y and attribute columns."))
                return

            raster_path = self._zones_raster_path()
            if raster_path is None:
                self.notifier.warning(dlg, tr("Error"),
                                      tr("Zones raster not found."))
                return

            out_path, _ = QFileDialog.getSaveFileName(
                dlg, tr("Save boxplots"), "",
                tr("PNG (*.png)"))
            if not out_path:
                return
            if not out_path.lower().endswith(".png"):
                out_path += ".png"

            with _wait_cursor():
                export_service.build_boxplots(ses.dados_amostrados, col_x, col_y, col_attr,
                                              raster_path, out_path)
            self.notifier.info(dlg, tr("Success"),
                               tr("Boxplots saved to:\n{}").format(out_path))
        except (ValueError, NoPointsInZones) as e:
            self.notifier.warning(dlg, tr("Error"), str(e))
        except DependencyMissing as e:
            self.notifier.warning(dlg, tr("Missing dependency"),
                                  e.user_message())
        except Exception as e:
            self.notifier.critical(dlg, tr("Error"),
                                   tr("Failed to export boxplots:\n{}").format(e))


class MZonesCtrl:
    """Facade: owns the shared session and the six step controllers."""

    def __init__(self, dialog, interface=None):
        self.dialog = dialog
        self.interface = interface
        self.session = PZSession()
        self.notifier = Notifier(interface)

        self.deps = DepsController(dialog, self.notifier)
        self.resample = ResampleController(interface, dialog, self.session, self.notifier)
        self.pca = PCAController(interface, dialog, self.session, self.notifier)
        self.zones = ZonesController(interface, dialog, self.session, self.notifier)
        self.filter = FilterController(interface, dialog, self.session, self.notifier)
        self.analysis = AnalysisController(interface, dialog, self.session, self.notifier)

        # Keep the checkable raster list in sync with the project
        # (add/remove/rename).
        self._project = QgsProject.instance()
        self._project.layersAdded.connect(self._on_layers_added)
        self._project.layersRemoved.connect(self._on_layers_changed)
        self._watched_layers = []
        self._watch_renames(self._project.mapLayers().values())

        self.dialog.mz_refresh_rasters()
        self.deps.refresh()

    def _watch_renames(self, layers):
        for layer in layers:
            if isinstance(layer, QgsRasterLayer):
                layer.nameChanged.connect(self._on_layers_changed)
                self._watched_layers.append(layer)

    def _on_layers_added(self, layers):
        self._watch_renames(layers)
        self._on_layers_changed()

    def _on_layers_changed(self, *_args):
        try:
            self.dialog.mz_refresh_rasters()
        except Exception:
            pass

    def cleanup(self):
        for ctrl in (self.zones, self.resample):
            try:
                ctrl.stop_worker()
            except Exception:
                pass
        try:
            self._project.layersAdded.disconnect(self._on_layers_added)
            self._project.layersRemoved.disconnect(self._on_layers_changed)
        except Exception:
            pass
        for layer in self._watched_layers:
            try:
                layer.nameChanged.disconnect(self._on_layers_changed)
            except Exception:
                pass
        self._watched_layers = []
