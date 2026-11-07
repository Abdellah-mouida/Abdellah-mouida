#!/usr/bin/env python3
"""Generate self-hosted GitHub profile SVG cards for Abdellah-mouida.

Uses GitHub's public REST API plus the authenticated Actions token when available.
No third-party stats-card service is required to render the profile.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

USER = "Abdellah-mouida"
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def request_json(url: str, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Abdellah-Mouida-Profile-Assets",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def request_text(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; profile-assets/1.0)", "Accept": "text/html"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", "replace")


def safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def get_profile_data():
    profile = request_json(f"https://api.github.com/users/{USER}")
    repos = []
    for page in range(1, 4):
        batch = request_json(
            f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={page}&sort=updated"
        )
        repos.extend(batch)
        if len(batch) < 100:
            break
    repos = [repo for repo in repos if not repo.get("private")]

    stars = sum(safe_int(repo.get("stargazers_count")) for repo in repos)
    forks = sum(safe_int(repo.get("forks_count")) for repo in repos)
    original_repos = [repo for repo in repos if not repo.get("fork")]

    language_bytes = Counter()
    for repo in original_repos:
        language_url = repo.get("languages_url")
        if not language_url:
            continue
        try:
            values = request_json(language_url)
            for name, amount in values.items():
                language_bytes[name] += safe_int(amount)
        except Exception:
            fallback = repo.get("language")
            if fallback:
                language_bytes[fallback] += max(1, safe_int(repo.get("size")))

    return {
        "public_repos": safe_int(profile.get("public_repos")),
        "followers": safe_int(profile.get("followers")),
        "stars": stars,
        "forks": forks,
        "original_repos": len(original_repos),
        "languages": language_bytes,
    }, repos


def get_contribution_days():
    # GraphQL provides the full contribution calendar when the token allows it.
    if TOKEN:
        query = """
        query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              contributionCalendar {
                totalContributions
                weeks { contributionDays { date contributionCount } }
              }
            }
          }
        }
        """
        try:
            result = request_json(
                "https://api.github.com/graphql",
                method="POST",
                payload={"query": query, "variables": {"login": USER}},
            )
            calendar = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            days = {}
            for week in calendar.get("weeks", []):
                for day in week.get("contributionDays", []):
                    days[day["date"]] = safe_int(day.get("contributionCount"))
            if days:
                return days, safe_int(calendar.get("totalContributions")), "contributions"
        except Exception as error:
            print(f"GraphQL contribution calendar unavailable; trying public calendar: {error}")

    # GitHub's public profile contribution fragment is a no-key fallback.
    try:
        fragment = request_text(f"https://github.com/users/{USER}/contributions")
        days = {}
        for tag in re.findall(r"<[^>]+>", fragment):
            date_match = re.search(r"""data-date=["'](\d{4}-\d{2}-\d{2})["']""", tag)
            count_match = re.search(r"""data-count=["'](\d+)["']""", tag)
            if date_match and count_match:
                days[date_match.group(1)] = safe_int(count_match.group(1))
        if days:
            return days, sum(days.values()), "contributions"
    except Exception as error:
        print(f"Public contribution fragment unavailable: {error}")

    # Last-resort fallback: show recent public event volume, honestly labelled.
    days: Counter[str] = Counter()
    try:
        events = request_json(f"https://api.github.com/users/{USER}/events/public?per_page=100")
        for event in events:
            timestamp = event.get("created_at")
            if timestamp:
                day = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
                days[day] += 1
        return dict(days), sum(days.values()), "recent public events"
    except Exception as error:
        print(f"Recent public events unavailable: {error}")
        return {}, 0, "activity"


def svg_header(width: int, height: int, title: str, subtitle: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="{width}" y2="{height}" gradientUnits="userSpaceOnUse"><stop stop-color="#101D30"/><stop offset="1" stop-color="#090F19"/></linearGradient>
  <linearGradient id="blue" x1="0" y1="0" x2="{width}" y2="0" gradientUnits="userSpaceOnUse"><stop stop-color="#367BE5"/><stop offset="1" stop-color="#85C3FF"/></linearGradient>
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7"/></filter>
</defs>
<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="18" fill="url(#bg)" stroke="#263F60"/>
<circle cx="{width-32}" cy="20" r="48" fill="#2563EB" opacity=".08" filter="url(#glow)"/>
<text x="28" y="38" fill="#E6F1FF" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="18" font-weight="700">{html.escape(title)}</text>
<text x="28" y="59" fill="#829BB9" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="11">{html.escape(subtitle)}</text>
<circle cx="{width-29}" cy="30" r="4" fill="#62D6A7"><animate attributeName="opacity" values="1;.3;1" dur="2.2s" repeatCount="indefinite"/></circle>
'''


def write_stats(metrics, contribution_total, contribution_label):
    cards = [
        ("PUBLIC REPOSITORIES", str(metrics["public_repos"]), "projects in the open"),
        ("STARS EARNED", str(metrics["stars"]), "across public repositories"),
        ("FOLLOWERS", str(metrics["followers"]), "people following the journey"),
        ("CONTRIBUTIONS", f"{contribution_total:,}", contribution_label + " · yearly view"),
    ]
    svg = [svg_header(1000, 190, "GITHUB / PROFILE OVERVIEW", "Live public profile metrics · refreshed automatically")]
    x_positions = [26, 270, 514, 758]
    for index, (label, value, caption) in enumerate(cards):
        x = x_positions[index]
        svg.append(f'<rect x="{x}" y="82" width="216" height="82" rx="12" fill="#101C2C" stroke="#294665"/>')
        svg.append(f'<text x="{x+16}" y="105" fill="#83A6CE" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="10" letter-spacing="1">{html.escape(label)}</text>')
        svg.append(f'<text x="{x+16}" y="139" fill="#E8F3FF" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="27" font-weight="700">{html.escape(value)}</text>')
        svg.append(f'<text x="{x+16}" y="155" fill="#7892B2" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="9">{html.escape(caption)}</text>')
        svg.append(f'<rect x="{x}" y="82" width="216" height="2" rx="1" fill="url(#blue)"><animate attributeName="opacity" values=".45;1;.45" dur="{2.4+index*.35}s" repeatCount="indefinite"/></rect>')
    svg.append('<text x="28" y="180" fill="#607D9E" font-family="monospace" font-size="9">NO THIRD-PARTY STATS SERVICE REQUIRED · SOURCE: GITHUB API</text>')
    svg.append("</svg>")
    (ASSETS / "stats-overview.svg").write_text("\n".join(svg), encoding="utf-8")


def write_languages(languages: Counter):
    ranked = languages.most_common(7)
    total = sum(languages.values())
    svg = [svg_header(1000, 370, "LANGUAGES / THE TOOLBOX", "Aggregated by bytes across public, non-fork repositories")]
    if not ranked or total <= 0:
        svg.append('<text x="30" y="125" fill="#A8BCD5" font-family="sans-serif" font-size="15">Language data is warming up. The next scheduled refresh will try again.</text>')
    else:
        palette = ["#68A9FF", "#51D6B0", "#A78BFA", "#F4B860", "#F28AA3", "#71C9D8", "#B1C0D7"]
        y = 91
        for index, (name, amount) in enumerate(ranked):
            percent = amount * 100 / total
            color = palette[index % len(palette)]
            bar_width = max(2, 900 * percent / 100)
            svg.append(f'<text x="30" y="{y+4}" fill="#DCE9F8" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="13">{html.escape(name)}</text>')
            svg.append(f'<text x="968" y="{y+4}" text-anchor="end" fill="#94AAC6" font-family="monospace" font-size="12">{percent:.1f}%</text>')
            svg.append(f'<rect x="30" y="{y+14}" width="938" height="8" rx="4" fill="#1A2A40"/>')
            svg.append(f'<rect x="30" y="{y+14}" width="{bar_width:.2f}" height="8" rx="4" fill="{color}"><animate attributeName="width" from="0" to="{bar_width:.2f}" dur="1.1s" fill="freeze"/></rect>')
            y += 37
    svg.append("</svg>")
    svg.append('<text x="30" y="352" fill="#607D9E" font-family="monospace" font-size="9">MORE BREATHING ROOM. SAME AMOUNT OF NERD.</text>')
    (ASSETS / "top-languages.svg").write_text("\n".join(svg), encoding="utf-8")


def write_activity(days: dict[str, int], total: int, label: str):
    today = dt.datetime.now(dt.timezone.utc).date()
    end = today
    start = end - dt.timedelta(days=363)
    start_monday = start - dt.timedelta(days=start.weekday())
    weeks = ((end - start_monday).days // 7) + 1
    cell = 12
    gap = 4
    x0 = 118
    y0 = 83
    svg = [svg_header(1000, 235, "CONTRIBUTION ACTIVITY", f"{total:,} {label} · last 52 weeks · GitHub refreshed data")]
    weekdays = [("Mon", 0), ("Wed", 2), ("Fri", 4)]
    for name, row in weekdays:
        svg.append(f'<text x="77" y="{y0+row*(cell+gap)+10}" text-anchor="end" fill="#718BA9" font-family="Inter,Arial,sans-serif" font-size="10">{name}</text>')
    month_names = {}
    for column in range(weeks):
        week_date = start_monday + dt.timedelta(days=column*7)
        if week_date.month not in month_names:
            month_names[week_date.month] = (column, week_date.strftime("%b"))
    for month, (column, name) in month_names.items():
        x = x0 + column*(cell+gap)
        svg.append(f'<text x="{x}" y="75" fill="#718BA9" font-family="Inter,Arial,sans-serif" font-size="10">{name}</text>')
    for offset in range(364):
        date = start + dt.timedelta(days=offset)
        if date > end:
            continue
        week = (date - start_monday).days // 7
        day = date.weekday()
        count = safe_int(days.get(date.isoformat(), 0))
        color = "#172537" if count == 0 else "#1B4777" if count == 1 else "#2865A8" if count <= 3 else "#3D8BFF" if count <= 6 else "#91C8FF"
        x = x0 + week*(cell+gap)
        y = y0 + day*(cell+gap)
        svg.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{color}"><title>{date.isoformat()}: {count}</title></rect>')
    svg.append('<circle cx="140" cy="211" r="3" fill="#172537"/><text x="149" y="215" fill="#718BA9" font-family="Inter,Arial,sans-serif" font-size="10">Less</text>')
    legend_x = 194
    for color in ["#1B4777", "#2865A8", "#3D8BFF", "#91C8FF"]:
        svg.append(f'<rect x="{legend_x}" y="208" width="9" height="9" rx="2" fill="{color}"/>')
        legend_x += 18
    svg.append('<text x="275" y="215" fill="#718BA9" font-family="Inter,Arial,sans-serif" font-size="10">More</text>')
    svg.append('<text x="968" y="215" text-anchor="end" fill="#526D8E" font-family="monospace" font-size="9">ONE DAY AT A TIME.</text>')
    svg.append("</svg>")
    (ASSETS / "contribution-activity.svg").write_text("\n".join(svg), encoding="utf-8")


def copy_snake():
    # Keep the contribution animation self-hosted too. If the snake workflow has
    # not published yet, leave any previously generated copy untouched.
    url = f"https://raw.githubusercontent.com/{USER}/{USER}/output/github-contribution-grid-snake-dark.svg"
    target = ASSETS / "contribution-snake.svg"
    try:
        content = request_text(url)
        if content.lstrip().startswith("<svg"):
            target.write_text(content, encoding="utf-8")
    except Exception as error:
        print(f"Snake asset not refreshed (existing copy is retained): {error}")


def main():
    metrics, _ = get_profile_data()
    days, contribution_total, contribution_label = get_contribution_days()
    write_stats(metrics, contribution_total, contribution_label)
    write_languages(metrics["languages"])
    write_activity(days, contribution_total, contribution_label)
    copy_snake()
    print("Generated profile assets:")
    for path in sorted(ASSETS.glob("*.svg")):
        print(f" - {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
