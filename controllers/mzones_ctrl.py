# -*- coding: utf-8 -*-
"""Management Zones controller (functional fork of precision_zones).

One facade (``MZonesCtrl``) owning the shared ``PZSession`` plus the six
step controllers ported from precision_zones. Signal wiring happens in
``farm_tools.py``; widgets live on the dialog as ``mz_*`` attributes
(published by ``view/mzones.py``).

The pipeline runs synchronously on the UI thread (faithful to the source
plugin); long steps are wrapped in a wait cursor.
"""
import os
from contextlib import contextmanager

import numpy as np
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication, QFileDialog
from qgis.core import QgsProject, QgsRasterLayer

from .. import extlibs_manager
from ..services.mzones import (
    clustering_service,
    export_service,
    filter_service,
    pca_service,
    resampling_service,
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
from ..services.mzones.raster_io import (
    find_layer_by_name,
    read_ref_metadata_from_layer,
)
from ..services.mzones.session import PZSession
from ..services.mzones.variance_service import NoZonesData


@contextmanager
def _wait_cursor():
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


def _stem_filename(title: str) -> str:
    return title.replace("/", "-").replace(":", "-")


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
    """Data tab: read inputs, call resampling_service, store state."""

    def __init__(self, iface, dialog, session, notifier):
        self.iface = iface
        self.dialog = dialog
        self.session = session
        self.notifier = notifier

    def run(self):
        dlg = self.dialog
        ses = self.session

        contorno_layer = dlg.mz_vector_combo.currentLayer()
        if contorno_layer is None:
            self.notifier.warning(dlg, tr("Error"),
                                  tr("Select a boundary vector layer."))
            return
        # A geographic boundary is auto-reprojected to its UTM CRS by the
        # resampling service.

        itens = dlg.mz_raster_list.selectedItems()
        rasters = []
        for item in itens:
            layer = find_layer_by_name(item.text())
            if isinstance(layer, QgsRasterLayer) and layer.isValid():
                rasters.append(layer)
        if not rasters:
            self.notifier.warning(dlg, tr("Error"),
                                  tr("Select at least one raster."))
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

        def _progress(title, msg, level=0):
            self.notifier.status(title, msg, level)

        try:
            with _wait_cursor():
                result = resampling_service.resample_and_extract(
                    contorno_layer, rasters, resolucao, progress=_progress)
        except DependencyMissing as e:
            self.notifier.warning(dlg, tr("Missing dependency"),
                                  e.user_message())
            return
        except Exception as e:
            self.notifier.critical(dlg, tr("Error"),
                                   tr("Failed to generate/extract values: {}").format(str(e)))
            return

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
    def choose_export_folder(self):
        pasta = QFileDialog.getExistingDirectory(
            self.dialog, tr("Choose folder to save"))
        if pasta:
            self.session.pasta_exportacao = pasta
            self.dialog.mz_export_path_lbl.setText(pasta)

    def export_report(self):
        dlg = self.dialog
        ses = self.session
        if ses.relatorio_pca is None or ses.variancia_explicada is None:
            self.notifier.warning(dlg, tr("Error"),
                                  tr("Run PCA before exporting the report."))
            return
        pasta = ses.pasta_exportacao or QFileDialog.getExistingDirectory(
            dlg, tr("Choose folder to save"))
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
            sel = dlg.mz_raster_list.selectedItems()
            if sel:
                ref_layer = find_layer_by_name(sel[0].text())
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
    """Zones tab: elbow/silhouette analysis, PNG/CSV export, zone raster."""

    def __init__(self, iface, dialog, session, notifier):
        self.iface = iface
        self.dialog = dialog
        self.session = session
        self.notifier = notifier

    # ------------------------------------------------ elbow + silhouette
    def run_elbow(self):
        dlg = self.dialog
        ses = self.session
        try:
            pd = import_pandas()

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

            with _wait_cursor():
                elbow = clustering_service.elbow_silhouette(dados, k_min, k_max)
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

            if not ses.pasta_exportacao:
                pasta = QFileDialog.getExistingDirectory(
                    dlg, tr("Choose a folder to save zones"))
                if not pasta:
                    return
                ses.pasta_exportacao = pasta

            with _wait_cursor():
                zonas = clustering_service.final_kmeans(dados, n_zonas)

                df = ses.dados_amostrados.copy()
                df["Zona"] = zonas + 1

                layer_title = _nome_base_zonas(n_zonas, modo_tag, pcs if use_pca else None)
                out_basename = f"zonas_manejo_k{n_zonas}_{modo_tag}.tif"
                out_path = os.path.join(ses.pasta_exportacao, out_basename)

                zones_service.rasterize_zones(df, crs_authid, ses.ref_gt, ses.grid_shape, out_path)

            layer_raster = QgsRasterLayer(out_path, layer_title)
            if not layer_raster.isValid():
                raise Exception(tr("Failed to load generated raster."))

            QgsProject.instance().addMapLayer(layer_raster)
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
            out_layer = QgsRasterLayer(result.out_path, layer_name, "gdal")
            if not out_layer.isValid():
                raise Exception(tr("Invalid/unreadable output."))

            try:
                out_layer.setRenderer(raster.renderer().clone())
                if result.nodata is not None:
                    out_layer.dataProvider().setNoDataValue(1, float(result.nodata))
                out_layer.triggerRepaint()
            except Exception:
                pass

            QgsProject.instance().addMapLayer(out_layer)
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

        # Keep the multi-select raster list in sync with the project.
        self._project = QgsProject.instance()
        self._project.layersAdded.connect(self._on_layers_changed)
        self._project.layersRemoved.connect(self._on_layers_changed)

        self.dialog.mz_refresh_rasters()
        self.deps.refresh()

    def _on_layers_changed(self, *_args):
        try:
            self.dialog.mz_refresh_rasters()
        except Exception:
            pass

    def cleanup(self):
        try:
            self._project.layersAdded.disconnect(self._on_layers_changed)
            self._project.layersRemoved.disconnect(self._on_layers_changed)
        except Exception:
            pass
