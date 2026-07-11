import React, { useState } from "react";
import { base44 } from "@/api/base44Client";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { FileText, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { logAction } from "@/lib/auditLogger";

const STAGE_LABELS = { applied: "Đã ứng tuyển", screening: "Đang sàng lọc", interview: "Phỏng vấn", offer: "Đề nghị", hired: "Đã tuyển", rejected: "Từ chối" };
const STAGE_COLORS = { applied: "#6366f1", screening: "#f59e0b", interview: "#3b82f6", offer: "#8b5cf6", hired: "#10b981", rejected: "#ef4444" };

export default function CandidateCard({ candidate, rank, onUpdate }) {
  const [expanded, setExpanded] = useState(false);
  const { toast } = useToast();

  const handleStageChange = async (newStage) => {
    await base44.entities.Candidate.update(candidate.id, { stage: newStage });
    await logAction("Cập nhật giai đoạn", "Candidate", candidate.id, candidate.full_name, `${STAGE_LABELS[candidate.stage]} → ${STAGE_LABELS[newStage]}`);
    toast({ title: `Đã chuyển sang ${STAGE_LABELS[newStage]}` });
    onUpdate?.();
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-sm font-bold">
            {rank ? `#${rank}` : candidate.full_name?.charAt(0)?.toUpperCase()}
          </div>
          <div>
            <p className="font-semibold text-slate-900">{candidate.full_name}</p>
            <p className="text-xs text-slate-500">{candidate.email} {candidate.phone && `• ${candidate.phone}`}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {candidate.ai_score != null && (
            <div className="text-center">
              <div className={`text-lg font-bold ${candidate.ai_score >= 70 ? "text-emerald-600" : candidate.ai_score >= 40 ? "text-amber-600" : "text-red-500"}`}>
                {candidate.ai_score}
              </div>
              <div className="text-[10px] text-slate-400 uppercase tracking-wider">AI Score</div>
            </div>
          )}
          <Select value={candidate.stage} onValueChange={handleStageChange}>
            <SelectTrigger className="w-36 h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(STAGE_LABELS).map(([k, v]) => (
                <SelectItem key={k} value={k}>{v}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {candidate.cv_url && (
            <a href={candidate.cv_url} target="_blank" rel="noopener noreferrer">
              <Button variant="ghost" size="icon" className="text-slate-400 hover:text-indigo-600"><FileText size={18} /></Button>
            </a>
          )}
          <Button variant="ghost" size="icon" onClick={() => setExpanded(!expanded)}>
            {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </Button>
        </div>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-slate-100 space-y-3 text-sm">
          {candidate.skills && (
            <div>
              <span className="font-medium text-slate-700">Kỹ năng: </span>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {candidate.skills.split(",").map((s) => (
                  <span key={s} className="text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded">{s.trim()}</span>
                ))}
              </div>
            </div>
          )}
          {candidate.education && <p><span className="font-medium text-slate-700">Học vấn: </span><span className="text-slate-600">{candidate.education}</span></p>}
          {candidate.experience_years != null && <p><span className="font-medium text-slate-700">Kinh nghiệm: </span><span className="text-slate-600">{candidate.experience_years} năm</span></p>}
          {candidate.ai_summary && (
            <div className="bg-indigo-50 rounded-lg p-3">
              <p className="text-xs font-medium text-indigo-700 mb-1">Đánh giá AI</p>
              <p className="text-sm text-indigo-900">{candidate.ai_summary}</p>
            </div>
          )}
          {candidate.notes && <p><span className="font-medium text-slate-700">Ghi chú: </span><span className="text-slate-600">{candidate.notes}</span></p>}
        </div>
      )}
    </div>
  );
}