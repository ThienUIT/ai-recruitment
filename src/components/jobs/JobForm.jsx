import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function JobForm({ job, onSave, onCancel }) {
  const [form, setForm] = useState({
    title: job?.title || "",
    department: job?.department || "",
    location: job?.location || "",
    employment_type: job?.employment_type || "full_time",
    salary_min: job?.salary_min || "",
    salary_max: job?.salary_max || "",
    description: job?.description || "",
    requirements: job?.requirements || "",
    status: job?.status || "draft",
    deadline: job?.deadline || "",
    experience_years: job?.experience_years || "",
    skills: job?.skills || "",
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const data = { ...form };
    if (data.salary_min) data.salary_min = Number(data.salary_min);
    else delete data.salary_min;
    if (data.salary_max) data.salary_max = Number(data.salary_max);
    else delete data.salary_max;
    if (data.experience_years) data.experience_years = Number(data.experience_years);
    else delete data.experience_years;
    await onSave(data);
    setSaving(false);
  };

  const update = (key, val) => setForm((p) => ({ ...p, [key]: val }));

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <Label>Tiêu đề *</Label>
          <Input value={form.title} onChange={(e) => update("title", e.target.value)} placeholder="VD: Senior Frontend Developer" required />
        </div>
        <div>
          <Label>Phòng ban *</Label>
          <Input value={form.department} onChange={(e) => update("department", e.target.value)} placeholder="VD: Engineering" required />
        </div>
        <div>
          <Label>Địa điểm</Label>
          <Input value={form.location} onChange={(e) => update("location", e.target.value)} placeholder="VD: Hà Nội" />
        </div>
        <div>
          <Label>Loại hình</Label>
          <Select value={form.employment_type} onValueChange={(v) => update("employment_type", v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="full_time">Toàn thời gian</SelectItem>
              <SelectItem value="part_time">Bán thời gian</SelectItem>
              <SelectItem value="contract">Hợp đồng</SelectItem>
              <SelectItem value="internship">Thực tập</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label>Trạng thái</Label>
          <Select value={form.status} onValueChange={(v) => update("status", v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="draft">Nháp</SelectItem>
              <SelectItem value="open">Đang mở</SelectItem>
              <SelectItem value="closed">Đã đóng</SelectItem>
              <SelectItem value="on_hold">Tạm dừng</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label>Lương tối thiểu</Label>
          <Input type="number" value={form.salary_min} onChange={(e) => update("salary_min", e.target.value)} placeholder="VD: 20000000" />
        </div>
        <div>
          <Label>Lương tối đa</Label>
          <Input type="number" value={form.salary_max} onChange={(e) => update("salary_max", e.target.value)} placeholder="VD: 35000000" />
        </div>
        <div>
          <Label>Kinh nghiệm (năm)</Label>
          <Input type="number" value={form.experience_years} onChange={(e) => update("experience_years", e.target.value)} placeholder="VD: 3" />
        </div>
        <div>
          <Label>Hạn nộp</Label>
          <Input type="date" value={form.deadline} onChange={(e) => update("deadline", e.target.value)} />
        </div>
        <div className="col-span-2">
          <Label>Kỹ năng yêu cầu</Label>
          <Input value={form.skills} onChange={(e) => update("skills", e.target.value)} placeholder="VD: React, Node.js, TypeScript (phân cách bằng dấu phẩy)" />
        </div>
        <div className="col-span-2">
          <Label>Mô tả công việc</Label>
          <Textarea value={form.description} onChange={(e) => update("description", e.target.value)} rows={4} placeholder="Mô tả chi tiết về vị trí..." />
        </div>
        <div className="col-span-2">
          <Label>Yêu cầu</Label>
          <Textarea value={form.requirements} onChange={(e) => update("requirements", e.target.value)} rows={4} placeholder="Các yêu cầu cho ứng viên..." />
        </div>
      </div>
      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>Hủy</Button>
        <Button type="submit" disabled={saving} className="bg-indigo-600 hover:bg-indigo-700">
          {saving ? "Đang lưu..." : (job ? "Cập nhật" : "Tạo việc làm")}
        </Button>
      </div>
    </form>
  );
}