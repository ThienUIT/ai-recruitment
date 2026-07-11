import React, { useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";
import { Search, Sparkles, Loader2, Users, Briefcase } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import CandidateCard from "@/components/candidates/CandidateCard";

export default function SemanticSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [candidates, setCandidates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [tab, setTab] = useState("candidates");

  useEffect(() => {
    Promise.all([
      base44.entities.Candidate.list(),
      base44.entities.Job.list(),
    ]).then(([c, j]) => { setCandidates(c); setJobs(j); });
  }, []);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);

    const dataToSearch = tab === "candidates"
      ? candidates.map((c) => ({
          id: c.id,
          name: c.full_name,
          email: c.email,
          skills: c.skills,
          education: c.education,
          experience: c.experience_years,
          summary: c.parsed_data,
          ai_summary: c.ai_summary,
          stage: c.stage,
        }))
      : jobs.map((j) => ({
          id: j.id,
          title: j.title,
          department: j.department,
          location: j.location,
          skills: j.skills,
          description: j.description,
          requirements: j.requirements,
          status: j.status,
        }));

    const result = await base44.integrations.Core.InvokeLLM({
      prompt: `You are a semantic search engine for a recruitment system. Search through the following ${tab} data and return the IDs that best match the user's search query. Rank by relevance.

Search query: "${query}"

Data:
${JSON.stringify(dataToSearch, null, 2)}

Return the IDs of matching items ordered by relevance. If no good matches, return empty array.`,
      response_json_schema: {
        type: "object",
        properties: {
          matched_ids: { type: "array", items: { type: "string" }, description: "Ordered list of matching IDs" },
          explanation: { type: "string", description: "Brief explanation of results in Vietnamese" }
        }
      }
    });

    setResults(result);
    setSearching(false);
  };

  const matchedCandidates = results?.matched_ids?.map((id) => candidates.find((c) => c.id === id)).filter(Boolean) || [];
  const matchedJobs = results?.matched_ids?.map((id) => jobs.find((j) => j.id === id)).filter(Boolean) || [];

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-heading font-bold text-slate-900">Tìm kiếm AI</h1>
        <p className="text-slate-500 mt-1">Tìm kiếm thông minh với AI — tìm ứng viên hoặc vị trí phù hợp</p>
      </div>

      <Tabs value={tab} onValueChange={(v) => { setTab(v); setResults(null); }}>
        <TabsList>
          <TabsTrigger value="candidates" className="gap-2"><Users size={14} /> Ứng viên</TabsTrigger>
          <TabsTrigger value="jobs" className="gap-2"><Briefcase size={14} /> Việc làm</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder={tab === "candidates" ? 'VD: "Tìm developer biết React có 3 năm kinh nghiệm"' : 'VD: "Vị trí cần kỹ năng Python tại Hà Nội"'}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="pl-10 h-12 text-base"
          />
        </div>
        <Button onClick={handleSearch} disabled={searching || !query.trim()} className="bg-indigo-600 hover:bg-indigo-700 h-12 px-6 gap-2">
          {searching ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
          Tìm kiếm
        </Button>
      </div>

      {results && (
        <div className="space-y-4">
          {results.explanation && (
            <div className="bg-indigo-50 rounded-xl p-4">
              <p className="text-sm text-indigo-800"><Sparkles size={14} className="inline mr-2" />{results.explanation}</p>
            </div>
          )}

          {tab === "candidates" ? (
            matchedCandidates.length === 0 ? (
              <p className="text-slate-400 text-center py-10">Không tìm thấy ứng viên phù hợp</p>
            ) : (
              <div className="space-y-3">
                {matchedCandidates.map((c, i) => (
                  <CandidateCard key={c.id} candidate={c} rank={i + 1} onUpdate={() => {}} />
                ))}
              </div>
            )
          ) : (
            matchedJobs.length === 0 ? (
              <p className="text-slate-400 text-center py-10">Không tìm thấy vị trí phù hợp</p>
            ) : (
              <div className="space-y-3">
                {matchedJobs.map((j) => (
                  <div key={j.id} className="bg-white rounded-xl border border-slate-200 p-5">
                    <h3 className="font-semibold text-slate-900">{j.title}</h3>
                    <p className="text-sm text-slate-500 mt-1">{j.department} {j.location && `• ${j.location}`}</p>
                    {j.skills && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {j.skills.split(",").map((s) => (
                          <span key={s} className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded">{s.trim()}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )
          )}
        </div>
      )}

      {!results && !searching && (
        <div className="text-center py-20">
          <Search size={48} className="mx-auto text-slate-300 mb-4" />
          <p className="text-slate-500">Nhập từ khóa để tìm kiếm thông minh</p>
          <p className="text-slate-400 text-sm mt-1">Sử dụng ngôn ngữ tự nhiên — AI sẽ hiểu ý bạn</p>
        </div>
      )}
    </div>
  );
}