import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Portfolio } from './pages/Portfolio';
import { Accounts } from './pages/Accounts';
import { Instruments } from './pages/Instruments';
import { Transactions } from './pages/Transactions';
import { CorporateActions } from './pages/CorporateActions';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Portfolio />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="/instruments" element={<Instruments />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/corporate-actions" element={<CorporateActions />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
