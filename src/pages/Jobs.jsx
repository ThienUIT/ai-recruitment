import React, { useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";
import { Plus, Search, MoreHorizontal, Edit2, Trash2, Eye, Users, Briefcase } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { logAction } from "@/lib/auditLogger";
import { Link } from "react-router-dom";
import JobForm from "@/components/jobs/JobForm";

const STATUS_MAP = {
  draft: { label: "Nháp", color: "bg-slate-100 text-slate-600" },
  open: { label: "Đang mở", color: "bg-emerald-50 text-emerald-700" },
  closed: { label: "Đã đóng", color: "bg-red-50 text-red-600" },
  on_hold: { label: "Tạm dừng", color: "bg-amber-50 text-amber-700" },
};

const TYPE_MAP = { full_time: "Toàn thời gian", part_time: "Bán thời gian", contract: "Hợp đồng", internship: "Thực tập" };

export default function Jobs() {
  const [jobs, setJobs] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showForm, setShowForm] = useState(false);
  const [editingJob, setEditingJob] = useState(null);
  const { toast } = useToast();

  const loadData = async () => {
    const [j, c] = await Promise.all([
      base44.entities.Job.list("-created_date"),
      base44.entities.Candidate.list(),
    ]);
    setJobs(j);
    setCandidates(c);
    setLoading(false);
  };

  useEffect(() => { loadData(); }, []);

  const handleSave = async (data) => {
    if (editingJob) {
      await base44.entities.Job.update(editingJob.id, data);
      await logAction("Cập nhật", "Job", editingJob.id, data.title, `Cập nhật việc làm: ${data.title}`);
      toast({ title: "Đã cập nhật việc làm" });
    } else {
      const created = await base44.entities.Job.create(data);
      await logAction("Tạo mới", "Job", created.id, data.title, `Tạo việc làm mới: ${data.title}`);
      toast({ title: "Đã tạo việc làm mới" });
    }
    setShowForm(false);
    setEditingJob(null);
    loadData();
  };

  const handleDelete = async (job) => {
    await base44.entities.Job.delete(job.id);
    await logAction("Xóa", "Job", job.id, job.title, `Xóa việc làm: ${job.title}`);
    toast({ title: "Đã xóa việc làm" });
    loadData();
  };

  const filtered = jobs.filter((j) => {
    const matchSearch = j.title?.toLowerCase().includes(search.toLowerCase()) || j.department?.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || j.status === statusFilter;
    return matchSearch && matchStatus;
  });

  if (loading) {
    return <div className="flex items-center justify-center h-full"><div className="w-8 h-8 border-4 border-slate-200 border-t-indigo-600 rounded-full animate-spin" /></div>;
  }

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-heading font-bold text-slate-900">Việc làm</h1>
          <p className="text-slate-500 mt-1">{jobs.length} vị trí tuyển dụng</p>
        </div>
        <Button onClick={() => { setEditingJob(null); setShowForm(true); }} className="bg-indigo-600 hover:bg-indigo-700">
          <Plus size={18} className="mr-2" /> Đăng việc làm
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input placeholder="Tìm theo tên hoặc phòng ban..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Trạng thái" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tất cả</SelectItem>
            <SelectItem value="draft">Nháp</SelectItem>
            <SelectItem value="open">Đang mở</SelectItem>
            <SelectItem value="closed">Đã đóng</SelectItem>
            <SelectItem value="on_hold">Tạm dừng</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-20">
          <Briefcase size={48} className="mx-auto text-slate-300 mb-4" />
          <p className="text-slate-500">Chưa có việc làm nào</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {filtered.map((job) => {
            const count = candidates.filter((c) => c.job_id === job.id).length;
            return (
              <div key={job.id} className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <Link to={`/jobs/${job.id}`} className="text-lg font-semibold text-slate-900 hover:text-indigo-600 transition-colors">{job.title}</Link>
                      <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${STATUS_MAP[job.status]?.color}`}>{STATUS_MAP[job.status]?.label}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-4 text-sm text-slate-500">
                      <span>{job.department}</span>
                      {job.location && <span>📍 {job.location}</span>}
                      {job.employment_type && <span>{TYPE_MAP[job.employment_type]}</span>}
                      {job.salary_min && job.salary_max && <span>💰 {job.salary_min.toLocaleString()} - {job.salary_max.toLocaleString()}</span>}
                      <span className="flex items-center gap-1"><Users size={14} /> {count} ứng viên</span>
                    </div>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon"><MoreHorizontal size={18} /></Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem asChild><Link to={`/jobs/${job.id}`}><Eye size={14} className="mr-2" /> Xem chi tiết</Link></DropdownMenuItem>
                      <DropdownMenuItem onClick={() => { setEditingJob(job); setShowForm(true); }}><Edit2 size={14} className="mr-2" /> Chỉnh sửa</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleDelete(job)} className="text-red-600"><Trash2 size={14} className="mr-2" /> Xóa</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Dialog open={showForm} onOpenChange={(v) => { setShowForm(v); if (!v) setEditingJob(null); }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingJob ? "Chỉnh sửa việc làm" : "Đăng việc làm mới"}</DialogTitle>
          </DialogHeader>
          <JobForm job={editingJob} onSave={handleSave} onCancel={() => { setShowForm(false); setEditingJob(null); }} />
        </DialogContent>
      </Dialog>
    </div>
  );
}