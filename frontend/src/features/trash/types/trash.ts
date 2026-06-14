export type TrashReference = {
  reference_type: string;
  reference_id: string;
  name: string;
  field: string;
  detail?: string | null;
};

export type TrashItem = {
  item_type: string;
  item_id: string;
  name: string;
  deleted_at?: string | null;
  deleted_by?: string | null;
  delete_reason?: string | null;
  restore_supported: boolean;
  purge_supported: boolean;
  reference_count: number;
  metadata: Record<string, unknown>;
};

export type TrashGroup = {
  item_type: string;
  title: string;
  items: TrashItem[];
};

export type TrashList = {
  groups: TrashGroup[];
};

export type TrashUsage = {
  item_type: string;
  item_id: string;
  references: TrashReference[];
};
