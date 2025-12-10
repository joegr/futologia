import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

// Basic color mapping by event type
const eventColors = {
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

function Timeline({ events, maxTime, homeTeam, awayTeam, currentTime }) {
  const svgRef = useRef(null);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    const width = 800;
    const height = 200;
    const margin = { top: 20, right: 20, bottom: 40, left: 40 };

    svg.attr('viewBox', `0 0 ${width} ${height}`);

    svg.selectAll('*').remove();

    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const timeDomainMax = maxTime > 0 ? maxTime : 1;

    const xScale = d3
      .scaleLinear()
      .domain([0, timeDomainMax])
      .range([0, innerWidth]);

    const yScale = d3
      .scaleBand()
      .domain([homeTeam, awayTeam])
      .range([0, innerHeight])
      .padding(0.4);

    const xAxis = d3.axisBottom(xScale).ticks(10).tickFormat((d) => `${d}s`);
    const yAxis = d3.axisLeft(yScale);

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(xAxis);

    g.append('g').call(yAxis);

    // Optional vertical cursor for current time
    if (currentTime != null) {
      const cx = xScale(currentTime);
      g.append('line')
        .attr('class', 'time-cursor')
        .attr('x1', cx)
        .attr('x2', cx)
        .attr('y1', 0)
        .attr('y2', innerHeight)
        .attr('stroke', '#e74c3c')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '4 4');
    }

    // Draw events as circles on a horizontal time line per team
    g.selectAll('circle.event')
      .data(events)
      .enter()
      .append('circle')
      .attr('class', 'event')
      .attr('cx', (d) => xScale(d.match_time))
      .attr('cy', (d) => {
        const team = d.team === homeTeam ? homeTeam : awayTeam;
        return (yScale(team) || 0) + yScale.bandwidth() / 2;
      })
      .attr('r', 5)
      .attr('fill', (d) => eventColors[d.event_type] || eventColors.OTHER)
      .append('title')
      .text(
        (d) =>
          `${d.match_time.toFixed ? d.match_time.toFixed(1) : d.match_time}s ` +
          `| ${d.team} | ${d.event_type} | ${d.description || ''}`
      );
  }, [events, maxTime, homeTeam, awayTeam]);

  return (
    <div className="timeline-container">
      <svg ref={svgRef} className="timeline-svg" />
    </div>
  );
}

export default Timeline;
