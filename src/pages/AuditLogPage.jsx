import React, { useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";
import { ClipboardList, Search, Calendar } from "lucide-react";
import { Input } from "@/components/ui/input";
import moment from "moment";

const ACTION_COLORS = {
  "Tạo mới": "bg-emerald-50 text-emerald-700",
  "Cập nhật": "bg-blue-50 text-blue-700",
  "Xóa": "bg-red-50 text-red-600",
  "Thêm ứng viên": "bg-indigo-50 text-indigo-700",
  "Phân tích CV": "bg-purple-50 text-purple-700",
  "AI Screening": "bg-amber-50 text-amber-700",
  "Cập nhật giai đoạn": "bg-cyan-50 text-cyan-700",
};

export default function AuditLogPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    base44.entities.AuditLog.list("-created_date", 200).then((l) => {
      setLogs(l);
      setLoading(false);
    });
  }, []);

  const filtered = logs.filter((l) =>
    l.action?.toLowerCase().includes(search.toLowerCase()) ||
    l.entity_name?.toLowerCase().includes(search.toLowerCase()) ||
    l.details?.toLowerCase().includes(search.toLowerCase()) ||
    l.performed_by?.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <div className="flex items-center justify-center h-full"><div className="w-8 h-8 border-4 border-slate-200 border-t-indigo-600 rounded-full animate-spin" /></div>;

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-heading font-bold text-slate-900">Nhật ký hoạt động</h1>
        <p className="text-slate-500 mt-1">Theo dõi tất cả thay đổi trong hệ thống</p>
      </div>

      <div className="relative max-w-md">
        <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input placeholder="Tìm trong nhật ký..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" />
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-20">
          <ClipboardList size={48} className="mx-auto text-slate-300 mb-4" />
          <p className="text-slate-500">Chưa có hoạt động nào được ghi nhận</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="divide-y divide-slate-100">
            {filtered.map((log) => (
              <div key={log.id} className="px-5 py-4 hover:bg-slate-50 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <div className="w-2 h-2 rounded-full bg-indigo-400 mt-2 flex-shrink-0" />
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ACTION_COLORS[log.action] || "bg-slate-100 text-slate-600"}`}>
                          {log.action}
                        </span>
                        <span className="text-xs text-slate-400">{log.entity_type}</span>
                      </div>
                      {log.entity_name && <p className="text-sm font-medium text-slate-900">{log.entity_name}</p>}
                      {log.details && <p className="text-sm text-slate-500 mt-0.5">{log.details}</p>}
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0 ml-4">
                    <p className="text-xs text-slate-400">{moment(log.created_date).format("DD/MM/YYYY HH:mm")}</p>
                    {log.performed_by && <p className="text-xs text-slate-500 mt-0.5">{log.performed_by}</p>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}