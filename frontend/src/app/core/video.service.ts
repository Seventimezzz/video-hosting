import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { StartUploadResponse, Video } from './models';

const CHUNK_RETRIES = 3;

export interface UploadProgress {
  sentBytes: number;
  totalBytes: number;
}

@Injectable({ providedIn: 'root' })
export class VideoService {
  private readonly http = inject(HttpClient);

  list(): Promise<Video[]> {
    return firstValueFrom(this.http.get<Video[]>('/api/videos'));
  }

  get(id: number): Promise<Video> {
    return firstValueFrom(this.http.get<Video>(`/api/videos/${id}`));
  }

  delete(id: number): Promise<unknown> {
    return firstValueFrom(this.http.delete(`/api/videos/${id}`));
  }

  /**
   * Полный протокол chunked upload из Этапа 3:
   * create → start (сервер говорит chunk_size) → PUT чанков 1..N → complete.
   * Прогресс считается по отправленным чанкам: при 5 МБ на чанк это достаточно плавно.
   */
  async upload(
    file: File,
    title: string,
    description: string,
    onProgress: (p: UploadProgress) => void,
  ): Promise<Video> {
    const video = await firstValueFrom(
      this.http.post<Video>('/api/videos', { title, description }),
    );
    const start = await firstValueFrom(
      this.http.post<StartUploadResponse>(`/api/videos/${video.id}/upload`, {
        total_size: file.size,
      }),
    );

    const chunkSize = start.chunk_size;
    const chunkCount = Math.ceil(file.size / chunkSize);
    onProgress({ sentBytes: 0, totalBytes: file.size });

    // Чанки на сервере нумеруются с 1 (см. upload_video_complete).
    for (let n = 1; n <= chunkCount; n++) {
      const begin = (n - 1) * chunkSize;
      const end = Math.min(begin + chunkSize, file.size);
      await this.putChunk(video.id, n, file.slice(begin, end));
      onProgress({ sentBytes: end, totalBytes: file.size });
    }

    return firstValueFrom(
      this.http.post<Video>(`/api/videos/${video.id}/upload/complete`, {}),
    );
  }

  /** PUT чанка идемпотентен на сервере, поэтому сетевой сбой можно просто повторить. */
  private async putChunk(videoId: number, n: number, blob: Blob): Promise<void> {
    for (let attempt = 1; ; attempt++) {
      try {
        await firstValueFrom(
          this.http.put(`/api/videos/${videoId}/upload/chunks/${n}`, blob, {
            headers: { 'Content-Type': 'application/octet-stream' },
          }),
        );
        return;
      } catch (err) {
        const retryable = err instanceof HttpErrorResponse && (err.status === 0 || err.status >= 500);
        if (!retryable || attempt >= CHUNK_RETRIES) {
          throw err;
        }
        await new Promise((resolve) => setTimeout(resolve, 1000 * attempt));
      }
    }
  }
}
