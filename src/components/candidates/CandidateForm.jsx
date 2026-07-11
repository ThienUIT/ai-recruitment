import React, { useState } from "react";
import { base44 } from "@/api/base44Client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Upload, FileText, Loader2 } from "lucide-react";

export default function CandidateForm({ jobs, onSave, onCancel }) {
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    job_id: "",
    source: "direct",
    notes: "",
    cv_url: "",
  });
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState("");

  const update = (key, val) => setForm((p) => ({ ...p, [key]: val }));

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setFileName(file.name);
    const { file_url } = await base44.integrations.Core.UploadFile({ file });
    update("cv_url", file_url);
    setUploading(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    await onSave(form);
    setSaving(false);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label>Họ tên *</Label>
          <Input value={form.full_name} onChange={(e) => update("full_name", e.target.value)} required placeholder="VD: Nguyễn Văn A" />
        </div>
        <div>
          <Label>Email *</Label>
          <Input type="email" value={form.email} onChange={(e) => update("email", e.target.value)} required placeholder="email@example.com" />
        </div>
        <div>
          <Label>Số điện thoại</Label>
          <Input value={form.phone} onChange={(e) => update("phone", e.target.value)} placeholder="0912345678" />
        </div>
        <div>
          <Label>Vị trí ứng tuyển *</Label>
          <Select value={form.job_id} onValueChange={(v) => update("job_id", v)} required>
            <SelectTrigger><SelectValue placeholder="Chọn vị trí" /></SelectTrigger>
            <SelectContent>
              {jobs.map((j) => <SelectItem key={j.id} value={j.id}>{j.title}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label>Nguồn</Label>
          <Select value={form.source} onValueChange={(v) => update("source", v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="direct">Trực tiếp</SelectItem>
              <SelectItem value="referral">Giới thiệu</SelectItem>
              <SelectItem value="linkedin">LinkedIn</SelectItem>
              <SelectItem value="website">Website</SelectItem>
              <SelectItem value="other">Khác</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label>Upload CV</Label>
          <div className="relative">
            <input type="file" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg" onChange={handleFileUpload} className="hidden" id="cv-upload" />
            <label htmlFor="cv-upload" className="flex items-center gap-2 px-4 py-2 border border-slate-200 rounded-md cursor-pointer hover:bg-slate-50 transition-colors text-sm">
              {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
              {fileName || "Chọn file CV"}
            </label>
            {form.cv_url && <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1"><FileText size={12} /> Đã upload</p>}
          </div>
        </div>
        <div className="col-span-2">
          <Label>Ghi chú</Label>
          <Textarea value={form.notes} onChange={(e) => update("notes", e.target.value)} rows={3} placeholder="Ghi chú thêm về ứng viên..." />
        </div>
      </div>
      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>Hủy</Button>
        <Button type="submit" disabled={saving || uploading} className="bg-indigo-600 hover:bg-indigo-700">
          {saving ? "Đang lưu..." : "Thêm ứng viên"}
        </Button>
      </div>
    </form>
  );
}