import React, { useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";
import { Plus, Search, Upload, Sparkles, Loader2, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { logAction } from "@/lib/auditLogger";
import CandidateCard from "@/components/candidates/CandidateCard";
import CandidateForm from "@/components/candidates/CandidateForm";

const STAGE_LABELS = { applied: "Đã ứng tuyển", screening: "Đang sàng lọc", interview: "Phỏng vấn", offer: "Đề nghị", hired: "Đã tuyển", rejected: "Từ chối" };

export default function Candidates() {
  const [candidates, setCandidates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState("all");
  const [jobFilter, setJobFilter] = useState("all");
  const [showForm, setShowForm] = useState(false);
  const [screeningId, setScreeningId] = useState(null);
  const { toast } = useToast();

  const loadData = async () => {
    const [c, j] = await Promise.all([
      base44.entities.Candidate.list("-created_date"),
      base44.entities.Job.list(),
    ]);
    setCandidates(c);
    setJobs(j);
    setLoading(false);
  };

  useEffect(() => { loadData(); }, []);

  const handleAddCandidate = async (data) => {
    const created = await base44.entities.Candidate.create(data);
    await logAction("Thêm ứng viên", "Candidate", created.id, data.full_name, `Thêm ứng viên: ${data.full_name}`);
    toast({ title: "Đã thêm ứng viên" });
    setShowForm(false);
    loadData();

    // Auto-parse CV if uploaded
    if (data.cv_url) {
      parseCV(created.id, data.cv_url, data.full_name);
    }
  };

  const parseCV = async (candidateId, cvUrl, name) => {
    toast({ title: "Đang phân tích CV...", description: "AI đang đọc và trích xuất thông tin" });
    const result = await base44.integrations.Core.InvokeLLM({
      prompt: `Analyze this CV/resume file and extract the following information in Vietnamese. Be concise and accurate.`,
      file_urls: [cvUrl],
      response_json_schema: {
        type: "object",
        properties: {
          skills: { type: "string", description: "Comma-separated list of skills" },
          education: { type: "string", description: "Highest education level and institution" },
          experience_years: { type: "number", description: "Total years of experience" },
          parsed_summary: { type: "string", description: "Brief summary of the candidate profile in Vietnamese" }
        }
      }
    });
    await base44.entities.Candidate.update(candidateId, {
      skills: result.skills || "",
      education: result.education || "",
      experience_years: result.experience_years || 0,
      parsed_data: result.parsed_summary || "",
    });
    await logAction("Phân tích CV", "Candidate", candidateId, name, "AI đã phân tích CV");
    toast({ title: "Đã phân tích CV xong" });
    loadData();
  };

  const handleAIScreen = async (candidate) => {
    setScreeningId(candidate.id);
    const job = jobs.find((j) => j.id === candidate.job_id);
    const result = await base44.integrations.Core.InvokeLLM({
      prompt: `You are an expert HR recruiter. Evaluate this candidate for the job position.

Job Title: ${job?.title || "N/A"}
Job Requirements: ${job?.requirements || "N/A"}
Required Skills: ${job?.skills || "N/A"}
Required Experience: ${job?.experience_years || "N/A"} years

Candidate: ${candidate.full_name}
Skills: ${candidate.skills || "N/A"}
Education: ${candidate.education || "N/A"}
Experience: ${candidate.experience_years || "N/A"} years
CV Summary: ${candidate.parsed_data || "N/A"}

Score this candidate from 0-100 based on how well they match the job requirements. Provide a brief evaluation summary in Vietnamese.`,
      response_json_schema: {
        type: "object",
        properties: {
          score: { type: "number", description: "Score from 0-100" },
          summary: { type: "string", description: "Evaluation summary in Vietnamese" }
        }
      }
    });
    await base44.entities.Candidate.update(candidate.id, {
      ai_score: result.score || 0,
      ai_summary: result.summary || "",
      stage: "screening",
    });
    await logAction("AI Screening", "Candidate", candidate.id, candidate.full_name, `AI Score: ${result.score}/100`);
    toast({ title: `AI Score: ${result.score}/100`, description: result.summary?.slice(0, 100) });
    setScreeningId(null);
    loadData();
  };

  const handleScreenAll = async () => {
    const unscreened = candidates.filter((c) => c.ai_score == null || c.ai_score === 0);
    if (unscreened.length === 0) {
      toast({ title: "Tất cả ứng viên đã được đánh giá" });
      return;
    }
    toast({ title: `Đang đánh giá ${unscreened.length} ứng viên...` });
    for (const c of unscreened) {
      await handleAIScreen(c);
    }
    toast({ title: "Đã đánh giá xong tất cả ứng viên" });
  };

  const filtered = candidates.filter((c) => {
    const matchSearch = c.full_name?.toLowerCase().includes(search.toLowerCase()) || c.email?.toLowerCase().includes(search.toLowerCase()) || c.skills?.toLowerCase().includes(search.toLowerCase());
    const matchStage = stageFilter === "all" || c.stage === stageFilter;
    const matchJob = jobFilter === "all" || c.job_id === jobFilter;
    return matchSearch && matchStage && matchJob;
  });

  const sorted = [...filtered].sort((a, b) => (b.ai_score || 0) - (a.ai_score || 0));

  if (loading) return <div className="flex items-center justify-center h-full"><div className="w-8 h-8 border-4 border-slate-200 border-t-indigo-600 rounded-full animate-spin" /></div>;

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-heading font-bold text-slate-900">Ứng viên</h1>
          <p className="text-slate-500 mt-1">{candidates.length} ứng viên</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleScreenAll} className="gap-2">
            <Sparkles size={16} /> AI Đánh giá tất cả
          </Button>
          <Button onClick={() => setShowForm(true)} className="bg-indigo-600 hover:bg-indigo-700 gap-2">
            <Plus size={18} /> Thêm ứng viên
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input placeholder="Tìm theo tên, email, kỹ năng..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" />
        </div>
        <Select value={stageFilter} onValueChange={setStageFilter}>
          <SelectTrigger className="w-40"><SelectValue placeholder="Giai đoạn" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tất cả</SelectItem>
            {Object.entries(STAGE_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={jobFilter} onValueChange={setJobFilter}>
          <SelectTrigger className="w-48"><SelectValue placeholder="Vị trí" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tất cả vị trí</SelectItem>
            {jobs.map((j) => <SelectItem key={j.id} value={j.id}>{j.title}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {sorted.length === 0 ? (
        <div className="text-center py-20">
          <Users size={48} className="mx-auto text-slate-300 mb-4" />
          <p className="text-slate-500">Chưa có ứng viên nào</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sorted.map((c, i) => (
            <div key={c.id} className="relative">
              {screeningId === c.id && (
                <div className="absolute inset-0 bg-white/80 z-10 flex items-center justify-center rounded-xl">
                  <Loader2 className="animate-spin text-indigo-600" size={24} />
                  <span className="ml-2 text-sm text-indigo-600">Đang đánh giá AI...</span>
                </div>
              )}
              <CandidateCard candidate={c} rank={c.ai_score ? i + 1 : null} onUpdate={loadData} />
              {(c.ai_score == null || c.ai_score === 0) && (
                <div className="absolute top-5 right-48">
                  <Button variant="ghost" size="sm" onClick={() => handleAIScreen(c)} className="text-indigo-600 hover:text-indigo-700 text-xs gap-1">
                    <Sparkles size={14} /> Đánh giá AI
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Thêm ứng viên mới</DialogTitle></DialogHeader>
          <CandidateForm jobs={jobs} onSave={handleAddCandidate} onCancel={() => setShowForm(false)} />
        </DialogContent>
      </Dialog>
    </div>
  );
}