# -*- coding: utf-8 -*-
"""HTML template used to render Field Guide PDF output."""

from datetime import datetime

from qgis.PyQt.QtCore import QCoreApplication


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


def build_points_html(mark_items):
    """Build styled HTML for clickable point list pages (starts on page 2)."""
    return build_points_html_with_routes(mark_items, route_items=[])


def build_points_html_with_routes(mark_items, route_items, footer_note=None):
    """Build styled HTML with optional all-stops route link cards.

    ``footer_note`` (optional) renders as a muted footer paragraph after the
    point list, e.g. for raster-based selection metadata.
    """
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")

    items_html = []
    for item in mark_items:
        items_html.append(
            """
            <li class=\"mark-item\">
                <a href=\"{url}\" class=\"mark-link\">
                    <span class=\"title\">{point_label} {index}</span>
                    <span class=\"coords\">Lat: {lat} | Lon: {lon}</span>
                    <span class=\"action\">{open_point_action}</span>
                </a>
            </li>
            """.format(
                point_label=_tr("Point"),
                index=item["index"],
                lat=item["latitude"],
                lon=item["longitude"],
                url=item["url"],
                open_point_action=_tr("Open in Google Maps"),
            )
        )

    route_html = []
    for route in route_items:
        route_html.append(
            """
            <li class=\"route-item\">
              <a href=\"{url}\" class=\"route-link\">
                <span class=\"title\">{route_label} {index}</span>
                <span class=\"coords\">{points_range_label} {start} {to_label} {end} ({count} {points_label})</span>
                <span class=\"action\">{open_route_action}</span>
              </a>
            </li>
            """.format(
                route_label=_tr("Route"),
                points_range_label=_tr("Points"),
                to_label=_tr("to"),
                points_label=_tr("points"),
                open_route_action=_tr("Open route in Google Maps"),
                index=route["index"],
                start=route["start_point"],
                end=route["end_point"],
                count=route["point_count"],
                url=route["url"],
            )
        )

    return """
    <html>
    <head>
      <meta charset=\"utf-8\" />
      <style>
        body {{ font-family: Arial, sans-serif; color: #111; margin: 0; padding: 0; }}
        .content {{ padding: 12px 14px 14px 14px; }}
        h2 {{ font-size: 17pt; margin: 0 0 8px 0; }}
        .meta {{ font-size: 10pt; color: #444; margin: 0 0 18px 0; }}
        .mark-list {{ list-style: none; padding: 0; margin: 0; }}
        .route-list {{ list-style: none; padding: 0; margin: 0 0 18px 0; }}
        .route-item {{ margin: 0 0 12px 0; page-break-inside: avoid; }}
        .route-link {{
          display: block;
          text-decoration: none;
          color: #234e52;
          border: 2px solid #2c7a7b;
          border-bottom-width: 4px;
          background: #e6fffa;
          border-radius: 12px;
          padding: 14px 14px;
        }}
        .mark-item {{ margin: 0 0 28px 0; page-break-inside: avoid; }}
        .mark-link {{
          display: block;
          text-decoration: none;
          color: #0f172a;
          border: 2px solid #0b3f75;
          border-bottom-width: 5px;
          background: #fefefe;
          border-radius: 14px;
          padding: 22px 20px;
          min-height: 120px;
        }}
        .title {{ display: block; font-size: 17pt; font-weight: bold; margin-bottom: 10px; }}
        .coords {{ display: block; font-size: 12pt; color: #1f2937; margin-bottom: 16px; }}
        .action {{
          display: inline-block;
          font-size: 13pt;
          font-weight: bold;
          color: #ffffff;
          background: #0b4a8b;
          border: 1px solid #08345f;
          border-radius: 9px;
          padding: 8px 14px;
        }}
        .footer-note {{
          font-size: 9pt;
          color: #555;
          border-top: 1px solid #ccc;
          margin-top: 18px;
          padding-top: 8px;
        }}
      </style>
    </head>
    <body>
      <div class=\"content\">
        <h2>{points_list_title}</h2>
        <p class=\"meta\">{generated_at_label}: {generated_at} | {total_points_label}: {total}</p>
        {routes_section}
        <ul class=\"mark-list\">{items}</ul>
        {footer_section}
      </div>
    </body>
    </html>
    """.format(
        generated_at=generated_at,
        points_list_title=_tr("Points list (tap to open on mobile)"),
        generated_at_label=_tr("Generated at"),
        total_points_label=_tr("Total points"),
        total=len(mark_items),
        routes_section=(
            '<ul class="route-list">{}</ul>'.format("".join(route_html))
            if route_html
            else ''
        ),
        items="".join(items_html),
        footer_section=(
            '<p class="footer-note">{}</p>'.format(footer_note)
            if footer_note
            else ''
        ),
    )
