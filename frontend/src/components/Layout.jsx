import React, { useState } from 'react';
import { Menu } from 'lucide-react';
import Sidebar from './Sidebar';

const Layout = ({ children }) => {
    const [sidebarOpen, setSidebarOpen] = useState(false);

    const toggleSidebar = () => setSidebarOpen(!sidebarOpen);
    const closeSidebar = () => setSidebarOpen(false);

    return (
        <div className="flex min-h-screen bg-[#0a0a0a] text-slate-200 font-sans">
            <Sidebar isOpen={sidebarOpen} onClose={closeSidebar} />

            {/* Main content area */}
            <div className="flex-1 lg:ml-64 ml-0 flex flex-col">
                {/* Mobile header */}
                <header className="lg:hidden sticky top-0 z-30 bg-[#111111] border-b border-slate-800 px-4 py-3 flex items-center gap-3">
                    <button
                        onClick={toggleSidebar}
                        className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
                        aria-label="Open navigation menu"
                        aria-expanded={sidebarOpen}
                    >
                        <Menu size={24} />
                    </button>
                    <span className="text-lg font-bold text-white">EXPENSIO</span>
                </header>

                {/* Page content */}
                <main className="flex-1 p-4 lg:p-8">
                    <div className="max-w-7xl mx-auto">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
};

export default Layout;
