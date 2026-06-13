# RAVI test suite

A QGIS plugin is hard to test because almost everything touches one of three
heavy, side-effecting dependencies: **Earth Engine** (`ee`, network + auth),
**QGIS/Qt** (`qgis.core`, `qgis.PyQt`, needs a running app), and the
**network** (`requests` → NASA POWER). The suite is built so the bulk of the
logic is testable *without* any of them, and the parts that genuinely need
QGIS are isolated and run under a real QGIS interpreter.

## Test pyramid

```
                 ┌─────────────────────────┐
                 │  smoke / integration     │  few   — plugin loads, dialog
                 │  (real QGIS, offscreen)  │          builds, classFactory ok
                 ├─────────────────────────┤
                 │  qgis tier               │  some  — real QgsSettings, AOI
                 │  @pytest.mark.qgis       │          geometry, layer convert
                 ├─────────────────────────┤
                 │  unit tier               │  many  — pure logic; ee + qgis
                 │  (headless, stubbed)     │          stubbed; requests mocked
                 └─────────────────────────┘
```

### Unit tier — `tests/unit/` (runs anywhere)
No QGIS required. `conftest.py` registers the plugin as the import package
`ravi_qgis_plugin` and, when `ee`/`qgis`/`shapely` are absent, installs
lightweight stubs so the modules import. Earth Engine *call composition* is
tested by passing a MagicMock image and asserting the call graph
(`tests/unit/test_indexes.py`); the network is mocked at `requests.get`
(`tests/unit/test_nasa_power_service.py`).

Covered today:
- `services/dem_registry.py` — bbox intersection math, catalog load, model.
- `tools/indexes.py` — every vegetation index's band selection / formula.
- `services/nasa_power_service.py` — URL build, -999→NaN, sort, proxy fallback,
  monthly roll-up.
- `services/aoi_service.py` — `_remove_z_dimension` (the pure half).

### QGIS tier — `tests/qgis/` (real QGIS Python)
Marked `@pytest.mark.qgis`; auto-skipped when `qgis.core` is not importable.
Exercises code against the real QGIS API with an isolated settings scope and
in-memory layers. Today: `SettingsManager` round-trip. Extend with:
- `AOIService` layer→EE/GeoJSON conversion using in-memory `QgsVectorLayer`
  (`"Polygon?crs=epsg:4326"`), including CRS reprojection + Z-drop.
- `DatasetManager` populating a `QComboBox` from a fake registry.

### Smoke / integration (real QGIS, offscreen)
`QT_QPA_PLATFORM=offscreen`. Assert `classFactory(iface)` returns a plugin,
`initGui()` registers the action, `RAVIDialog()` builds without raising. These
catch import/wiring regressions the layer tests miss.

## Layers still to cover (priority order)

1. **workers/** (`*_worker.py`) — QThread workers. Test the *run logic* by
   extracting the pure compute path or by driving the worker and capturing its
   signals with `QSignalSpy` (qgis tier). Mock the `ee`/service calls; assert
   `finished`/`error`/`progress` emissions and payload shape.
2. **controllers/** — orchestration. Inject mock services + a fake dialog;
   assert the right service calls happen on the right UI events. Mostly unit
   tier with stubs.
3. **services/** remaining (`optical`, `sar`, `landsat`, `sysi`, `dem`,
   `gee_service`) — same MagicMock-image call-composition style as indexes;
   for `gee_service` auth, mock `ee.Initialize`/`ee.Authenticate` and assert
   state transitions (no real credentials).
4. **view/** widgets — qgis tier, offscreen; build the widget, assert initial
   state and that signals fire on simulated input.
5. **renderers/** — pure-ish min/max/colormap math → unit tier.

## Running

Headless unit tier (any venv with `pytest`; the plugin `.venv` already has
`ee`/`pandas`/`numpy`):

```powershell
& "<plugin>\.venv\Scripts\python.exe" -m pytest tests/unit
```

Full suite (qgis tests skip if QGIS absent):

```powershell
& "<plugin>\.venv\Scripts\python.exe" -m pytest
```

QGIS tier under the real QGIS Python (Windows — sets the QGIS env first).
Just run `tests/run_qgis_tests.bat`: it auto-detects the install (QGIS 4 →
`python-qgis.bat`, QGIS 3 LTR → `python-qgis-ltr.bat`), preferring the newer
one. Override with `set QGIS_ROOT=...` before calling. First time, install the
deps into that interpreter:

```bat
REM QGIS 4 (Qt6)
call "C:\QGIS 4.0.3\bin\python-qgis.bat" -m pip install pytest pytest-mock
REM QGIS 3 LTR (Qt5)
call "C:\QGIS 3.44.10\bin\python-qgis-ltr.bat" -m pip install pytest pytest-mock
```

Markers: `qgis`, `ee`, `gui`, `net` (`net` is opt-in: `pytest -m net`).

## Coverage

```powershell
& "<plugin>\.venv\Scripts\python.exe" -m pytest tests/unit --cov=. --cov-report=term-missing
```

## CI sketch (GitHub Actions)

```yaml
jobs:
  unit:                       # fast, every push
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements_test.txt
      - run: pytest tests/unit --cov=. --cov-report=xml
  qgis:                       # nightly / on demand
    runs-on: ubuntu-latest
    container: qgis/qgis:release-3_44
    env: { QT_QPA_PLATFORM: offscreen }
    steps:
      - uses: actions/checkout@v4
      - run: pip install pytest pytest-mock
      - run: xvfb-run -a pytest -m qgis
```
