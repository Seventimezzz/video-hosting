import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { interval } from 'rxjs';

import { AuthService } from '../../core/auth.service';
import { errorMessage } from '../../core/errors';
import { IN_PROGRESS_STATUSES, Video } from '../../core/models';
import { VideoService } from '../../core/video.service';

const POLL_INTERVAL_MS = 3000;

@Component({
  selector: 'app-video-list',
  imports: [RouterLink, DatePipe],
  template: `
    <h2>Видео</h2>
    @if (error()) {
      <p class="error">{{ error() }}</p>
    }
    @if (videos() === null) {
      @if (!error()) {
        <p class="muted">Загрузка…</p>
      }
    } @else if (videos()!.length === 0) {
      <p class="muted">Пока нет ни одного видео.</p>
    } @else {
      <ul>
        @for (video of videos(); track video.id) {
          <li class="card">
            <div class="row">
              <a [routerLink]="['/videos', video.id]">{{ video.title }}</a>
              <span class="status" [class]="video.status">{{ video.status }}</span>
            </div>
            @if (video.description) {
              <div class="muted">{{ video.description }}</div>
            }
            <div class="row">
              <small class="muted">#{{ video.id }} · {{ video.created_at | date: 'dd.MM.yyyy HH:mm' }}</small>
              @if (auth.user()?.id === video.owner_id) {
                <button class="danger" (click)="remove(video)">Удалить</button>
              }
            </div>
          </li>
        }
      </ul>
    }
  `,
  styles: `
    ul {
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 10px;
    }
    .row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }
  `,
})
export class VideoList {
  protected readonly auth = inject(AuthService);
  private readonly videoService = inject(VideoService);

  protected readonly videos = signal<Video[] | null>(null);
  protected readonly error = signal<string | null>(null);

  private readonly hasInProgress = computed(
    () => this.videos()?.some((v) => IN_PROGRESS_STATUSES.includes(v.status)) ?? false,
  );

  constructor() {
    this.load();
    // Статус меняет воркер в фоне, push-уведомлений нет, поэтому опрашиваем,
    // пока в списке есть видео в обработке.
    interval(POLL_INTERVAL_MS)
      .pipe(takeUntilDestroyed())
      .subscribe(() => {
        if (this.hasInProgress()) {
          this.load();
        }
      });
  }

  private async load(): Promise<void> {
    try {
      const videos = await this.videoService.list();
      this.videos.set(videos.sort((a, b) => b.id - a.id));
      this.error.set(null);
    } catch (err) {
      this.error.set(errorMessage(err));
    }
  }

  protected async remove(video: Video): Promise<void> {
    if (!confirm(`Удалить «${video.title}»?`)) {
      return;
    }
    try {
      await this.videoService.delete(video.id);
      this.videos.update((list) => list?.filter((v) => v.id !== video.id) ?? null);
    } catch (err) {
      this.error.set(errorMessage(err));
    }
  }
}
