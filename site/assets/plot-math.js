'use strict';
((root) => {
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  function scale(values, start, end) {
    const numbers = values.filter(finite);
    let low = numbers.length ? Math.min(...numbers) : 0;
    let high = numbers.length ? Math.max(...numbers) : 1;
    const padding = high === low ? Math.max(Math.abs(low) * .08, .01) : (high - low) * .12;
    low -= padding; high += padding;
    const power = Math.floor(Math.log10((high - low) / 4));
    let best;
    for (let exponent = power - 1; exponent <= power + 1; exponent++) {
      for (const factor of [1, 2, 2.5, 5, 10]) {
        const step = factor * 10 ** exponent;
        const minimum = Math.floor(low / step) * step;
        const maximum = Math.ceil(high / step) * step;
        const intervals = Math.round((maximum - minimum) / step);
        if (intervals < 3 || intervals > 5) continue;
        const cost = Math.abs(intervals - 4) * 2 + (maximum - minimum) / (high - low);
        if (!best || cost < best.cost) best = {minimum, maximum, step, intervals, cost};
      }
    }
    const ticks = Array.from({length: best.intervals + 1}, (_, i) => Number((best.minimum + i * best.step).toPrecision(14)));
    return {minimum: ticks[0], maximum: ticks.at(-1), ticks,
      position: value => start + (value - ticks[0]) / (ticks.at(-1) - ticks[0]) * (end - start)};
  }
  const overlaps = (a, b, gap = 4) => a.left < b.left + b.width + gap && a.left + a.width + gap > b.left && a.top < b.top + b.height + gap && a.top + a.height + gap > b.top;
  function placeLabels(points, bounds, obstacles = []) {
    const placed = [];
    const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));
    for (const point of points.filter(p => finite(p.x) && finite(p.y))) {
      const {x, y, width, height} = point;
      if (width > bounds.right - bounds.left || height > bounds.bottom - bounds.top) throw new RangeError('Label exceeds plot area');
      const fit = (left, top) => ({left: clamp(left, bounds.left, bounds.right - width), top: clamp(top, bounds.top, bounds.bottom - height), width, height});
      const candidates = [fit(x + 13, y - height / 2), fit(x - 13 - width, y - height / 2), fit(x - width / 2, y - 14 - height), fit(x - width / 2, y + 14)];
      const clear = box => !obstacles.some(other => overlaps(box, other)) && !placed.some(other => overlaps(box, other)) && !points.some(p => finite(p.x) && finite(p.y) && overlaps(box, {left:p.x - 9, top:p.y - 9, width:18, height:18}, 2));
      let box = candidates.find(clear);
      if (!box) {
        const alternatives = [];
        for (let top = bounds.top; top <= bounds.bottom - height; top += 6) {
          for (let left = bounds.left; left <= bounds.right - width; left += 6) {
            const option = fit(left, top);
            if (clear(option)) alternatives.push(option);
          }
        }
        alternatives.sort((a, b) => Math.hypot(a.left + width / 2 - x, a.top + height / 2 - y) - Math.hypot(b.left + width / 2 - x, b.top + height / 2 - y));
        box = alternatives[0];
      }
      if (!box) throw new RangeError('Labels cannot fit within plot area');
      const anchorX = clamp(x, box.left, box.left + width), anchorY = clamp(y, box.top, box.top + height);
      placed.push({...box, id:point.id, anchorX, anchorY, leader:Math.hypot(anchorX - x, anchorY - y) > 18});
    }
    return placed;
  }
  const formatParameters = (millions, tick = false) => `${tick ? Number(millions.toFixed(1)) : millions.toFixed(1)}M`;
  const hiddenTicks = (plates, ticks) => ticks.map((tick, index) => plates.some(plate => overlaps(plate, tick, 0)) ? index : -1).filter(index => index >= 0);
  function placeTooltip(point, size, bounds, obstacles = [], gap = 20) {
    const {width, height} = size;
    const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
    const fits = box => box.left >= bounds.left && box.top >= bounds.top && box.left + width <= bounds.right && box.top + height <= bounds.bottom && !obstacles.some(other => overlaps(box, other, 2));
    for (const side of ['right', 'left', 'below', 'above']) {
      const horizontal = side === 'right' || side === 'left';
      const desired = horizontal ? point.y - height / 2 : point.x - width / 2;
      const low = horizontal ? bounds.top : bounds.left;
      const high = (horizontal ? bounds.bottom - height : bounds.right - width);
      if (high < low) continue;
      const offsets = [desired, low, high, horizontal ? point.y - height - gap : point.x - width - gap, horizontal ? point.y + gap : point.x + gap];
      for (const box of obstacles) offsets.push(horizontal ? box.top - height - 4 : box.left - width - 4, horizontal ? box.top + box.height + 4 : box.left + box.width + 4);
      const positions = [...new Set(offsets.map(value => clamp(value, low, high)))].sort((a, b) => Math.abs(a - desired) - Math.abs(b - desired));
      for (const offset of positions) {
        const box = {width, height, side,
          left: horizontal ? side === 'right' ? point.x + gap : point.x - gap - width : offset,
          top: horizontal ? offset : side === 'below' ? point.y + gap : point.y - gap - height};
        if (fits(box)) return box;
      }
    }
    return null;
  }
  const api = {finite, scale, overlaps, placeLabels, formatParameters, hiddenTicks, placeTooltip};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.MagbenchPlotMath = api;
})(typeof globalThis === 'undefined' ? this : globalThis);
