import { Link, useLocation } from 'react-router-dom';
import { Home, List, Settings, Plus, Receipt } from 'lucide-react';
import { useState } from 'react';
import TransactionModal from './TransactionModal';

const Sidebar = () => {
  const location = useLocation();
  const [showTransactionModal, setShowTransactionModal] = useState(false);

  const navItems = [
    { path: '/', label: 'Dashboard', icon: Home },
    { path: '/accounts', label: 'Accounts', icon: List },
    { path: '/transactions', label: 'Transactions', icon: Receipt },
    { path: '/settings', label: 'Settings', icon: Settings },
  ];

  return (
    <>
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Financial Planner</h1>
        </div>
        
        <nav className="sidebar-nav">
          {navItems.map(({ path, label, icon: Icon }) => (
            <Link
              key={path}
              to={path}
              className={`nav-item ${location.pathname === path ? 'active' : ''}`}
            >
              <Icon />
              {label}
            </Link>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button 
            className="new-transaction-btn"
            onClick={() => setShowTransactionModal(true)}
          >
            <Plus size={16} style={{ marginRight: 8 }} />
            New Transaction
          </button>
        </div>
      </aside>

      {showTransactionModal && (
        <TransactionModal
          onClose={() => setShowTransactionModal(false)}
          onSave={() => {
            setShowTransactionModal(false);
            // TODO: Refresh data
          }}
        />
      )}
    </>
  );
};

export default Sidebar;