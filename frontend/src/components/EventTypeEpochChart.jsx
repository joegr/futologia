import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

const EVENT_COLORS = {
  SHOT: '#e74c3c',
  PASS: '#3498db',
  FOUL: '#9b59b6',
  TURNOVER: '#e67e22',
  TACKLE: '#2ecc71',
  DRIBBLE: '#1abc9c',
  INTERCEPTION: '#f1c40f',
  SAVE: '#34495e',
  CLEARANCE: '#7f8c8d',
  OTHER: '#95a5a6',
};

function EventTypeEpochChart({ events, maxTime, windowStart, windowEnd }) {
  const svgRef = useRef(null);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    const width = 800;
    const height = 260;
    const margin = { top: 20, right: 100, bottom: 30, left: 40 };

    svg.attr('viewBox', `0 0 ${width} ${height}`);
    svg.selectAll('*').remove();

    if (!events.length || maxTime <= 0) {
      return;
    }

    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Fixed bin size of 5 seconds. For each event in the selected time window,
    // look at the NEXT event that occurs within 5 seconds. Aggregate those
    // next-event types into 5s bins based on the time of the current event,
    // then turn counts into probabilities and render a stacked histogram.

    const types = Array.from(new Set(events.map((e) => e.event_type))).sort();
    if (!types.length) {
      return;
    }

    const rangeStart = windowStart != null ? windowStart : 0;
    const rangeEnd =
      windowEnd != null && windowEnd > rangeStart ? windowEnd : maxTime;

    if (rangeEnd <= rangeStart) {
      return;
    }

    const HORIZON = 5; // seconds after each event to look for the next event

    // Sort events by time
    const sorted = [...events].sort((a, b) => a.match_time - b.match_time);

    // Bin size is fixed at 5 seconds
    const binSize = HORIZON;
    const binCount = Math.max(1, Math.ceil((rangeEnd - rangeStart) / binSize));

    const countsPerBin = Array.from({ length: binCount }, () => {
      const obj = {};
      types.forEach((t) => {
        obj[t] = 0;
      });
      return obj;
    });

    for (let i = 0; i < sorted.length - 1; i += 1) {
      const current = sorted[i];
      const next = sorted[i + 1];
      const t = current.match_time;
      const nextTime = next.match_time;

      // Only consider current events inside the slider window
      if (t < rangeStart || t > rangeEnd) continue;

      // Only count the next event if it happens within 5 seconds
      if (nextTime > t + HORIZON) continue;

      let idx = Math.floor((t - rangeStart) / binSize);
      if (idx < 0) idx = 0;
      if (idx >= binCount) idx = binCount - 1;

      const binCounts = countsPerBin[idx];
      const et = next.event_type;
      if (binCounts[et] == null) binCounts[et] = 0;
      binCounts[et] += 1;
    }

    const alpha = 1.0;
    const k = types.length;

    const epochs = [];
    for (let i = 0; i < binCount; i += 1) {
      const start = rangeStart + i * binSize;
      const end = Math.min(rangeEnd, start + binSize);
      const center = (start + end) / 2;

      const counts = countsPerBin[i];
      const total =
        Object.values(counts).reduce((sum, c) => sum + c, 0) + alpha * k;
      const probs = {};
      types.forEach((t) => {
        probs[t] = total > 0 ? (counts[t] + alpha) / total : 1 / k;
      });

      epochs.push({ center, probs });
    }

    const xScale = d3
      .scaleLinear()
      .domain([rangeStart, rangeEnd])
      .range([0, innerWidth]);

    const yScale = d3.scaleLinear().domain([0, 1]).range([innerHeight, 0]);

    const xAxis = d3.axisBottom(xScale).ticks(8).tickFormat((d) => `${d}s`);
    const yAxis = d3
      .axisLeft(yScale)
      .ticks(5)
      .tickFormat((d) => `${Math.round(d * 100)}%`);

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(xAxis);

    g.append('g').call(yAxis);

    const barWidth = (innerWidth / binCount) * 0.9;

    // Stacked histogram: each bin's bar is stacked by event-type probability
    epochs.forEach((epoch) => {
      let acc = 0;
      types.forEach((t) => {
        const p = epoch.probs[t];
        if (!p) return;
        const y0 = acc;
        const y1 = acc + p;
        acc = y1;

        g.append('rect')
          .attr('x', xScale(epoch.center) - barWidth / 2)
          .attr('width', barWidth)
          .attr('y', yScale(y1))
          .attr('height', yScale(y0) - yScale(y1))
          .attr('fill', EVENT_COLORS[t] || EVENT_COLORS.OTHER)
          .append('title')
          .text(
            `${t}: ${Math.round(p * 100)}% at ${
              epoch.center.toFixed ? epoch.center.toFixed(1) : epoch.center
            }s`
          );
      });
    });

    // Simple legend
    const legend = svg
      .append('g')
      .attr('transform', `translate(${width - margin.right + 10},${margin.top})`);

    types.forEach((t, idx) => {
      const y = idx * 16;
      legend
        .append('rect')
        .attr('x', 0)
        .attr('y', y)
        .attr('width', 12)
        .attr('height', 12)
        .attr('fill', EVENT_COLORS[t] || EVENT_COLORS.OTHER);

      legend
        .append('text')
        .attr('x', 18)
        .attr('y', y + 10)
        .attr('font-size', 10)
        .text(t);
    });
  }, [events, maxTime, windowStart, windowEnd]);

  return (
    <div className="timeline-container">
      <svg ref={svgRef} className="timeline-svg" />
    </div>
  );
}

export default EventTypeEpochChart;
