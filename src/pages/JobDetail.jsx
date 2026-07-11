import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { base44 } from "@/api/base44Client";
import { ArrowLeft, Users, MapPin, Calendar, Briefcase, DollarSign, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import CandidateCard from "@/components/candidates/CandidateCard";

const STAGE_LABELS = { applied: "Đã ứng tuyển", screening: "Đang sàng lọc", interview: "Phỏng vấn", offer: "Đề nghị", hired: "Đã tuyển", rejected: "Từ chối" };
const TYPE_MAP = { full_time: "Toàn thời gian", part_time: "Bán thời gian", contract: "Hợp đồng", internship: "Thực tập" };

export default function JobDetail() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    const [j, c] = await Promise.all([
      base44.entities.Job.get(id),
      base44.entities.Candidate.filter({ job_id: id }),
    ]);
    setJob(j);
    setCandidates(c);
    setLoading(false);
  };

  useEffect(() => { loadData(); }, [id]);

  if (loading) return <div className="flex items-center justify-center h-full"><div className="w-8 h-8 border-4 border-slate-200 border-t-indigo-600 rounded-full animate-spin" /></div>;
  if (!job) return <div className="p-8 text-center text-slate-500">Không tìm thấy việc làm</div>;

  const rankedCandidates = [...candidates].sort((a, b) => (b.ai_score || 0) - (a.ai_score || 0));

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      <Link to="/jobs" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 transition-colors">
        <ArrowLeft size={16} /> Quay lại danh sách
      </Link>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h1 className="text-2xl font-heading font-bold text-slate-900">{job.title}</h1>
        <div className="flex flex-wrap gap-4 mt-3 text-sm text-slate-500">
          <span className="flex items-center gap-1"><Briefcase size={14} /> {job.department}</span>
          {job.location && <span className="flex items-center gap-1"><MapPin size={14} /> {job.location}</span>}
          {job.employment_type && <span className="flex items-center gap-1"><Clock size={14} /> {TYPE_MAP[job.employment_type]}</span>}
          {job.salary_min && job.salary_max && <span className="flex items-center gap-1"><DollarSign size={14} /> {job.salary_min.toLocaleString()} - {job.salary_max.toLocaleString()}</span>}
          {job.deadline && <span className="flex items-center gap-1"><Calendar size={14} /> Hạn: {job.deadline}</span>}
          <span className="flex items-center gap-1"><Users size={14} /> {candidates.length} ứng viên</span>
        </div>
        {job.skills && (
          <div className="flex flex-wrap gap-2 mt-4">
            {job.skills.split(",").map((s) => (
              <span key={s} className="text-xs bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-full">{s.trim()}</span>
            ))}
          </div>
        )}
        {job.description && (
          <div className="mt-5">
            <h3 className="font-semibold text-sm text-slate-700 mb-2">Mô tả công việc</h3>
            <p className="text-sm text-slate-600 whitespace-pre-wrap">{job.description}</p>
          </div>
        )}
        {job.requirements && (
          <div className="mt-4">
            <h3 className="font-semibold text-sm text-slate-700 mb-2">Yêu cầu</h3>
            <p className="text-sm text-slate-600 whitespace-pre-wrap">{job.requirements}</p>
          </div>
        )}
      </div>

      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Ứng viên ({candidates.length}) — Xếp hạng theo AI Score</h2>
        {rankedCandidates.length === 0 ? (
          <p className="text-slate-400 text-center py-10">Chưa có ứng viên nào</p>
        ) : (
          <div className="space-y-3">
            {rankedCandidates.map((c, i) => (
              <CandidateCard key={c.id} candidate={c} rank={i + 1} onUpdate={loadData} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}