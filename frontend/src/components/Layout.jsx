import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Receipt, PieChart, Settings } from 'lucide-react';

const SidebarItem = ({ to, icon: Icon, label }) => {
    const location = useLocation();
    const isActive = location.pathname === to;
    
    return (
        <Link to={to} className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${isActive ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>
            <Icon size={20} />
            <span className="font-medium">{label}</span>
        </Link>
    );
};

const Layout = ({ children }) => {
    return (
        <div className="flex min-h-screen">
            {/* Sidebar */}
            <aside className="w-64 bg-white border-r border-slate-200 fixed h-full">
                <div className="p-6 border-b border-slate-100">
                    <h1 className="text-2xl font-bold text-blue-600">FinTracker</h1>
                </div>
                <nav className="p-4 space-y-2">
                    <SidebarItem to="/" icon={LayoutDashboard} label="Dashboard" />
                    <SidebarItem to="/transactions" icon={Receipt} label="Transactions" />
                    <SidebarItem to="/analytics" icon={PieChart} label="Analytics" />
                    <SidebarItem to="/settings" icon={Settings} label="Settings" />
                </nav>
            </aside>

            {/* Main Content */}
            <main className="ml-64 flex-1 p-8">
                {children}
            </main>
        </div>
    );
};

export default Layout;