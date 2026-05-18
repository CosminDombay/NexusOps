export type RemoteFileType = 'file' | 'directory' | 'symlink' | 'other';

export type RemoteFileEntry = {
  name: string;
  path: string;
  type: RemoteFileType;
  size: number;
  modified_at: string | null;
  permissions: string;
  owner: string | null;
  group: string | null;
};

export type RemoteDirectoryListing = {
  path: string;
  entries: RemoteFileEntry[];
};

export type RemoteFileRead = {
  path: string;
  content: string;
  sha256: string;
  size: number;
  modified_at: string | null;
};

export type RemoteFileWriteRequest = {
  path: string;
  content: string;
  expected_hash: string;
};

export type RemoteFileWriteResponse = {
  path: string;
  sha256: string;
  size: number;
  modified_at: string | null;
};
