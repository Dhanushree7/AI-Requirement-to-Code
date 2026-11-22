import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import FloatingAssistant from './FloatingAssistant';
import NewProjectModal from '../NewProjectModal';

export default function Layout() {
  return (
    <div className="min-h-screen bg-[#0B0F17] text-slate-100 flex">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content Area (offset by 255px) */}
      <div className="flex-1 ml-[255px] flex flex-col min-h-screen">
        <TopBar />
        <main className="flex-1 p-8 overflow-y-auto">
          <Outlet />
        </main>
      </div>

      {/* Floating Project-Aware Assistant */}
      <FloatingAssistant />

      {/* New Project Creation Modal */}
      <NewProjectModal />
    </div>
  );
}
