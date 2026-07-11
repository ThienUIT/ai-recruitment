import React, { useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";
import { Briefcase, Users, UserCheck, Clock, TrendingUp, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const STAGE_COLORS = {
  applied: "#6366f1",
  screening: "#f59e0b",
  interview: "#3b82f6",
  offer: "#8b5cf6",
  hired: "#10b981",
  rejected: "#ef4444",
};

const STAGE_LABELS = {
  applied: "Đã ứng tuyển",
  screening: "Đang sàng lọc",
  interview: "Phỏng vấn",
  offer: "Đề nghị",
  hired: "Đã tuyển",
  rejected: "Từ chối",
};

export default function Dashboard() {
  const [jobs, setJobs] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      base44.entities.Job.list(),
      base44.entities.Candidate.list(),
    ]).then(([j, c]) => {
      setJobs(j);
      setCandidates(c);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-8 h-8 border-4 border-slate-200 border-t-indigo-600 rounded-full animate-spin" />
      </div>
    );
  }

  const openJobs = jobs.filter((j) => j.status === "open").length;
  const totalCandidates = candidates.length;
  const hiredCount = candidates.filter((c) => c.stage === "hired").length;
  const inProcess = candidates.filter((c) => ["screening", "interview", "offer"].includes(c.stage)).length;

  const stageCounts = Object.keys(STAGE_LABELS).map((key) => ({
    name: STAGE_LABELS[key],
    value: candidates.filter((c) => c.stage === key).length,
    fill: STAGE_COLORS[key],
  }));

  const recentCandidates = [...candidates].sort((a, b) => new Date(b.created_date) - new Date(a.created_date)).slice(0, 5);

  const jobStats = jobs.filter(j => j.status === "open").slice(0, 6).map((job) => ({
    name: job.title.length > 15 ? job.title.slice(0, 15) + "…" : job.title,
    count: candidates.filter((c) => c.job_id === job.id).length,
  }));

  const stats = [
    { label: "Việc làm đang mở", value: openJobs, icon: Briefcase, color: "bg-indigo-50 text-indigo-600" },
    { label: "Tổng ứng viên", value: totalCandidates, icon: Users, color: "bg-blue-50 text-blue-600" },
    { label: "Đã tuyển", value: hiredCount, icon: UserCheck, color: "bg-emerald-50 text-emerald-600" },
    { label: "Đang xử lý", value: inProcess, icon: Clock, color: "bg-amber-50 text-amber-600" },
  ];

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-heading font-bold text-slate-900">Dashboard</h1>
        <p className="text-slate-500 mt-1">Tổng quan tuyển dụng</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {stats.map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">{s.label}</p>
                <p className="text-3xl font-bold mt-1">{s.value}</p>
              </div>
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${s.color}`}>
                <s.icon size={22} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="font-semibold text-slate-900 mb-4">Ứng viên theo giai đoạn</h3>
          {candidates.length === 0 ? (
            <p className="text-slate-400 text-sm py-10 text-center">Chưa có dữ liệu</p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={stageCounts.filter(s => s.value > 0)} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} innerRadius={55} paddingAngle={3}>
                  {stageCounts.filter(s => s.value > 0).map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
          <div className="flex flex-wrap gap-3 mt-2">
            {stageCounts.filter(s => s.value > 0).map((s) => (
              <span key={s.name} className="flex items-center gap-1.5 text-xs text-slate-600">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.fill }} />
                {s.name} ({s.value})
              </span>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="font-semibold text-slate-900 mb-4">Ứng viên theo vị trí</h3>
          {jobStats.length === 0 ? (
            <p className="text-slate-400 text-sm py-10 text-center">Chưa có dữ liệu</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={jobStats}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#6366f1" radius={[6, 6, 0, 0]} name="Ứng viên" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-900">Ứng viên gần đây</h3>
          <Link to="/candidates" className="text-sm text-indigo-600 hover:text-indigo-700 flex items-center gap-1">
            Xem tất cả <ArrowRight size={14} />
          </Link>
        </div>
        {recentCandidates.length === 0 ? (
          <p className="text-slate-400 text-sm py-6 text-center">Chưa có ứng viên nào</p>
        ) : (
          <div className="space-y-3">
            {recentCandidates.map((c) => (
              <div key={c.id} className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-sm font-semibold">
                    {c.full_name?.charAt(0)?.toUpperCase() || "?"}
                  </div>
                  <div>
                    <p className="font-medium text-sm text-slate-900">{c.full_name}</p>
                    <p className="text-xs text-slate-500">{c.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {c.ai_score != null && (
                    <span className="text-xs font-semibold text-indigo-600 bg-indigo-50 px-2 py-1 rounded-full">
                      {c.ai_score}/100
                    </span>
                  )}
                  <span className="text-xs px-2.5 py-1 rounded-full font-medium" style={{ backgroundColor: STAGE_COLORS[c.stage] + "20", color: STAGE_COLORS[c.stage] }}>
                    {STAGE_LABELS[c.stage] || c.stage}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}