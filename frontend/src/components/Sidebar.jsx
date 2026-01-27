import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Receipt, AlertCircle, Copy, Wallet } from 'lucide-react';

const Sidebar = () => {
    const location = useLocation();
    
    const menuItems = [
        { icon: LayoutDashboard, label: 'Home', path: '/' },
        { icon: Receipt, label: 'Expenses', path: '/transactions' },
    ];

    const actionItems = [
        { icon: AlertCircle, label: 'Needs Review', path: '/needs-review' },
        { icon: Copy, label: 'Potential Duplicates', path: '/duplicates' },
    ];

    const NavItem = ({ item, isAction }) => {
        const isActive = location.pathname === item.path;
        return (
            <Link 
                to={item.path}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                    isActive 
                        ? 'bg-slate-800 text-teal-400' 
                        : isAction 
                            ? 'text-rose-400 hover:bg-rose-500/10' 
                            : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                }`}
            >
                <item.icon size={20} />
                <span className="font-medium">{item.label}</span>
            </Link>
        );
    };

    return (
        <div className="w-64 h-screen bg-[#111111] text-white flex flex-col p-6 fixed left-0 top-0 border-r border-slate-800 z-50">
            {/* Logo */}
            <div className="flex items-center gap-2 text-teal-400 mb-8 px-2">
                <Wallet size={28} />
                <span className="text-xl font-bold tracking-wider text-white">EXPENSIO</span>
            </div>

            {/* Greeting */}
            <div className="mb-8 px-2">
                <div className="text-slate-400 text-xs uppercase font-bold tracking-wider mb-1">Welcome</div>
                <h2 className="text-2xl font-semibold text-white">Hi, Prem</h2>
            </div>

            {/* Main Menu */}
            <nav className="space-y-2 mb-8">
                {menuItems.map((item) => <NavItem key={item.label} item={item} />)}
            </nav>

            {/* Action Items Section */}
            <div>
                <div className="px-4 text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">
                    Actions
                </div>
                <nav className="space-y-2">
                    {actionItems.map((item) => <NavItem key={item.label} item={item} isAction={true} />)}
                </nav>
            </div>
        </div>
    );
};

export default Sidebar;