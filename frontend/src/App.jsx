import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './layout/Navbar';
import Landing from './pages/Landing';
import Evaluation from './pages/Evaluation';
import Roadmap from './pages/Roadmap';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-slate-50 font-sans flex flex-col">
        <Navbar />
        <div className="flex-1 relative">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/evaluation" element={<Evaluation />} />
            <Route path="/roadmap" element={<Roadmap />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App;
