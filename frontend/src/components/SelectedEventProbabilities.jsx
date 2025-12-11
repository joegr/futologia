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

function SelectedEventProbabilities({ selectedEvent, events }) {
  const svgRef = useRef(null);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    const width = 600;
    const height = 200;
    const margin = { top: 20, right: 100, bottom: 30, left: 40 };

    svg.attr('viewBox', `0 0 ${width} ${height}`);
    svg.selectAll('*').remove();

    if (!selectedEvent || !events.length) {
      return;
    }

    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Find the next event within 5 seconds
    const sorted = [...events].sort((a, b) => a.match_time - b.match_time);
    const currentIndex = sorted.findIndex(e => e === selectedEvent);
    let nextEvent = null;
    
    if (currentIndex !== -1 && currentIndex < sorted.length - 1) {
      const candidate = sorted[currentIndex + 1];
      if (candidate.match_time <= selectedEvent.match_time + 5) {
        nextEvent = candidate;
      }
    }

    // Build probability distribution based on all similar transitions
    const types = Array.from(new Set(events.map(e => e.event_type))).sort();
    const alpha = 1.0;
    const k = types.length;

    // Count transitions from events of the same type
    const counts = {};
    types.forEach(t => { counts[t] = 0; });

    for (let i = 0; i < sorted.length - 1; i++) {
      const current = sorted[i];
      const next = sorted[i + 1];
      
      if (current.event_type === selectedEvent.event_type && 
          next.match_time <= current.match_time + 5) {
        counts[next.event_type] = (counts[next.event_type] || 0) + 1;
      }
    }

    const total = Object.values(counts).reduce((sum, c) => sum + c, 0) + alpha * k;
    const probs = {};
    types.forEach(t => {
      probs[t] = total > 0 ? (counts[t] + alpha) / total : 1 / k;
    });

    // Create bar chart
    const barWidth = innerWidth / types.length * 0.8;
    const barSpacing = innerWidth / types.length;

    const yScale = d3.scaleLinear()
      .domain([0, 1])
      .range([innerHeight, 0]);

    const yAxis = d3.axisLeft(yScale)
      .ticks(5)
      .tickFormat(d => `${Math.round(d * 100)}%`);

    g.append('g').call(yAxis);

    // Draw bars
    types.forEach((type, i) => {
      const p = probs[type];
      const x = i * barSpacing + (barSpacing - barWidth) / 2;
      const height = innerHeight - yScale(p);
      
      g.append('rect')
        .attr('x', x)
        .attr('y', yScale(p))
        .attr('width', barWidth)
        .attr('height', height)
        .attr('fill', EVENT_COLORS[type] || EVENT_COLORS.OTHER)
        .append('title')
        .text(`${type}: ${Math.round(p * 100)}%`);

      // Add type labels
      g.append('text')
        .attr('x', x + barWidth / 2)
        .attr('y', innerHeight + 15)
        .attr('text-anchor', 'middle')
        .attr('font-size', 10)
        .text(type);
    });

    // Highlight actual next event if it exists
    if (nextEvent) {
      const actualType = nextEvent.event_type;
      const typeIndex = types.indexOf(actualType);
      if (typeIndex !== -1) {
        const x = typeIndex * barSpacing + (barSpacing - barWidth) / 2;
        g.append('rect')
          .attr('x', x - 2)
          .attr('y', yScale(probs[actualType]) - 2)
          .attr('width', barWidth + 4)
          .attr('height', innerHeight - yScale(probs[actualType]) + 4)
          .attr('fill', 'none')
          .attr('stroke', '#000')
          .attr('stroke-width', 2)
          .attr('stroke-dasharray', '3,3');
      }
    }

    // Add title
    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', -5)
      .attr('text-anchor', 'middle')
      .attr('font-size', 12)
      .text(`Next event probabilities after ${selectedEvent.event_type}`);

  }, [selectedEvent, events]);

  return (
    <div className="timeline-container">
      <svg ref={svgRef} className="timeline-svg" />
    </div>
  );
}

export default SelectedEventProbabilities;
