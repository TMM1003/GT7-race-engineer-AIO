# src/ui/track_map_3d.py
from __future__ import annotations

from typing import Optional, Tuple, List

from PySide6 import QtWidgets

from src.core.telemetry_session import TelemetrySession, LapData


class TrackMap3DWidget(QtWidgets.QWidget):
    """
    3D track visualization using pyqtgraph's OpenGL module.

    This 3D view is intended to model *track elevation*, not car vertical dynamics.
    Raw PositionY often includes suspension/compression noise; we compute an
    elevation proxy via distance-based smoothing + loop-closure correction.

    - Requires PyOpenGL (and often PyOpenGL_accelerate).
    - If OpenGL deps are missing, this widget degrades to a helpful message.
    """

    def __init__(self):
        super().__init__()

        self._gl = None
        self._have_gl = False

        self._ref_item = None
        self._last_item = None
        self._car_item = None
        self._grid_item = None

        # Shared normalization transform (so ref/last/car align)
        self._norm_center: Optional[Tuple[float, float, float]] = None
        self._norm_scale: float = 1.0

        # Elevation scaling is independent from X/Z footprint scaling.
        self._y_exaggeration: float = 8.0
        self._y_scale: float = 1.0

        # Elevation mode: "proxy" (smoothed, recommended) or "raw"
        self._elevation_mode: str = "proxy"

        # Smoothing parameters (in "track distance units" – typically meters-ish)
        self._elev_tau_m: float = 15.0   # low-pass distance constant; higher = smoother
        self._elev_outlier_clip_pct: float = 99.0  # robust clip raw Y before smoothing

        # Grade coloring (slope) for the "last" lap
        self._grade_coloring_enabled: bool = True

        # UI container so we can safely rebuild GL view after docking changes
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.view = None
        self._fallback_label = None

        # Build GL view (or fallback)
        self._init_gl_view()

    # ----------------------------
    # OpenGL lifecycle hardening
    # ----------------------------

    def _init_gl_view(self) -> None:
        """Create the GLViewWidget and grid (or fallback label). Safe to call multiple times."""
        # Remove existing view if present
        if self.view is not None:
            try:
                self._layout.removeWidget(self.view)
            except Exception:
                pass
            try:
                self.view.deleteLater()
            except Exception:
                pass
            self.view = None

        # Remove fallback label if present
        if self._fallback_label is not None:
            try:
                self._layout.removeWidget(self._fallback_label)
            except Exception:
                pass
            try:
                self._fallback_label.deleteLater()
            except Exception:
                pass
            self._fallback_label = None

        self._have_gl = False
        self._gl = None
        self._grid_item = None

        # Lazy import so the app doesn't crash if OpenGL isn't installed.
        try:
            import pyqtgraph.opengl as gl  # type: ignore

            self._gl = gl
            self.view = gl.GLViewWidget()
            self.view.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            self.view.setCameraPosition(distance=250)

            grid = gl.GLGridItem()
            grid.setSize(300, 300)
            grid.setSpacing(25, 25)
            self.view.addItem(grid)
            self._grid_item = grid

            self._layout.addWidget(self.view)
            self._have_gl = True

        except Exception as e:
            self.view = None
            self._fallback_label = QtWidgets.QLabel(
                "3D view unavailable (OpenGL deps missing).\n\n"
                "Install:\n"
                "  pip install PyOpenGL PyOpenGL_accelerate\n\n"
                f"Details: {type(e).__name__}: {e}"
            )
            self._fallback_label.setWordWrap(True)
            self._fallback_label.setMargin(12)
            self._layout.addWidget(self._fallback_label)

    def recover_gl_context(self) -> None:
        """
        Rebuild GLViewWidget after dock float/dock.
        Prevents shader/VBO crashes (GL_INVALID_VALUE) on some drivers (common on Windows).
        """
        if not self._have_gl:
            return

        # Remove GL items so we don't try to draw stale objects mid-transition.
        try:
            self.clear()
        except Exception:
            pass

        # Rebuild the GL view (fresh context)
        self._init_gl_view()

        # Force re-creation of plot items on next update
        self._ref_item = None
        self._last_item = None
        self._car_item = None

    # ----------------------------
    # Public API
    # ----------------------------

    def clear(self) -> None:
        if not self._have_gl:
            return
        for it in (self._ref_item, self._last_item, self._car_item):
            if it is not None:
                try:
                    self.view.removeItem(it)
                except Exception:
                    pass
        self._ref_item = None
        self._last_item = None
        self._car_item = None

    def update_from_session(self, session: TelemetrySession) -> None:
        """Draw reference vs last lap in 3D and the current car position."""
        if not self._have_gl:
            return
        if self.view is None:
            return

        ref = session.reference_lap()
        completed = session.completed_laps()
        last = completed[-1] if completed else None

        if ref is None and last is None:
            self.clear()
            return

        base_lap = ref or last
        if base_lap is not None:
            # Normalize using the same elevation mode we will render with
            self._compute_norm(base_lap, elevation_mode=self._elevation_mode)

        if ref is not None:
            self._upsert_line(ref, which="ref", elevation_mode=self._elevation_mode)
        if last is not None:
            self._upsert_line(last, which="last", elevation_mode=self._elevation_mode)

        # Car marker: keep it raw so it reflects what telemetry reports *now*.
        snap = session.latest_snapshot() or {}
        x = float(snap.get("position_x") or snap.get("x") or 0.0)
        y = float(snap.get("position_y") or snap.get("y") or 0.0)
        z = float(snap.get("position_z") or snap.get("z") or 0.0)
        if abs(x) > 1e-6 or abs(z) > 1e-6:
            self._upsert_car((x, y, z))

        self._autoframe(base_lap, elevation_mode=self._elevation_mode)

    # ---- internals ----

    def _lap_points_xyz_raw(self, lap: LapData) -> List[Tuple[float, float, float]]:
        pts: List[Tuple[float, float, float]] = []
        for s in lap.samples:
            if abs(s.x) > 1e-6 or abs(s.z) > 1e-6:
                pts.append((float(s.x), float(getattr(s, "y", 0.0)), float(s.z)))
        return pts

    def _lap_points_xyz(self, lap: LapData, elevation_mode: str) -> List[Tuple[float, float, float]]:
        raw = self._lap_points_xyz_raw(lap)
        if elevation_mode != "proxy":
            return raw
        return self._elevation_proxy_xyz(raw)

    def _elevation_proxy_xyz(self, raw_pts: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        """
        Build an elevation proxy from raw (x, y, z) by:
          1) robustly clipping outliers in y
          2) distance-based exponential smoothing of y along the lap polyline
          3) loop-closure correction so start/end heights match
        """
        import numpy as np

        if len(raw_pts) < 3:
            return raw_pts

        xs = np.array([p[0] for p in raw_pts], dtype=float)
        ys = np.array([p[1] for p in raw_pts], dtype=float)
        zs = np.array([p[2] for p in raw_pts], dtype=float)

        # 1) Robust clip raw Y
        lo = float(np.percentile(ys, 100.0 - self._elev_outlier_clip_pct))
        hi = float(np.percentile(ys, self._elev_outlier_clip_pct))
        ys_clip = np.clip(ys, lo, hi)

        # Compute horizontal step distances (XZ plane)
        dx = np.diff(xs)
        dz = np.diff(zs)
        ds = np.sqrt(dx * dx + dz * dz)
        ds = np.where(ds < 1e-6, 1e-6, ds)

        # 2) Distance-based exponential smoothing
        tau = max(float(self._elev_tau_m), 1e-3)
        alpha = np.exp(-ds / tau)

        y_smooth = np.empty_like(ys_clip)
        y_smooth[0] = ys_clip[0]
        for i in range(1, len(ys_clip)):
            a = alpha[i - 1]
            y_smooth[i] = a * y_smooth[i - 1] + (1.0 - a) * ys_clip[i]

        # 3) Loop-closure correction
        end_delta = y_smooth[-1] - y_smooth[0]
        if abs(end_delta) > 1e-9:
            t = np.linspace(0.0, 1.0, len(y_smooth))
            y_smooth = y_smooth - t * end_delta

        # Remove residual mean offset (keeps center stable)
        y_smooth = y_smooth - float(np.mean(y_smooth))

        return list(zip(xs.tolist(), y_smooth.tolist(), zs.tolist()))

    def _compute_norm(self, lap: LapData, elevation_mode: str) -> None:
        pts = self._lap_points_xyz(lap, elevation_mode=elevation_mode)
        if not pts:
            self._norm_center = None
            self._norm_scale = 1.0
            self._y_scale = 1.0
            return

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        cz = (min(zs) + max(zs)) / 2.0

        # Footprint scaling
        x_span = max(xs) - min(xs)
        z_span = max(zs) - min(zs)
        footprint = max(x_span, z_span, 1e-6)
        self._norm_center = (cx, cy, cz)
        self._norm_scale = 200.0 / footprint

        # Elevation scaling independent from footprint
        y_span = max(ys) - min(ys)
        if y_span < 0.05:
            self._y_scale = 0.0
        else:
            target_y_span = 25.0
            self._y_scale = (target_y_span / y_span) * self._y_exaggeration

    def _normalize_point(self, p: Tuple[float, float, float]) -> Tuple[float, float, float]:
        if self._norm_center is None:
            return p
        cx, cy, cz = self._norm_center
        s = self._norm_scale
        ys = self._y_scale
        return ((p[0] - cx) * s, (p[1] - cy) * ys, (p[2] - cz) * s)

    def _normalize_pts(self, pts: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        return [self._normalize_point(p) for p in pts]

    def _grade_colors_rgba(self, raw_pts: List[Tuple[float, float, float]]):
        """Compute per-vertex RGBA colors based on grade (slope) along X/Z."""
        import numpy as np

        n = len(raw_pts)
        if n < 2:
            return np.ones((n, 4), dtype=float)

        xs = np.array([p[0] for p in raw_pts], dtype=float)
        ys = np.array([p[1] for p in raw_pts], dtype=float)
        zs = np.array([p[2] for p in raw_pts], dtype=float)

        dx = np.diff(xs)
        dz = np.diff(zs)
        dy = np.diff(ys)

        ds = np.sqrt(dx * dx + dz * dz)
        ds = np.where(ds < 1e-6, 1e-6, ds)
        grade_seg = dy / ds  # length n-1

        grade_v = np.zeros(n, dtype=float)
        grade_v[1:-1] = 0.5 * (grade_seg[:-1] + grade_seg[1:])
        grade_v[0] = grade_seg[0]
        grade_v[-1] = grade_seg[-1]

        abs_g = np.abs(grade_v)
        clip = float(np.percentile(abs_g, 95)) if np.any(abs_g > 0) else 0.0
        clip = max(clip, 1e-3)
        g = np.clip(grade_v / clip, -1.0, 1.0)

        flat = np.array([0.2, 1.0, 0.4], dtype=float)
        up = np.array([1.0, 0.25, 0.25], dtype=float)
        down = np.array([0.25, 0.55, 1.0], dtype=float)

        t = np.abs(g)
        sign = np.sign(g)

        rgb = np.empty((n, 3), dtype=float)
        up_mask = sign >= 0
        rgb[up_mask] = (1.0 - t[up_mask, None]) * flat + t[up_mask, None] * up
        rgb[~up_mask] = (1.0 - t[~up_mask, None]) * flat + t[~up_mask, None] * down

        a = np.ones((n, 1), dtype=float)
        return np.concatenate([rgb, a], axis=1)

    def _upsert_line(self, lap: LapData, which: str, elevation_mode: str) -> None:
        gl = self._gl
        if gl is None or self.view is None:
            return

        raw_pts = self._lap_points_xyz(lap, elevation_mode=elevation_mode)
        pts = self._normalize_pts(raw_pts)
        if len(pts) < 2:
            return

        import numpy as np
        pos = np.array(pts, dtype=float)

        if which == "ref":
            color = (0.2, 0.8, 1.0, 1.0)
            width = 2
            item_attr = "_ref_item"
        else:
            color = (0.2, 1.0, 0.4, 1.0)
            width = 2
            item_attr = "_last_item"

        colors = None
        if which == "last" and self._grade_coloring_enabled:
            try:
                colors = self._grade_colors_rgba(raw_pts)
            except Exception:
                colors = None

        item = getattr(self, item_attr)
        if item is None:
            if colors is not None:
                item = gl.GLLinePlotItem(pos=pos, color=colors, width=width, antialias=True)
            else:
                item = gl.GLLinePlotItem(pos=pos, color=color, width=width, antialias=True)
            self.view.addItem(item)
            setattr(self, item_attr, item)
        else:
            try:
                if colors is not None:
                    item.setData(pos=pos, color=colors)
                else:
                    item.setData(pos=pos)
            except Exception:
                # If a context hiccup happened mid-run, try to recreate this item.
                try:
                    self.view.removeItem(item)
                except Exception:
                    pass
                if colors is not None:
                    item = gl.GLLinePlotItem(pos=pos, color=colors, width=width, antialias=True)
                else:
                    item = gl.GLLinePlotItem(pos=pos, color=color, width=width, antialias=True)
                self.view.addItem(item)
                setattr(self, item_attr, item)

    def _upsert_car(self, p: Tuple[float, float, float]) -> None:
        gl = self._gl
        if gl is None or self.view is None:
            return

        p_n = self._normalize_point(p)

        import numpy as np
        pos = np.array([p_n], dtype=float)

        if self._car_item is None:
            self._car_item = gl.GLScatterPlotItem(pos=pos, size=8, color=(1.0, 1.0, 1.0, 1.0))
            self.view.addItem(self._car_item)
        else:
            try:
                self._car_item.setData(pos=pos)
            except Exception:
                pass

    def _autoframe(self, lap: Optional[LapData], elevation_mode: str) -> None:
        if lap is None or self.view is None:
            return
        pts = self._normalize_pts(self._lap_points_xyz(lap, elevation_mode=elevation_mode))
        if not pts:
            return

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        cz = (min(zs) + max(zs)) / 2.0

        try:
            self.view.opts["center"] = self._gl.Vector(cx, cy, cz)  # type: ignore[attr-defined]
        except Exception:
            pass
