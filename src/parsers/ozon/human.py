"""Human-like interaction: Bezier mouse paths, Fitts-law dwell, natural scroll."""
from __future__ import annotations

import asyncio
import math
import random
from typing import Sequence


def _bezier(p0: tuple[float, float], p1: tuple[float, float],
            p2: tuple[float, float], p3: tuple[float, float],
            steps: int) -> list[tuple[float, float]]:
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        x = (mt**3)*p0[0] + 3*(mt**2)*t*p1[0] + 3*mt*(t**2)*p2[0] + (t**3)*p3[0]
        y = (mt**3)*p0[1] + 3*(mt**2)*t*p1[1] + 3*mt*(t**2)*p2[1] + (t**3)*p3[1]
        # micro jitter
        x += random.gauss(0, 0.4)
        y += random.gauss(0, 0.4)
        pts.append((x, y))
    return pts


def _fitts_time(distance: float, width: float = 20.0) -> float:
    """Fitts' law ms: a + b * log2(D/W + 1)."""
    a, b = 0.07, 0.16  # seconds
    return a + b * math.log2(max(distance, 1) / max(width, 1) + 1)


async def bezier_mouse_move(page, x: float, y: float, origin: tuple[float, float] | None = None):
    """Move mouse along a curved path with micro-jitter."""
    try:
        start = origin or (random.uniform(100, 400), random.uniform(100, 400))
        dx, dy = x - start[0], y - start[1]
        dist = math.hypot(dx, dy)
        # Control points offset perpendicular for natural curve
        px, py = -dy / max(dist, 1), dx / max(dist, 1)
        curve = random.uniform(0.15, 0.45) * dist
        c1 = (start[0] + dx*0.3 + px*curve, start[1] + dy*0.3 + py*curve)
        c2 = (start[0] + dx*0.7 + px*curve*0.5, start[1] + dy*0.7 + py*curve*0.5)
        steps = max(20, int(dist / 10))
        pts = _bezier(start, c1, c2, (x, y), steps)
        total = _fitts_time(dist)
        step_sleep = total / max(len(pts), 1)
        for px_, py_ in pts:
            await page.mouse.move(px_, py_)
            await asyncio.sleep(step_sleep * random.uniform(0.7, 1.3))
    except Exception:
        pass


async def random_dwell(min_s: float = 0.5, max_s: float = 2.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def natural_scroll(page, total_px: int = 2500, direction: int = 1):
    """Scroll in variable-size chunks with pauses; triggers lazy-load."""
    scrolled = 0
    while scrolled < total_px:
        step = random.randint(120, 380)
        await page.mouse.wheel(0, direction * step)
        scrolled += step
        # Occasional pause to 'read'
        if random.random() < 0.25:
            await asyncio.sleep(random.uniform(0.6, 1.6))
        else:
            await asyncio.sleep(random.uniform(0.15, 0.45))
        # Rare reverse scroll (user re-reading)
        if random.random() < 0.08:
            await page.mouse.wheel(0, -random.randint(50, 150))
            await asyncio.sleep(random.uniform(0.3, 0.8))


async def human_viewport_tour(page, n_moves: int = 3):
    """Hover a few random spots inside viewport to emit mousemove trails."""
    try:
        viewport = page.viewport_size or {"width": 1536, "height": 864}
        w, h = viewport["width"], viewport["height"]
        origin = (random.uniform(50, w - 50), random.uniform(50, h - 50))
        for _ in range(n_moves):
            tx = random.uniform(50, w - 50)
            ty = random.uniform(50, h - 50)
            await bezier_mouse_move(page, tx, ty, origin)
            origin = (tx, ty)
            await random_dwell(0.3, 1.1)
    except Exception:
        pass


async def human_type(page, selector: str, text: str):
    """Type with variable per-char delay."""
    await page.click(selector)
    await random_dwell(0.2, 0.6)
    for ch in text:
        await page.keyboard.type(ch, delay=random.uniform(60, 180))
    await random_dwell(0.3, 0.9)
