export interface User {
  id: number;
  email: string;
}

export type VideoStatus = 'pending' | 'uploading' | 'uploaded' | 'processing' | 'ready' | 'failed';

export interface Video {
  id: number;
  title: string;
  description: string;
  owner_id: number;
  status: VideoStatus;
  created_at: string;
  // Контракт с бэкендом (Этап 5): адрес master.m3u8, null пока видео не готово.
  playback_url: string | null;
}

export interface StartUploadResponse {
  id: number;
  status: VideoStatus;
  chunk_size: number;
}

/** Статусы, при которых видео ещё может измениться без участия пользователя. */
export const IN_PROGRESS_STATUSES: readonly VideoStatus[] = ['uploaded', 'processing'];
