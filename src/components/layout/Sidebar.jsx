import React from "react";
import { Link, useLocation } from "react-router-dom";
import { LayoutDashboard, Briefcase, Users, Search, ClipboardList, LogOut, ChevronLeft, ChevronRight } from "lucide-react";
import { base44 } from "@/api/base44Client";
import { useState } from "react";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, path: "/" },
  { label: "Việc làm", icon: Briefcase, path: "/jobs" },
  { label: "Ứng viên", icon: Users, path: "/candidates" },
  { label: "Tìm kiếm AI", icon: Search, path: "/search" },
  { label: "Nhật ký", icon: ClipboardList, path: "/audit-log" },
];

export default function Sidebar() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside className={`${collapsed ? "w-[72px]" : "w-64"} h-screen bg-slate-900 text-white flex flex-col transition-all duration-300 flex-shrink-0`}>
      <div className="p-5 flex items-center justify-between border-b border-slate-700/50">
        {!collapsed && (
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center text-sm font-bold">
              HR
            </div>
            <span className="font-heading font-semibold text-lg tracking-tight">RecruitAI</span>
          </div>
        )}
        <button onClick={() => setCollapsed(!collapsed)} className="p-1.5 rounded-md hover:bg-slate-700/50 transition-colors">
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path || (item.path !== "/" && location.pathname.startsWith(item.path));
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200
                ${isActive
                  ? "bg-indigo-500/20 text-indigo-300"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
              title={collapsed ? item.label : undefined}
            >
              <item.icon size={20} className="flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t border-slate-700/50">
        <button
          onClick={() => base44.auth.logout("/")}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-all w-full"
          title={collapsed ? "Đăng xuất" : undefined}
        >
          <LogOut size={20} className="flex-shrink-0" />
          {!collapsed && <span>Đăng xuất</span>}
        </button>
      </div>
    </aside>
  );
}