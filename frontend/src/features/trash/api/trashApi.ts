import { apiClient } from '../../../lib/api/client';
import type { TrashItem, TrashList, TrashUsage } from '../types/trash';

export async function listTrash(): Promise<TrashList> {
  const response = await apiClient.get<TrashList>('/trash');
  return response.data;
}

export async function getTrashReferences(itemType: string, itemId: string): Promise<TrashUsage> {
  const response = await apiClient.get<TrashUsage>(`/trash/${itemType}/${itemId}/references`);
  return response.data;
}

export async function restoreTrashItem(itemType: string, itemId: string): Promise<TrashItem> {
  const response = await apiClient.post<TrashItem>(`/trash/${itemType}/${itemId}/restore`);
  return response.data;
}

export async function purgeTrashItem(itemType: string, itemId: string): Promise<void> {
  await apiClient.delete(`/trash/${itemType}/${itemId}/purge`);
}
