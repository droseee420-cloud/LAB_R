export const createLeadsTable = `
  CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    name TEXT,
    contact_method TEXT NOT NULL,
    contact TEXT NOT NULL,
    message TEXT NOT NULL,
    product_link TEXT,
    no_product INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new'
  )
`;

export const createLeadFilesTable = `
  CREATE TABLE IF NOT EXISTS lead_files (
    id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL,
    object_key TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT,
    size_bytes INTEGER NOT NULL,
    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
  )
`;

export const createLeadStatusIndex = `
  CREATE INDEX IF NOT EXISTS idx_leads_status_created_at
  ON leads(status, created_at)
`;

export const createLeadFilesIndex = `
  CREATE INDEX IF NOT EXISTS idx_lead_files_lead_id
  ON lead_files(lead_id)
`;
