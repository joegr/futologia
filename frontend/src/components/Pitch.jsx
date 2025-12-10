import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

function Pitch({ events, homeTeam, awayTeam }) {
  const svgRef = useRef(null);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    const width = 1800; // 3x previous width
    const height = 1080; // 3x previous height
    const margin = { top: 20, right: 20, bottom: 20, left: 20 };

    svg.attr('viewBox', `0 0 ${width} ${height}`);
    svg.selectAll('*').remove();

    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Draw simple pitch (horizontal, 0-1 x,y from our data)
    g.append('rect')
      .attr('x', 0)
      .attr('y', 0)
      .attr('width', innerWidth)
      .attr('height', innerHeight)
      .attr('fill', '#0b7f3b')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 2);

    // Center line
    g.append('line')
      .attr('x1', innerWidth / 2)
      .attr('y1', 0)
      .attr('x2', innerWidth / 2)
      .attr('y2', innerHeight)
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 2);

    // Center circle
    const centerRadius = innerHeight * 0.18;
    g.append('circle')
      .attr('cx', innerWidth / 2)
      .attr('cy', innerHeight / 2)
      .attr('r', centerRadius)
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 2)
      .attr('fill', 'none');

    const xScale = d3
      .scaleLinear()
      .domain([0, 1])
      .range([0, innerWidth]);

    const yScale = d3
      .scaleLinear()
      .domain([0, 1])
      .range([innerHeight, 0]);

    // Simple binary coloring: home vs away
    const teamColors = {
      [homeTeam]: '#3498db',
      [awayTeam]: '#e74c3c',
    };

    const colorForEvent = (d) => {
      const baseTeamColor = teamColors[d.team] || '#7f8c8d';
      return baseTeamColor;
    };

    // Plot events with known x,y
    g.selectAll('circle.event')
      .data(events.filter((e) => e.x != null && e.y != null))
      .enter()
      .append('circle')
      .attr('class', 'pitch-event')
      .attr('cx', (d) => xScale(d.x))
      .attr('cy', (d) => yScale(d.y))
      .attr('r', (d) => (d.event_type === 'SHOT' ? 8 : 5))
      .attr('fill', (d) => colorForEvent(d))
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 1.5)
      .append('title')
      .text(
        (d) =>
          `${d.match_time.toFixed ? d.match_time.toFixed(1) : d.match_time}s ` +
          `| ${d.team} | ${d.event_type} | ${d.description || ''}`
      );
  }, [events]);

  return (
    <div className="pitch-container">
      <svg ref={svgRef} className="pitch-svg" />
      <div className="pitch-legend">
        <div className="legend-item">
          <span className="legend-swatch legend-home" /> {homeTeam}
        </div>
        <div className="legend-item">
          <span className="legend-swatch legend-away" /> {awayTeam}
        </div>
        <div className="legend-item">
          <span className="legend-swatch legend-shot" /> Shot (larger marker)
        </div>
      </div>
    </div>
  );
}

export default Pitch;
