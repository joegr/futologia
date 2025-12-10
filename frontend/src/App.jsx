import React from 'react';
import MatchView2 from './components/MatchView2.jsx';

function App() {
  return (
    <div className="app-root">
      <header className="app-header">
        <h1>Soccer Match Event Viewer</h1>
      </header>
      <main className="app-main">
        <MatchView2 />
      </main>
    </div>
  );
}

export default App;
