// 90_kt_meeting_owner: record who uploaded a handover call; the first uploader stays the owner on re-ingest.
// Params: $meeting_id, $user_id.
MATCH (m:Meeting {id: $meeting_id})
SET m.uploaded_by = coalesce(m.uploaded_by, $user_id)
RETURN m.uploaded_by AS uploaded_by
