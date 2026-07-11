import { base44 } from "@/api/base44Client";

export async function logAction(action, entityType, entityId, entityName, details) {
  try {
    const user = await base44.auth.me();
    await base44.entities.AuditLog.create({
      action,
      entity_type: entityType,
      entity_id: entityId,
      entity_name: entityName || "",
      details: details || "",
      performed_by: user?.full_name || user?.email || "System",
    });
  } catch (e) {
    console.error("Audit log error:", e);
  }
}